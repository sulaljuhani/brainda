"""Speech-to-text transcription endpoints."""
import os
import time
import uuid
from typing import Optional

from fastapi import APIRouter, File, UploadFile, Depends, HTTPException, Form
from pydantic import BaseModel
import structlog

from api.dependencies import get_current_user, get_db

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/transcribe", tags=["transcribe"])


class TranscriptionResponse(BaseModel):
    """Transcription result."""
    text: str
    language: str
    duration: float
    segments: list
    status: str = "completed"


class TranscriptionTask(BaseModel):
    """Async transcription task."""
    task_id: str
    status: str  # pending, processing, completed, failed
    text: Optional[str] = None
    error: Optional[str] = None


@router.post("", response_model=TranscriptionResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    wait: bool = Form(True),  # Wait for result or return task_id
    user_id: uuid.UUID = Depends(get_current_user),
):
    """
    Transcribe audio file using local Whisper model.

    Supported formats: mp3, wav, m4a, webm, ogg, flac
    Max file size: 25MB
    Max duration: 10 minutes
    """

    # Validate content type
    allowed_types = [
        "audio/mpeg", "audio/mp3",
        "audio/wav", "audio/wave",
        "audio/m4a", "audio/mp4",
        "audio/webm",
        "audio/ogg",
        "audio/flac",
    ]

    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio format: {file.content_type}. "
                   f"Supported: mp3, wav, m4a, webm, ogg, flac"
        )

    # Read file content
    content = await file.read()

    # Validate file size (max 25MB)
    max_size = 25 * 1024 * 1024  # 25MB
    if len(content) > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {len(content)} bytes. Max: {max_size} bytes (25MB)"
        )

    # Save to temporary file
    ext = os.path.splitext(file.filename)[1] or ".webm"
    temp_filename = f"audio_{user_id}_{int(time.time())}_{uuid.uuid4().hex[:8]}{ext}"
    temp_path = f"/tmp/{temp_filename}"

    with open(temp_path, "wb") as f:
        f.write(content)

    logger.info(
        "transcribe_audio_request",
        user_id=str(user_id),
        filename=file.filename,
        size_bytes=len(content),
        language=language,
    )

    # Queue transcription task
    from worker.tasks import transcribe_audio_task

    task = transcribe_audio_task.delay(temp_path, language)

    # If wait=False, return task ID immediately
    if not wait:
        return TranscriptionTask(
            task_id=task.id,
            status="processing",
        )

    # Wait for result (with timeout)
    try:
        result = task.get(timeout=120)  # 2 minute timeout

        return TranscriptionResponse(
            text=result["text"],
            language=result["language"],
            duration=result["duration"],
            segments=result["segments"],
            status="completed",
        )

    except Exception as exc:
        logger.error("transcribe_audio_timeout", task_id=task.id, error=str(exc))

        # Return task ID for polling
        raise HTTPException(
            status_code=202,
            detail={
                "message": "Transcription is taking longer than expected. Use the task_id to check status.",
                "task_id": task.id,
            }
        )


@router.get("/tasks/{task_id}", response_model=TranscriptionTask)
async def get_transcription_task(
    task_id: str,
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Check status of async transcription task."""
    from celery.result import AsyncResult

    task = AsyncResult(task_id)

    if task.ready():
        if task.successful():
            result = task.result
            return TranscriptionTask(
                task_id=task_id,
                status="completed",
                text=result["text"],
            )
        else:
            return TranscriptionTask(
                task_id=task_id,
                status="failed",
                error=str(task.info),
            )

    return TranscriptionTask(
        task_id=task_id,
        status="processing",
    )
