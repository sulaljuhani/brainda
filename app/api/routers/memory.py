"""Memory router for OpenMemory integration."""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel

from api.services.memory_service import MemoryService
from api.dependencies import get_current_user


router = APIRouter(prefix="/api/v1/memory", tags=["memory"])


class MemoryCreateRequest(BaseModel):
    """Request model for creating a memory."""
    content: str
    memory_type: Optional[str] = "fact"
    metadata: Optional[dict] = None


class MemorySearchRequest(BaseModel):
    """Request model for searching memories."""
    query: str
    limit: Optional[int] = 5
    min_score: Optional[float] = 0.5
    memory_type: Optional[str] = None


class MemoryResponse(BaseModel):
    """Response model for memory operations."""
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None


@router.get("/health")
async def memory_health(
    user_id: UUID = Depends(get_current_user),
):
    """Check OpenMemory service health."""
    service = MemoryService()
    health_status = await service.health_check()
    return health_status


@router.post("", response_model=MemoryResponse)
async def store_memory(
    request: MemoryCreateRequest,
    user_id: UUID = Depends(get_current_user),
):
    """Store a new memory in OpenMemory.

    This endpoint allows you to explicitly store facts, events, or other
    information that should be remembered for future conversations.

    Example:
        {
            "content": "User prefers dark mode for all applications",
            "memory_type": "preference",
            "metadata": {"category": "ui_settings"}
        }
    """
    service = MemoryService()

    if not service.is_enabled():
        raise HTTPException(
            status_code=503,
            detail="OpenMemory integration is disabled. Set OPENMEMORY_ENABLED=true to enable.",
        )

    memory = await service.store_memory(
        user_id=user_id,
        content=request.content,
        memory_type=request.memory_type,
        metadata=request.metadata,
    )

    if not memory:
        raise HTTPException(
            status_code=500,
            detail="Failed to store memory in OpenMemory",
        )

    return MemoryResponse(success=True, data=memory)


@router.post("/search")
async def search_memories(
    request: MemorySearchRequest,
    user_id: UUID = Depends(get_current_user),
):
    """Search memories by semantic similarity.

    This endpoint searches through stored memories to find relevant information
    based on the query. Results are ranked by similarity score.

    Example:
        {
            "query": "What are the user's UI preferences?",
            "limit": 5,
            "min_score": 0.5,
            "memory_type": "preference"
        }
    """
    service = MemoryService()

    if not service.is_enabled():
        raise HTTPException(
            status_code=503,
            detail="OpenMemory integration is disabled",
        )

    memories = await service.search_memories(
        user_id=user_id,
        query=request.query,
        limit=request.limit,
        min_score=request.min_score,
        memory_type=request.memory_type,
    )

    return {
        "success": True,
        "data": {
            "memories": memories,
            "count": len(memories),
        },
    }


@router.get("")
async def list_memories(
    limit: int = 50,
    offset: int = 0,
    user_id: UUID = Depends(get_current_user),
):
    """Get all memories for the current user (paginated).

    Returns memories in chronological order, most recent first.

    Query parameters:
        - limit: Maximum memories per page (default: 50)
        - offset: Number of memories to skip (default: 0)
    """
    service = MemoryService()

    if not service.is_enabled():
        raise HTTPException(
            status_code=503,
            detail="OpenMemory integration is disabled",
        )

    memories = await service.get_user_memories(
        user_id=user_id,
        limit=limit,
        offset=offset,
    )

    return {
        "success": True,
        "data": {
            "memories": memories,
            "count": len(memories),
            "limit": limit,
            "offset": offset,
        },
    }


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: str,
    user_id: UUID = Depends(get_current_user),
):
    """Delete a specific memory.

    This permanently removes a memory from OpenMemory storage.

    Path parameters:
        - memory_id: The ID of the memory to delete
    """
    service = MemoryService()

    if not service.is_enabled():
        raise HTTPException(
            status_code=503,
            detail="OpenMemory integration is disabled",
        )

    success = await service.delete_memory(
        user_id=user_id,
        memory_id=memory_id,
    )

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Memory {memory_id} not found or could not be deleted",
        )

    return {
        "success": True,
        "message": f"Memory {memory_id} deleted successfully",
    }


@router.get("/context/preview")
async def preview_conversation_context(
    query: str,
    max_memories: int = 10,
    user_id: UUID = Depends(get_current_user),
):
    """Preview conversation context that would be retrieved for a query.

    This is useful for debugging and understanding what context OpenMemory
    would provide for a given query in the chat endpoint.

    Query parameters:
        - query: The query to search for relevant memories
        - max_memories: Maximum memories to include (default: 10)
    """
    service = MemoryService()

    if not service.is_enabled():
        raise HTTPException(
            status_code=503,
            detail="OpenMemory integration is disabled",
        )

    context = await service.get_conversation_context(
        user_id=user_id,
        current_query=query,
        max_memories=max_memories,
    )

    return {
        "success": True,
        "data": {
            "query": query,
            "context": context,
            "context_length": len(context),
        },
    }
