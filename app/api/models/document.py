from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, validator


class DocumentUpload(BaseModel):
    """Schema for inbound upload metadata."""

    filename: str
    mime_type: str
    size_bytes: int

    @validator("size_bytes")
    def validate_size(cls, value: int) -> int:
        max_size = 50 * 1024 * 1024  # 50MB
        if value > max_size:
            raise ValueError(f"File size {value} exceeds maximum {max_size}")
        return value

    @validator("mime_type")
    def validate_mime(cls, value: str) -> str:
        allowed = {
            "application/pdf",
            "text/markdown",
            "text/plain",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        }
        if value not in allowed:
            raise ValueError(f"Unsupported file type: {value}")
        return value


class DocumentResponse(BaseModel):
    id: UUID
    user_id: UUID
    filename: str
    source: Optional[str]
    storage_path: str
    mime_type: Optional[str]
    sha256: Optional[str]
    size_bytes: Optional[int]
    status: str
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime


class ChunkResponse(BaseModel):
    id: UUID
    document_id: UUID
    ordinal: int
    text: str
    tokens: Optional[int]
    metadata: Dict[str, Any]
    created_at: datetime


class JobResponse(BaseModel):
    id: UUID
    user_id: Optional[UUID]
    type: str
    status: str
    payload: Optional[Dict[str, Any]]
    result: Optional[Dict[str, Any]]
    error_message: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]


class SearchResult(BaseModel):
    id: str
    content_type: str
    title: str
    excerpt: str
    score: float
    payload: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any]


class SearchResponse(BaseModel):
    results: List[SearchResult]
    query: str
    total: int


class Citation(BaseModel):
    type: str
    id: str
    title: str
    chunk_index: Optional[int] = None
    location: Optional[str] = None
    excerpt: str


class RAGResponse(BaseModel):
    answer: str
    citations: List[Citation]
    sources_used: int
