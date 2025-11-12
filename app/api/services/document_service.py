import hashlib
from pathlib import Path
from typing import List, Optional
from uuid import UUID

import structlog

logger = structlog.get_logger()


class DocumentService:
    """CRUD + storage helpers for uploaded documents."""

    def __init__(self, db, storage_path: str = "/app/uploads"):
        self.db = db
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

    async def create_document(
        self,
        user_id: UUID,
        filename: str,
        file_content: bytes,
        mime_type: str,
    ) -> dict:
        search_path = await self.db.fetchval("SHOW search_path")
        logger.info("document_create_search_path", search_path=search_path)
        file_hash = hashlib.sha256(file_content).hexdigest()

        existing = await self.db.fetchrow(
            """
            SELECT * FROM documents
            WHERE user_id = $1 AND sha256 = $2
            """,
            user_id,
            file_hash,
        )

        if existing:
            logger.info(
                "duplicate_document_skipped",
                user_id=str(user_id),
                document_id=str(existing["id"]),
                filename=filename,
                sha256=file_hash,
            )
            data = dict(existing)
            data["message"] = f"Document already exists: {existing['filename']}"
            return {"success": True, "deduplicated": True, "data": data}

        user_folder = self.storage_path / f"{user_id}"
        user_folder.mkdir(parents=True, exist_ok=True)
        file_path = user_folder / f"{file_hash}_{filename}"
        file_path.write_bytes(file_content)

        storage_rel_path = file_path.relative_to(self.storage_path.parent)

        document = await self.db.fetchrow(
            """
            INSERT INTO documents (
                user_id, filename, source, storage_path, mime_type,
                sha256, size_bytes, status
            )
            VALUES ($1, $2, 'upload', $3, $4, $5, $6, 'pending')
            RETURNING *
            """,
            user_id,
            filename,
            str(storage_rel_path),
            mime_type,
            file_hash,
            len(file_content),
        )

        logger.info(
            "document_created",
            user_id=str(user_id),
            document_id=str(document["id"]),
            filename=filename,
            size_bytes=len(file_content),
            sha256=file_hash,
        )

        return {"success": True, "data": dict(document)}

    async def get_document(self, document_id: UUID, user_id: UUID) -> Optional[dict]:
        record = await self.db.fetchrow(
            """
            SELECT * FROM documents
            WHERE id = $1 AND user_id = $2
            """,
            document_id,
            user_id,
        )
        return dict(record) if record else None

    async def list_documents(
        self,
        user_id: UUID,
        status: Optional[str] = None,
        limit: int = 50,
        cursor: Optional[UUID] = None,
    ) -> List[dict]:
        # Whitelist of valid document statuses to prevent SQL injection
        VALID_STATUSES = {"pending", "processing", "indexed", "failed"}

        clauses = ["user_id = $1"]
        params = [user_id]

        if status:
            # Validate status against whitelist
            if status not in VALID_STATUSES:
                logger.warning(
                    "invalid_document_status_rejected",
                    status=status,
                    user_id=str(user_id)
                )
                # Return empty list for invalid status instead of raising error
                return []
            clauses.append(f"status = ${len(params) + 1}")
            params.append(status)

        if cursor:
            clauses.append(f"id < ${len(params) + 1}")
            params.append(cursor)

        params.append(limit)
        where_sql = " AND ".join(clauses)

        rows = await self.db.fetch(
            f"""
            SELECT * FROM documents
            WHERE {where_sql}
            ORDER BY created_at DESC
            LIMIT ${len(params)}
            """,
            *params,
        )
        return [dict(row) for row in rows]

    async def delete_document(self, document_id: UUID, user_id: UUID) -> bool:
        document = await self.get_document(document_id, user_id)
        if not document:
            return False

        from api.services.vector_service import VectorService

        vector_service = VectorService()
        await vector_service.delete_document(document_id)

        file_path = Path(self.storage_path.parent) / document["storage_path"]
        if file_path.exists():
            file_path.unlink()

        await self.db.execute("DELETE FROM documents WHERE id = $1", document_id)

        logger.info(
            "document_deleted",
            user_id=str(user_id),
            document_id=str(document_id),
            filename=document["filename"],
        )
        return True

    async def get_chunks(self, document_id: UUID, user_id: UUID) -> List[dict]:
        document = await self.get_document(document_id, user_id)
        if not document:
            return []

        rows = await self.db.fetch(
            """
            SELECT * FROM chunks
            WHERE document_id = $1
            ORDER BY ordinal ASC
            """,
            document_id,
        )
        return [dict(row) for row in rows]


class JobService:
    """Basic CRUD helper for async jobs."""

    def __init__(self, db):
        self.db = db

    async def create_job(self, user_id: UUID, job_type: str, payload: dict) -> dict:
        record = await self.db.fetchrow(
            """
            INSERT INTO jobs (user_id, type, status, payload)
            VALUES ($1, $2, 'pending', $3)
            RETURNING *
            """,
            user_id,
            job_type,
            payload,
        )

        logger.info(
            "job_created", user_id=str(user_id), job_id=str(record["id"]), type=job_type
        )
        return dict(record)

    async def get_job(self, job_id: UUID, user_id: UUID) -> Optional[dict]:
        record = await self.db.fetchrow(
            """
            SELECT * FROM jobs
            WHERE id = $1 AND user_id = $2
            """,
            job_id,
            user_id,
        )
        return dict(record) if record else None

    async def update_job_status(
        self,
        job_id: UUID,
        status: str,
        result: Optional[dict] = None,
        error_message: Optional[str] = None,
    ) -> None:
        updates = ["status = $2", "updated_at = NOW()"]
        params = [job_id, status]
        placeholder = 3

        if status == "running":
            updates.append("started_at = NOW()")
        elif status in {"completed", "failed"}:
            updates.append("completed_at = NOW()")

        if result is not None:
            updates.append(f"result = ${placeholder}")
            params.append(result)
            placeholder += 1

        if error_message:
            updates.append(f"error_message = ${placeholder}")
            params.append(error_message)

        query = f"UPDATE jobs SET {', '.join(updates)} WHERE id = $1"
        await self.db.execute(query, *params)

        logger.info(
            "job_updated",
            job_id=str(job_id),
            status=status,
            has_error=bool(error_message),
        )
