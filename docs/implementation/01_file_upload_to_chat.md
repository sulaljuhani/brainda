# File Upload to Chat - Implementation Plan

## Overview
Enable users to upload files (images, PDFs, documents, audio) directly in the chat interface. Files are processed, embedded for RAG context, and displayed with messages.

## Use Cases
- Upload screenshot → Ask "What does this error mean?"
- Upload PDF → Ask "Summarize this document"
- Upload invoice → Ask "Extract line items"
- Upload voice memo → Transcribe and create task
- Upload image → OCR text extraction

---

## Phase 1: Database Schema (30 mins)

### Migration: `migrations/022_add_chat_attachments.sql`

```sql
-- Add attachments column to chat_messages
ALTER TABLE chat_messages
ADD COLUMN IF NOT EXISTS attachments JSONB DEFAULT '[]'::jsonb;

-- Create index for querying messages with attachments
CREATE INDEX IF NOT EXISTS idx_chat_messages_attachments
ON chat_messages USING gin (attachments);

-- Create chat_files table for tracking uploaded files
CREATE TABLE IF NOT EXISTS chat_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES chat_conversations(id) ON DELETE CASCADE,
    message_id UUID REFERENCES chat_messages(id) ON DELETE CASCADE,

    filename VARCHAR(500) NOT NULL,
    original_filename VARCHAR(500) NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    storage_path TEXT NOT NULL,

    -- Processing metadata
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    processed_at TIMESTAMPTZ,
    error_message TEXT,

    -- Extracted content
    extracted_text TEXT,
    embedding_id UUID,  -- Reference to Qdrant point if embedded

    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_chat_files_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_chat_files_conversation FOREIGN KEY (conversation_id) REFERENCES chat_conversations(id) ON DELETE CASCADE,
    CONSTRAINT fk_chat_files_message FOREIGN KEY (message_id) REFERENCES chat_messages(id) ON DELETE CASCADE
);

CREATE INDEX idx_chat_files_user_id ON chat_files(user_id);
CREATE INDEX idx_chat_files_conversation_id ON chat_files(conversation_id);
CREATE INDEX idx_chat_files_message_id ON chat_files(message_id);
CREATE INDEX idx_chat_files_status ON chat_files(status);
```

### Attachments JSONB Structure
```json
[
  {
    "id": "uuid",
    "type": "image|pdf|audio|document",
    "filename": "screenshot.png",
    "url": "/api/v1/chat/files/{file_id}",
    "thumbnail_url": "/api/v1/chat/files/{file_id}/thumbnail",
    "mime_type": "image/png",
    "size_bytes": 123456,
    "status": "completed|processing|failed",
    "extracted_text": "...",
    "metadata": {
      "width": 1920,
      "height": 1080,
      "duration": 60  // for audio/video
    }
  }
]
```

---

## Phase 2: Backend - File Upload Service (2-3 hours)

### File: `app/api/services/chat_file_service.py` (NEW)

```python
"""Service for handling file uploads in chat."""
import os
import uuid
from typing import Optional, List, Dict, Any
from uuid import UUID
from pathlib import Path
import mimetypes
import hashlib

from PIL import Image
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
            metadata,
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

        if file_type == "image":
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
                # Queue OCR task
                from worker.tasks import extract_text_from_image_task
                result = await extract_text_from_image_task.delay(
                    file_record["storage_path"]
                )
                extracted_text = result.get(timeout=30)

            elif file_type == "pdf":
                # Use existing document ingestion
                from api.services.parsing_service import ParsingService
                parser = ParsingService()
                extracted_text = await parser.extract_text_from_pdf(
                    file_record["storage_path"]
                )

            elif file_type == "text":
                with open(file_record["storage_path"], "r") as f:
                    extracted_text = f.read()

            elif file_type == "audio":
                # Queue transcription task
                from worker.tasks import transcribe_audio_task
                result = transcribe_audio_task.delay(file_record["storage_path"])
                extracted_text = result.get(timeout=60)

            # Generate embedding if we have text
            embedding_id = None
            if extracted_text:
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
```

---

## Phase 3: Backend - Chat Endpoint Modification (1 hour)

### Update: `app/api/routers/chat.py`

Add file upload support to chat messages endpoint:

```python
from fastapi import File, UploadFile, Form
from typing import List

@router.post("/messages/with-files")
async def create_message_with_files(
    content: str = Form(...),
    conversation_id: Optional[UUID] = Form(None),
    files: List[UploadFile] = File(default=[]),
    user_id: UUID = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    """Create chat message with file attachments."""

    from api.services.chat_file_service import ChatFileService

    file_service = ChatFileService(db)
    attachments = []

    # Save files first
    for uploaded_file in files:
        file_content = await uploaded_file.read()

        file_record = await file_service.save_file(
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=None,  # Will update after message creation
            file_content=file_content,
            filename=uploaded_file.filename,
            mime_type=uploaded_file.content_type or "application/octet-stream",
        )

        attachments.append({
            "id": str(file_record["id"]),
            "type": file_service._detect_file_type(file_record["mime_type"]),
            "filename": file_record["original_filename"],
            "url": f"/api/v1/chat/files/{file_record['id']}",
            "mime_type": file_record["mime_type"],
            "size_bytes": file_record["file_size_bytes"],
            "status": file_record["status"],
            "metadata": file_record["metadata"],
        })

    # Create message with attachments
    async with db.transaction():
        # Create or verify conversation
        if not conversation_id:
            conv_row = await db.fetchrow(
                "INSERT INTO chat_conversations (user_id) VALUES ($1) RETURNING id",
                user_id,
            )
            conversation_id = conv_row["id"]

        # Create message
        message_row = await db.fetchrow(
            """
            INSERT INTO chat_messages (
                conversation_id, user_id, role, content, attachments
            )
            VALUES ($1, $2, 'user', $3, $4)
            RETURNING id, conversation_id, role, content, attachments, created_at
            """,
            conversation_id,
            user_id,
            content,
            attachments,
        )

        message_id = message_row["id"]

        # Update file records with message_id
        for attachment in attachments:
            await db.execute(
                "UPDATE chat_files SET message_id = $1 WHERE id = $2",
                message_id,
                uuid.UUID(attachment["id"]),
            )

        # Queue file processing tasks
        from worker.tasks import process_chat_file_task
        for attachment in attachments:
            process_chat_file_task.delay(attachment["id"], str(user_id))

    return ChatMessageModel(**dict(message_row))


@router.get("/files/{file_id}")
async def get_chat_file(
    file_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    """Download chat file."""
    from fastapi.responses import FileResponse
    from api.services.chat_file_service import ChatFileService

    service = ChatFileService(db)
    file_record = await service.get_file(file_id, user_id)

    if not file_record:
        raise HTTPException(404, "File not found")

    return FileResponse(
        path=file_record["storage_path"],
        filename=file_record["original_filename"],
        media_type=file_record["mime_type"],
    )


@router.get("/files/{file_id}/thumbnail")
async def get_chat_file_thumbnail(
    file_id: UUID,
    size: int = 200,
    user_id: UUID = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    """Get thumbnail for image files."""
    # TODO: Generate and cache thumbnails
    pass
```

---

## Phase 4: Worker Tasks (1 hour)

### Update: `app/worker/tasks.py`

Add file processing task:

```python
@celery_app.task(bind=True, max_retries=3)
def process_chat_file_task(self, file_id: str, user_id: str):
    """Process chat file attachment (OCR, transcription, embedding)."""
    import asyncio
    from api.services.chat_file_service import ChatFileService

    async def _process():
        async with get_db_connection() as db:
            service = ChatFileService(db)
            result = await service.process_file(
                uuid.UUID(file_id),
                uuid.UUID(user_id),
            )
            return result

    try:
        result = asyncio.run(_process())
        if not result["success"]:
            raise Exception(result["error"])
        return result
    except Exception as exc:
        logger.error("process_chat_file_failed", file_id=file_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60)
```

---

## Phase 5: Frontend - File Upload UI (3-4 hours)

### Update: `app/web/src/components/chat/ChatInput.tsx`

```typescript
import { useState, useRef, ChangeEvent } from 'react';
import { Send, Paperclip, X, Image, File } from 'lucide-react';
import './ChatInput.css';

interface AttachmentPreview {
  file: File;
  id: string;
  preview?: string;
  type: 'image' | 'document' | 'audio' | 'other';
}

interface ChatInputProps {
  onSendMessage: (message: string, files?: File[]) => void;
  disabled?: boolean;
}

export function ChatInput({ onSendMessage, disabled }: ChatInputProps) {
  const [message, setMessage] = useState('');
  const [attachments, setAttachments] = useState<AttachmentPreview[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const detectFileType = (file: File): AttachmentPreview['type'] => {
    if (file.type.startsWith('image/')) return 'image';
    if (file.type.startsWith('audio/')) return 'audio';
    if (file.type === 'application/pdf') return 'document';
    return 'other';
  };

  const handleFileSelect = (e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;

    const newAttachments: AttachmentPreview[] = [];

    Array.from(files).forEach((file) => {
      const type = detectFileType(file);
      const id = Math.random().toString(36).substring(7);

      // Create preview for images
      if (type === 'image') {
        const reader = new FileReader();
        reader.onload = (event) => {
          setAttachments((prev) =>
            prev.map((att) =>
              att.id === id ? { ...att, preview: event.target?.result as string } : att
            )
          );
        };
        reader.readAsDataURL(file);
      }

      newAttachments.push({ file, id, type });
    });

    setAttachments((prev) => [...prev, ...newAttachments]);

    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const removeAttachment = (id: string) => {
    setAttachments((prev) => prev.filter((att) => att.id !== id));
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if ((message.trim() || attachments.length > 0) && !disabled) {
      const files = attachments.map((att) => att.file);
      onSendMessage(message.trim(), files);
      setMessage('');
      setAttachments([]);

      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  };

  return (
    <form className="chat-input" onSubmit={handleSubmit}>
      {/* File previews */}
      {attachments.length > 0 && (
        <div className="chat-input__attachments">
          {attachments.map((att) => (
            <div key={att.id} className="chat-input__attachment">
              {att.type === 'image' && att.preview ? (
                <img src={att.preview} alt={att.file.name} className="attachment-preview" />
              ) : (
                <div className="attachment-icon">
                  {att.type === 'audio' ? '🎵' : '📄'}
                </div>
              )}
              <div className="attachment-info">
                <div className="attachment-name">{att.file.name}</div>
                <div className="attachment-size">
                  {(att.file.size / 1024).toFixed(1)} KB
                </div>
              </div>
              <button
                type="button"
                onClick={() => removeAttachment(att.id)}
                className="attachment-remove"
              >
                <X size={16} />
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="chat-input__wrapper">
        <textarea
          ref={textareaRef}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder={attachments.length > 0 ? "Add a message..." : "Ask me anything..."}
          disabled={disabled}
          className="chat-input__textarea"
          rows={1}
        />

        {/* File upload button */}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept="image/*,application/pdf,audio/*,.txt,.md,.doc,.docx"
          onChange={handleFileSelect}
          style={{ display: 'none' }}
        />
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          className="chat-input__attach-button"
          disabled={disabled}
          title="Attach files"
        >
          <Paperclip size={20} />
        </button>

        <button
          type="submit"
          disabled={disabled || (!message.trim() && attachments.length === 0)}
          className="chat-input__send-button"
        >
          <Send size={20} />
        </button>
      </div>
    </form>
  );
}
```

### CSS: `app/web/src/components/chat/ChatInput.css`

Add styles for attachments:

```css
.chat-input__attachments {
  display: flex;
  gap: 8px;
  padding: 12px;
  background: var(--background-secondary);
  border-top: 1px solid var(--border-color);
  overflow-x: auto;
}

.chat-input__attachment {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  min-width: 200px;
}

.attachment-preview {
  width: 48px;
  height: 48px;
  object-fit: cover;
  border-radius: 4px;
}

.attachment-icon {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--background-secondary);
  border-radius: 4px;
  font-size: 24px;
}

.attachment-info {
  flex: 1;
  min-width: 0;
}

.attachment-name {
  font-size: 14px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.attachment-size {
  font-size: 12px;
  color: var(--text-secondary);
}

.attachment-remove {
  padding: 4px;
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--text-secondary);
  border-radius: 4px;
}

.attachment-remove:hover {
  background: var(--background-hover);
  color: var(--text-primary);
}

.chat-input__attach-button {
  padding: 8px;
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--text-secondary);
  border-radius: 4px;
}

.chat-input__attach-button:hover {
  background: var(--background-hover);
  color: var(--text-primary);
}
```

---

## Phase 6: Frontend - Message Display (1 hour)

### Update: `app/web/src/components/chat/MessageList.tsx`

Display attachments in messages:

```typescript
{message.attachments && message.attachments.length > 0 && (
  <div className={styles.messageAttachments}>
    {message.attachments.map((attachment) => (
      <div key={attachment.id} className={styles.attachment}>
        {attachment.type === 'image' ? (
          <a href={attachment.url} target="_blank" rel="noopener noreferrer">
            <img
              src={attachment.url}
              alt={attachment.filename}
              className={styles.attachmentImage}
              loading="lazy"
            />
          </a>
        ) : (
          <a
            href={attachment.url}
            download={attachment.filename}
            className={styles.attachmentLink}
          >
            <span className={styles.attachmentIcon}>
              {attachment.type === 'audio' ? '🎵' : '📄'}
            </span>
            <div className={styles.attachmentInfo}>
              <div className={styles.attachmentFilename}>{attachment.filename}</div>
              <div className={styles.attachmentMeta}>
                {(attachment.size_bytes / 1024).toFixed(1)} KB
                {attachment.status === 'processing' && ' • Processing...'}
                {attachment.status === 'failed' && ' • Failed'}
              </div>
            </div>
          </a>
        )}
      </div>
    ))}
  </div>
)}
```

---

## Phase 7: Integration with RAG (30 mins)

When user sends message with files, include extracted text as context:

```python
# In chat flow
async def _dispatch_chat(message: str, user_id: UUID, db, model_id, attachments: List[dict]):
    # Build context from attachments
    attachment_context = []

    for attachment in attachments:
        if attachment.get("extracted_text"):
            attachment_context.append(
                f"[Attachment: {attachment['filename']}]\n{attachment['extracted_text'][:2000]}"
            )

    # Combine user message with attachment context
    full_message = message
    if attachment_context:
        full_message = f"{message}\n\n--- Attached Files ---\n" + "\n\n".join(attachment_context)

    # Send to RAG/LLM
    return await rag_service.answer_question(full_message, user_id)
```

---

## Testing Checklist

- [ ] Upload image → See preview
- [ ] Upload PDF → File appears in message
- [ ] Upload audio → Transcription triggers
- [ ] Upload multiple files → All show up
- [ ] Remove attachment before sending → File removed
- [ ] Send message with attachments → Files saved to DB
- [ ] Click image in message → Opens in new tab
- [ ] Download PDF from message → File downloads
- [ ] Ask question about uploaded image → OCR text used in context
- [ ] Ask question about uploaded PDF → Document content used in answer

---

## Performance Considerations

1. **File size limits**: Max 10MB per file, 50MB total per message
2. **Thumbnail generation**: Create thumbnails for images on upload
3. **Lazy loading**: Only load attachment content when message visible
4. **Compression**: Compress images before upload (frontend)
5. **Cleanup**: Delete orphaned files (files with no message_id after 1 hour)

---

## Security Considerations

1. **User isolation**: All file queries MUST filter by user_id
2. **Path validation**: Prevent directory traversal attacks
3. **MIME type validation**: Check actual file content, not just extension
4. **Virus scanning**: Consider integrating ClamAV for production
5. **Rate limiting**: Max 20 files per minute per user

---

## Estimated Total Time: 8-10 hours
