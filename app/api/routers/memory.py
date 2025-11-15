"""Memory router for OpenMemory integration."""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field, HttpUrl
import asyncpg

from api.services.memory_service import MemoryService
from api.services.openmemory_settings_service import OpenMemorySettingsService
from api.dependencies import get_current_user, get_db


router = APIRouter(prefix="/api/v1/memory", tags=["memory"])


class MemoryCreateRequest(BaseModel):
    """Request model for creating a memory.

    OpenMemory will automatically classify the content into appropriate sectors
    (semantic, episodic, procedural, emotional, reflective).
    """
    content: str
    tags: Optional[List[str]] = None
    metadata: Optional[dict] = None


class MemorySearchRequest(BaseModel):
    """Request model for searching memories.

    OpenMemory uses composite scoring: 0.6×similarity + 0.2×salience +
    0.1×recency + 0.1×link_weight
    """
    query: str
    limit: Optional[int] = 5
    min_score: Optional[float] = 0.5
    sectors: Optional[List[str]] = None  # Filter by sectors: semantic, episodic, procedural, emotional, reflective
    tags: Optional[List[str]] = None  # Filter by tags


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

    OpenMemory will automatically classify your content into appropriate sectors
    (semantic, episodic, procedural, emotional, reflective) and create multiple
    embeddings for multi-dimensional recall.

    Example:
        {
            "content": "User prefers dark mode for all applications",
            "tags": ["preference", "ui"],
            "metadata": {"category": "ui_settings"}
        }

    Response includes the assigned sectors:
        {
            "success": true,
            "data": {
                "id": "memory_uuid",
                "content": "User prefers dark mode...",
                "sectors": ["semantic", "procedural"],
                ...
            }
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
        tags=request.tags,
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
    """Search memories by semantic similarity with sector filtering.

    OpenMemory ranks results using composite scoring:
    - 60% similarity (semantic match)
    - 20% salience (importance)
    - 10% recency (how recent)
    - 10% link weight (connections to other memories)

    Example without sector filter:
        {
            "query": "What are the user's UI preferences?",
            "limit": 5,
            "min_score": 0.5
        }

    Example with sector filter (only search specific memory types):
        {
            "query": "How does the user prefer to work?",
            "limit": 5,
            "sectors": ["procedural", "semantic"],
            "tags": ["preference"]
        }

    Available sectors:
        - semantic: Facts and conceptual knowledge
        - episodic: Specific events and experiences
        - procedural: How-to knowledge and workflows
        - emotional: Emotional context and sentiment
        - reflective: Insights and meta-cognition

    Response includes sectors for each memory:
        {
            "success": true,
            "data": {
                "memories": [
                    {
                        "id": "...",
                        "content": "...",
                        "sectors": ["semantic", "procedural"],
                        "score": 0.85,
                        ...
                    }
                ]
            }
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
        sectors=request.sectors,
        tags=request.tags,
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


@router.post("/sync")
async def sync_to_vault(
    background_tasks: BackgroundTasks,
    user_id: UUID = Depends(get_current_user),
):
    """Sync OpenMemory contents to markdown files (memory vault).

    This creates a vault-like mirror of your OpenMemory contents in `/memory_vault`,
    organized by sector (semantic/, episodic/, procedural/, etc.).

    The sync runs in the background and creates:
    - Markdown files for each memory
    - Organization by primary sector
    - Index file with overview
    - Frontmatter with metadata

    Enable vault sync by setting:
        MEMORY_VAULT_SYNC_ENABLED=true
        MEMORY_VAULT_PATH=/memory_vault  # Optional, defaults to /memory_vault

    Response:
        {
            "success": true,
            "message": "Sync started in background",
            "vault_path": "/memory_vault/user-uuid"
        }
    """
    import os
    from worker.memory_sync import sync_memory_for_user

    enabled = os.getenv("MEMORY_VAULT_SYNC_ENABLED", "false").lower() == "true"
    vault_path = os.getenv("MEMORY_VAULT_PATH", "/memory_vault")

    if not enabled:
        raise HTTPException(
            status_code=503,
            detail="Memory vault sync is disabled. Set MEMORY_VAULT_SYNC_ENABLED=true to enable.",
        )

    service = MemoryService()
    if not service.is_enabled():
        raise HTTPException(
            status_code=503,
            detail="OpenMemory integration is disabled",
        )

    # Run sync in background
    background_tasks.add_task(sync_memory_for_user, str(user_id))

    return {
        "success": True,
        "message": "Memory vault sync started in background",
        "vault_path": f"{vault_path}/{user_id}",
    }


# OpenMemory Settings Management

class OpenMemorySettingsResponse(BaseModel):
    """Response model for OpenMemory settings."""
    enabled: bool
    server_url: Optional[str] = None
    api_key: Optional[str] = None
    auto_store_conversations: bool = True
    retention_days: int = Field(default=90, ge=1, le=3650)


class OpenMemorySettingsUpdate(BaseModel):
    """Request model for updating OpenMemory settings."""
    enabled: Optional[bool] = None
    server_url: Optional[str] = None
    api_key: Optional[str] = None
    auto_store_conversations: Optional[bool] = None
    retention_days: Optional[int] = Field(None, ge=1, le=3650)


@router.get("/settings", response_model=OpenMemorySettingsResponse)
async def get_openmemory_settings(
    user_id: UUID = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    """Get OpenMemory settings for the current user.

    Returns user-specific settings if they exist, otherwise returns global defaults
    from environment variables (OPENMEMORY_URL, OPENMEMORY_API_KEY, etc.).

    User-specific settings always override global environment settings when enabled.

    NOTE: Currently these settings are stored and retrieved, but MemoryService still
    uses global environment variables. Future enhancement: Update MemoryService to
    respect per-user settings when making OpenMemory API calls.

    Response:
        {
            "enabled": true,
            "server_url": "http://localhost:8080",
            "api_key": "user_api_key",
            "auto_store_conversations": true,
            "retention_days": 90
        }
    """
    settings_service = OpenMemorySettingsService(db)

    try:
        settings = await settings_service.get_user_settings(user_id)
        return OpenMemorySettingsResponse(**settings)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve OpenMemory settings: {str(exc)}",
        ) from exc


@router.put("/settings", response_model=OpenMemorySettingsResponse)
async def update_openmemory_settings(
    payload: OpenMemorySettingsUpdate,
    user_id: UUID = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    """Update OpenMemory settings for the current user.

    This allows users to override global OpenMemory settings with their own configuration.
    All fields are optional - only provided fields will be updated.

    Example request:
        {
            "enabled": true,
            "server_url": "http://my-openmemory.example.com",
            "api_key": "my_secret_key",
            "auto_store_conversations": true,
            "retention_days": 365
        }

    Security:
        - API keys are encrypted using Fernet before storage
        - User settings are isolated by user_id (one user cannot access another's settings)

    Response includes the updated settings (with decrypted API key for display).
    """
    settings_service = OpenMemorySettingsService(db)

    try:
        updated_settings = await settings_service.update_user_settings(
            user_id=user_id,
            enabled=payload.enabled,
            server_url=payload.server_url,
            api_key=payload.api_key,
            auto_store_conversations=payload.auto_store_conversations,
            retention_days=payload.retention_days,
        )
        return OpenMemorySettingsResponse(**updated_settings)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update OpenMemory settings: {str(exc)}",
        ) from exc
