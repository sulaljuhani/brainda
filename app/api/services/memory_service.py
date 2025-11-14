"""Memory service for managing OpenMemory integration."""

import os
from typing import Dict, List, Optional, Any
from uuid import UUID

import structlog

from api.adapters.openmemory_adapter import OpenMemoryAdapter, OpenMemoryError

logger = structlog.get_logger()


class MemoryService:
    """Service for managing long-term AI memory using OpenMemory."""

    def __init__(self, openmemory_adapter: Optional[OpenMemoryAdapter] = None):
        """Initialize memory service.

        Args:
            openmemory_adapter: OpenMemory adapter instance (defaults to new instance)
        """
        self.adapter = openmemory_adapter or OpenMemoryAdapter()
        self.enabled = os.getenv("OPENMEMORY_ENABLED", "true").lower() == "true"

    def is_enabled(self) -> bool:
        """Check if OpenMemory integration is enabled."""
        return self.enabled

    async def store_conversation(
        self,
        user_id: UUID,
        user_message: str,
        assistant_message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Store a conversation turn in OpenMemory.

        Args:
            user_id: User identifier
            user_message: User's message
            assistant_message: Assistant's response
            metadata: Additional context (sources, query type, etc.)

        Returns:
            Created memory object or None if disabled/failed
        """
        if not self.enabled:
            logger.debug("openmemory_disabled_skipping_storage")
            return None

        try:
            memory = await self.adapter.store_conversation_turn(
                user_id=user_id,
                user_message=user_message,
                assistant_message=assistant_message,
                metadata=metadata,
            )
            logger.info(
                "conversation_stored_in_openmemory",
                user_id=str(user_id),
                memory_id=memory.get("id"),
            )
            return memory
        except OpenMemoryError as e:
            logger.warning(
                "failed_to_store_conversation_in_openmemory",
                user_id=str(user_id),
                error=str(e),
            )
            return None

    async def get_conversation_context(
        self,
        user_id: UUID,
        current_query: str,
        max_memories: int = 10,
    ) -> str:
        """Retrieve relevant conversation context from OpenMemory.

        Args:
            user_id: User identifier
            current_query: Current user query for semantic search
            max_memories: Maximum number of memories to retrieve

        Returns:
            Formatted context string for LLM prompting (empty if disabled/failed)
        """
        if not self.enabled:
            return ""

        try:
            context = await self.adapter.get_conversation_context(
                user_id=user_id,
                query=current_query,
                max_memories=max_memories,
            )
            logger.info(
                "retrieved_conversation_context",
                user_id=str(user_id),
                context_length=len(context),
            )
            return context
        except OpenMemoryError as e:
            logger.warning(
                "failed_to_retrieve_conversation_context",
                user_id=str(user_id),
                error=str(e),
            )
            return ""

    async def store_memory(
        self,
        user_id: UUID,
        content: str,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Store a generic memory.

        OpenMemory will automatically determine which sectors (semantic, episodic,
        procedural, emotional, reflective) apply to this memory.

        Args:
            user_id: User identifier
            content: Memory content
            tags: Optional tags for categorization (e.g., ["fact", "project-alpha"])
            metadata: Additional metadata

        Returns:
            Created memory object with assigned sectors, or None if disabled/failed
            Example: {"id": "...", "sectors": ["semantic", "procedural"], ...}
        """
        if not self.enabled:
            return None

        try:
            memory = await self.adapter.store_memory(
                user_id=user_id,
                content=content,
                metadata=metadata,
                tags=tags,
            )
            logger.info(
                "memory_stored_in_openmemory",
                user_id=str(user_id),
                tags=tags,
                memory_id=memory.get("id"),
                sectors=memory.get("sectors", []),
            )
            return memory
        except OpenMemoryError as e:
            logger.warning(
                "failed_to_store_memory",
                user_id=str(user_id),
                error=str(e),
            )
            return None

    async def search_memories(
        self,
        user_id: UUID,
        query: str,
        limit: int = 5,
        min_score: float = 0.5,
        sectors: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Search memories by semantic similarity.

        OpenMemory ranks results using: 0.6×similarity + 0.2×salience +
        0.1×recency + 0.1×link_weight

        Args:
            user_id: User identifier
            query: Search query
            limit: Maximum results
            min_score: Minimum similarity threshold
            sectors: Filter by specific sectors (e.g., ["semantic", "procedural"])
                    Available: semantic, episodic, procedural, emotional, reflective
            tags: Filter by tags

        Returns:
            List of matching memories with sectors field (empty if disabled/failed)
            Example: [{"id": "...", "content": "...", "sectors": ["semantic"], ...}, ...]
        """
        if not self.enabled:
            return []

        try:
            memories = await self.adapter.search_memories(
                user_id=user_id,
                query=query,
                limit=limit,
                min_score=min_score,
                sectors=sectors,
                tags=tags,
            )
            logger.info(
                "searched_memories",
                user_id=str(user_id),
                results_count=len(memories),
                sector_filter=sectors,
            )
            return memories
        except OpenMemoryError as e:
            logger.warning(
                "failed_to_search_memories",
                user_id=str(user_id),
                error=str(e),
            )
            return []

    async def get_user_memories(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get all memories for a user (paginated).

        Args:
            user_id: User identifier
            limit: Maximum memories per page
            offset: Pagination offset

        Returns:
            List of memories (empty if disabled/failed)
        """
        if not self.enabled:
            return []

        try:
            memories = await self.adapter.get_user_memories(
                user_id=user_id,
                limit=limit,
                offset=offset,
            )
            logger.info(
                "retrieved_user_memories",
                user_id=str(user_id),
                count=len(memories),
            )
            return memories
        except OpenMemoryError as e:
            logger.warning(
                "failed_to_retrieve_user_memories",
                user_id=str(user_id),
                error=str(e),
            )
            return []

    async def delete_memory(
        self,
        user_id: UUID,
        memory_id: str,
    ) -> bool:
        """Delete a specific memory.

        Args:
            user_id: User identifier
            memory_id: Memory ID to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        if not self.enabled:
            return False

        try:
            await self.adapter.delete_memory(
                user_id=user_id,
                memory_id=memory_id,
            )
            logger.info(
                "memory_deleted",
                user_id=str(user_id),
                memory_id=memory_id,
            )
            return True
        except OpenMemoryError as e:
            logger.warning(
                "failed_to_delete_memory",
                user_id=str(user_id),
                memory_id=memory_id,
                error=str(e),
            )
            return False

    async def health_check(self) -> Dict[str, Any]:
        """Check OpenMemory service health.

        Returns:
            Health status dictionary
        """
        if not self.enabled:
            return {
                "enabled": False,
                "status": "disabled",
                "message": "OpenMemory integration is disabled",
            }

        try:
            is_healthy = await self.adapter.health_check()
            return {
                "enabled": True,
                "status": "healthy" if is_healthy else "unhealthy",
                "url": self.adapter.base_url,
            }
        except Exception as e:
            logger.error("openmemory_health_check_failed", error=str(e))
            return {
                "enabled": True,
                "status": "error",
                "error": str(e),
            }

    async def close(self):
        """Close adapter connections."""
        await self.adapter.close()
