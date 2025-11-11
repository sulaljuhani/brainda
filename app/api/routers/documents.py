import os
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from api.dependencies import get_current_user, get_db
from api.metrics import celery_queue_depth
from api.models.document import (
    ChunkResponse,
    DocumentResponse,
    DocumentUpload,
    JobResponse,
)
from api.services.document_service import DocumentService, JobService

router = APIRouter(prefix="/api/v1", tags=["documents"])


@router.post("/ingest")
async def ingest_document(
    file: UploadFile = File(...),
    user_id: UUID = Depends(get_current_user),
    db=Depends(get_db),
):
    content = await file.read()
    try:
        upload_meta = DocumentUpload(
            filename=file.filename,
            mime_type=file.content_type or "application/octet-stream",
            size_bytes=len(content),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    storage_root = os.getenv("UPLOADS_PATH", "/app/uploads")
    doc_service = DocumentService(db, storage_root)
    result = await doc_service.create_document(
        user_id,
        upload_meta.filename,
        content,
        upload_meta.mime_type,
    )

    if result.get("deduplicated"):
        return {
            "success": True,
            "deduplicated": True,
            "document_id": result["data"]["id"],
            "message": result["data"].get("message", "Document already ingested"),
        }

    job_service = JobService(db)
    job = await job_service.create_job(
        user_id,
        "embed_document",
        {"document_id": str(result["data"]["id"])},
    )

    from worker.tasks import process_document_ingestion

    process_document_ingestion.delay(str(job["id"]))
    celery_queue_depth.labels(queue_name="document_ingest").inc()

    return {
        "success": True,
        "job_id": job["id"],
        "document_id": result["data"]["id"],
        "status": "pending",
    }


@router.get("/documents", response_model=List[DocumentResponse])
async def list_documents(
    status: Optional[str] = None,
    limit: int = 50,
    cursor: Optional[UUID] = None,
    user_id: UUID = Depends(get_current_user),
    db=Depends(get_db),
):
    service = DocumentService(db, os.getenv("UPLOADS_PATH", "/app/uploads"))
    return await service.list_documents(user_id, status, limit, cursor)


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db=Depends(get_db),
):
    service = DocumentService(db, os.getenv("UPLOADS_PATH", "/app/uploads"))
    document = await service.get_document(document_id, user_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db=Depends(get_db),
):
    service = DocumentService(db, os.getenv("UPLOADS_PATH", "/app/uploads"))
    success = await service.delete_document(document_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"success": True, "message": "Document deleted"}


@router.get("/documents/{document_id}/chunks", response_model=List[ChunkResponse])
async def get_document_chunks(
    document_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db=Depends(get_db),
):
    service = DocumentService(db, os.getenv("UPLOADS_PATH", "/app/uploads"))
    return await service.get_chunks(document_id, user_id)


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job_status(
    job_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db=Depends(get_db),
):
    service = JobService(db)
    job = await service.get_job(job_id, user_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
