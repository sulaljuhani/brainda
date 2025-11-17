"""Service for handling file uploads in chat."""
import os
import uuid
from typing import Optional, List, Dict, Any
from uuid import UUID
from pathlib import Path
import mimetypes
import hashlib
import json

try:
    from PIL import Image
except ImportError:
    Image = None

import structlog

logger = structlog.get_logger()


class ChatFileService:
    """Handle file uploads, storage, and processing for chat."""

    def __init__(self, db, storage_root: str = "/app/uploads/chat"):
        self.db = db
        self.storage_root = Path(storage_root)
        self.storage_root.mkdir(parents=True, exist_ok=True)

    async def save_file(
        self,
        user_id: UUID,
        conversation_id: Optional[UUID],
        message_id: Optional[UUID],
        file_content: bytes,
        filename: str,
        mime_type: str,
    ) -> Dict[str, Any]:
        """Save uploaded file and create database record."""

        # Generate unique filename
        file_id = uuid.uuid4()
        ext = Path(filename).suffix
        unique_filename = f"{file_id}{ext}"

        # User-specific directory
        user_dir = self.storage_root / str(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)

        file_path = user_dir / unique_filename

        # Write file
        with open(file_path, "wb") as f:
            f.write(file_content)

        # Determine file type
        file_type = self._detect_file_type(mime_type)

        # Extract metadata
        metadata = await self._extract_metadata(file_path, file_type)

        # Create database record
        row = await self.db.fetchrow(
            """
            INSERT INTO chat_files (
                id, user_id, conversation_id, message_id,
                filename, original_filename, mime_type, file_size_bytes,
                storage_path, status, metadata
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING id, filename, mime_type, file_size_bytes, storage_path, status, metadata
            """,
            file_id,
            user_id,
            conversation_id,
            message_id,
            unique_filename,
            filename,
            mime_type,
            len(file_content),
            str(file_path),
            "pending",
            json.dumps(metadata),
        )

        logger.info("chat_file_saved", file_id=str(file_id), filename=filename, size=len(file_content))

        return dict(row)

    def _detect_file_type(self, mime_type: str) -> str:
        """Detect file type from MIME type."""
        if mime_type.startswith("image/"):
            return "image"
        elif mime_type == "application/pdf":
            return "pdf"
        elif mime_type.startswith("audio/"):
            return "audio"
        elif mime_type.startswith("video/"):
            return "video"
        elif mime_type in ["text/plain", "text/markdown"]:
            return "text"
        else:
            return "document"

    async def _extract_metadata(self, file_path: Path, file_type: str) -> Dict[str, Any]:
        """Extract metadata from file."""
        metadata = {}

        if file_type == "image" and Image is not None:
            try:
                with Image.open(file_path) as img:
                    metadata["width"] = img.width
                    metadata["height"] = img.height
                    metadata["format"] = img.format
            except Exception as exc:
                logger.warning("failed_to_extract_image_metadata", error=str(exc))

        elif file_type == "audio":
            # TODO: Extract duration using ffprobe
            pass

        return metadata

    async def process_file(self, file_id: UUID, user_id: UUID) -> Dict[str, Any]:
        """Process file: extract text, generate embeddings, create thumbnail."""

        # Get file record
        file_record = await self.db.fetchrow(
            "SELECT * FROM chat_files WHERE id = $1 AND user_id = $2",
            file_id,
            user_id,
        )

        if not file_record:
            raise ValueError("File not found")

        # Update status to processing
        await self.db.execute(
            "UPDATE chat_files SET status = 'processing' WHERE id = $1",
            file_id,
        )

        try:
            file_type = self._detect_file_type(file_record["mime_type"])
            extracted_text = None

            # Extract text based on file type
            if file_type == "image":
                # For now, skip OCR - would need pytesseract or similar
                logger.info("image_processing_skipped", file_id=str(file_id), note="OCR not implemented yet")
                extracted_text = None

            elif file_type == "pdf":
                # Use existing document ingestion
                try:
                    from api.services.parsing_service import ParsingService
                    parser = ParsingService()
                    extracted_text = await parser.extract_text_from_pdf(
                        file_record["storage_path"]
                    )
                except Exception as exc:
                    logger.warning("pdf_extraction_failed", error=str(exc))
                    extracted_text = None

            elif file_type == "text":
                try:
                    with open(file_record["storage_path"], "r", encoding="utf-8") as f:
                        extracted_text = f.read()
                except Exception as exc:
                    logger.warning("text_extraction_failed", error=str(exc))
                    extracted_text = None

            elif file_type == "audio":
                # Skip transcription for now - would need whisper or similar
                logger.info("audio_processing_skipped", file_id=str(file_id), note="Transcription not implemented yet")
                extracted_text = None

            # Generate embedding if we have text
            embedding_id = None
            if extracted_text:
                try:
                    from api.services.embedding_service import EmbeddingService
                    from api.services.vector_service import VectorService

                    embedding_service = EmbeddingService()
                    vector_service = VectorService()

                    embedding = await embedding_service.create_embedding(extracted_text)

                    # Store in Qdrant
                    point_id = await vector_service.upsert(
                        point_id=str(file_id),
                        vector=embedding,
                        payload={
                            "user_id": str(user_id),
                            "content_type": "chat_file",
                            "file_id": str(file_id),
                            "filename": file_record["original_filename"],
                            "text": extracted_text[:1000],  # Store excerpt
                            "mime_type": file_record["mime_type"],
                        },
                    )
                    embedding_id = uuid.UUID(point_id)
                except Exception as exc:
                    logger.warning("embedding_generation_failed", error=str(exc))
                    embedding_id = None

            # Update record
            await self.db.execute(
                """
                UPDATE chat_files
                SET status = 'completed',
                    processed_at = NOW(),
                    extracted_text = $1,
                    embedding_id = $2
                WHERE id = $3
                """,
                extracted_text,
                embedding_id,
                file_id,
            )

            logger.info("chat_file_processed", file_id=str(file_id), has_text=bool(extracted_text))

            return {
                "success": True,
                "file_id": str(file_id),
                "extracted_text": extracted_text,
            }

        except Exception as exc:
            logger.error("chat_file_processing_failed", file_id=str(file_id), error=str(exc))

            await self.db.execute(
                """
                UPDATE chat_files
                SET status = 'failed', error_message = $1
                WHERE id = $2
                """,
                str(exc),
                file_id,
            )

            return {"success": False, "error": str(exc)}

    async def get_file(self, file_id: UUID, user_id: UUID) -> Optional[Dict[str, Any]]:
        """Get file record."""
        row = await self.db.fetchrow(
            "SELECT * FROM chat_files WHERE id = $1 AND user_id = $2",
            file_id,
            user_id,
        )
        return dict(row) if row else None

    async def get_file_content(self, file_id: UUID, user_id: UUID) -> Optional[bytes]:
        """Get file content from storage."""
        file_record = await self.get_file(file_id, user_id)
        if not file_record:
            return None

        file_path = Path(file_record["storage_path"])
        if not file_path.exists():
            return None

        with open(file_path, "rb") as f:
            return f.read()

    async def list_files_for_conversation(
        self, conversation_id: UUID, user_id: UUID
    ) -> List[Dict[str, Any]]:
        """List all files in a conversation."""
        rows = await self.db.fetch(
            """
            SELECT * FROM chat_files
            WHERE conversation_id = $1 AND user_id = $2
            ORDER BY created_at DESC
            """,
            conversation_id,
            user_id,
        )
        return [dict(row) for row in rows]

    async def delete_file(self, file_id: UUID, user_id: UUID) -> bool:
        """Delete file from storage and database."""
        file_record = await self.get_file(file_id, user_id)
        if not file_record:
            return False

        # Delete from storage
        file_path = Path(file_record["storage_path"])
        if file_path.exists():
            try:
                os.remove(file_path)
            except Exception as exc:
                logger.warning("file_deletion_failed", file_id=str(file_id), error=str(exc))

        # Delete from vector store if embedded
        if file_record.get("embedding_id"):
            try:
                from api.services.vector_service import VectorService
                vector_service = VectorService()
                await vector_service.delete(str(file_id))
            except Exception as exc:
                logger.warning("vector_deletion_failed", file_id=str(file_id), error=str(exc))

        # Delete from database (cascades to message attachments)
        await self.db.execute(
            "DELETE FROM chat_files WHERE id = $1 AND user_id = $2",
            file_id,
            user_id,
        )

        logger.info("chat_file_deleted", file_id=str(file_id))
        return True
