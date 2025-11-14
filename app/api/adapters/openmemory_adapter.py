"""OpenMemory adapter for long-term AI memory integration."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx
import structlog
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = structlog.get_logger()


class OpenMemoryError(RuntimeError):
    """Raised when OpenMemory API request fails."""


class OpenMemoryAdapter:
    """Client adapter for interacting with OpenMemory API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 30,
        retry_attempts: int = 3,
    ):
        """Initialize OpenMemory adapter.

        Args:
            base_url: OpenMemory server URL (defaults to OPENMEMORY_URL env var)
            api_key: API key for authentication (defaults to OPENMEMORY_API_KEY env var)
            timeout: Request timeout in seconds
            retry_attempts: Number of retry attempts for failed requests
        """
        self.base_url = (base_url or os.getenv("OPENMEMORY_URL", "http://localhost:8080")).rstrip("/")
        self.api_key = api_key or os.getenv("OPENMEMORY_API_KEY", "")
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=self.timeout,
            )
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Make HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            **kwargs: Additional request parameters

        Returns:
            JSON response data

        Raises:
            OpenMemoryError: If request fails after retries
        """
        client = await self._get_client()

        try:
            async for attempt in AsyncRetrying(
                retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
                stop=stop_after_attempt(self.retry_attempts),
                wait=wait_exponential(multiplier=1, min=1, max=10),
                reraise=True,
            ):
                with attempt:
                    response = await client.request(method, endpoint, **kwargs)
                    response.raise_for_status()
                    return response.json()
        except (RetryError, httpx.HTTPError) as e:
            logger.error(
                "openmemory_request_failed",
                method=method,
                endpoint=endpoint,
                error=str(e),
            )
            raise OpenMemoryError(f"OpenMemory request failed: {e}") from e

    async def store_memory(
        self,
        user_id: UUID,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Store a new memory in OpenMemory.

        OpenMemory automatically determines which sectors (semantic, episodic,
        procedural, emotional, reflective) apply to the content.

        Args:
            user_id: User identifier for memory isolation
            content: Memory content to store
            metadata: Additional metadata (e.g., source, timestamp)
            tags: Optional tags for categorization

        Returns:
            Created memory object with ID, sectors, and embeddings
            Example: {"id": "...", "sectors": ["semantic", "procedural"], ...}
        """
        payload = {
            "user_id": str(user_id),
            "content": content,
            "tags": tags or [],
            "metadata": metadata or {},
        }

        logger.info(
            "storing_openmemory",
            user_id=str(user_id),
            content_preview=content[:100],
            tags=tags,
        )

        result = await self._request("POST", "/memory/add", json=payload)

        # Log which sectors were assigned
        if "sectors" in result:
            logger.info(
                "openmemory_sectors_assigned",
                user_id=str(user_id),
                sectors=result["sectors"],
            )

        return result

    async def search_memories(
        self,
        user_id: UUID,
        query: str,
        limit: int = 5,
        min_score: float = 0.5,
        sectors: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Search memories using semantic similarity.

        OpenMemory uses composite scoring: 0.6Ã—similarity + 0.2Ã—salience +
        0.1Ã—recency + 0.1Ã—link_weight

        Args:
            user_id: User identifier for memory isolation
            query: Search query text
            limit: Maximum number of results (k parameter in OpenMemory)
            min_score: Minimum similarity score threshold
            sectors: Filter by specific sectors (e.g., ["semantic", "procedural"])
                    Available: semantic, episodic, procedural, emotional, reflective
            tags: Filter by tags

        Returns:
            List of memory objects sorted by relevance, each with sectors field
            Example: [{"id": "...", "content": "...", "sectors": ["semantic"], "score": 0.85}, ...]
        """
        payload = {
            "user_id": str(user_id),
            "query": query,
            "k": limit,
        }

        # Add filters if specified
        filters = {}
        if sectors:
            filters["sectors"] = sectors
        if tags:
            filters["tags"] = tags

        if filters:
            payload["filters"] = filters

        logger.info(
            "searching_openmemory",
            user_id=str(user_id),
            query_preview=query[:100],
            limit=limit,
            sector_filters=sectors,
        )

        result = await self._request("POST", "/memory/query", json=payload)
        memories = result.get("memories", [])

        # Log sector distribution in results
        if memories:
            all_sectors = []
            for mem in memories:
                all_sectors.extend(mem.get("sectors", []))
            logger.info(
                "openmemory_search_results",
                user_id=str(user_id),
                result_count=len(memories),
                sectors_found=list(set(all_sectors)),
            )

        return memories

    async def get_conversation_context(
        self,
        user_id: UUID,
        query: str,
        max_memories: int = 10,
    ) -> str:
        """Get formatted conversation context from relevant memories.

        Args:
            user_id: User identifier
            query: Current user query
            max_memories: Maximum memories to include

        Returns:
            Formatted context string for LLM prompting
        """
        memories = await self.search_memories(
            user_id=user_id,
            query=query,
            limit=max_memories,
            min_score=0.3,
            tags=["conversation"],
        )

        if not memories:
            return ""

        context_parts = []
        for idx, memory in enumerate(memories, start=1):
            timestamp = memory.get("timestamp", "")
            content = memory.get("content", "")
            score = memory.get("score", 0.0)

            context_parts.append(
                f"[Memory {idx}] (relevance: {score:.2f}, time: {timestamp})\n{content}"
            )

        return "\n\n".join(context_parts)

    async def store_conversation_turn(
        self,
        user_id: UUID,
        user_message: str,
        assistant_message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Store a conversation turn (user + assistant exchange).

        OpenMemory will automatically classify this into appropriate sectors
        (typically episodic for the interaction, semantic for facts mentioned).

        Args:
            user_id: User identifier
            user_message: User's message
            assistant_message: Assistant's response
            metadata: Additional context (e.g., sources used, query type)

        Returns:
            Created memory object with assigned sectors
        """
        conversation_content = f"User: {user_message}\n\nAssistant: {assistant_message}"

        combined_metadata = metadata or {}
        combined_metadata.update({
            "user_message": user_message,
            "assistant_message": assistant_message,
            "interaction_type": "chat",
        })

        return await self.store_memory(
            user_id=user_id,
            content=conversation_content,
            metadata=combined_metadata,
            tags=["conversation", "chat"],
        )

    async def get_user_memories(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get all memories for a user (chronological).

        Args:
            user_id: User identifier
            limit: Maximum number of memories
            offset: Pagination offset

        Returns:
            List of memory objects
        """
        params = {
            "user_id": str(user_id),
            "limit": limit,
            "offset": offset,
        }

        result = await self._request("GET", "/api/memory", params=params)
        return result.get("memories", [])

    async def delete_memory(
        self,
        user_id: UUID,
        memory_id: str,
    ) -> bool:
        """Delete a specific memory.

        Args:
            user_id: User identifier (for authorization)
            memory_id: Memory ID to delete

        Returns:
            True if deleted successfully
        """
        logger.info(
            "deleting_openmemory",
            user_id=str(user_id),
            memory_id=memory_id,
        )

        await self._request(
            "DELETE",
            f"/api/memory/{memory_id}",
            params={"user_id": str(user_id)},
        )
        return True

    async def store_temporal_fact(
        self,
        user_id: UUID,
        fact: str,
        valid_from: Optional[str] = None,
        valid_until: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Store a temporal fact with validity period.

        Args:
            user_id: User identifier
            fact: Fact content
            valid_from: ISO8601 timestamp when fact becomes valid
            valid_until: ISO8601 timestamp when fact expires
            metadata: Additional metadata

        Returns:
            Created temporal fact object
        """
        payload = {
            "user_id": str(user_id),
            "fact": fact,
            "metadata": metadata or {},
        }

        if valid_from:
            payload["valid_from"] = valid_from
        if valid_until:
            payload["valid_until"] = valid_until

        logger.info(
            "storing_temporal_fact",
            user_id=str(user_id),
            fact_preview=fact[:100],
        )

        result = await self._request("POST", "/api/temporal/fact", json=payload)
        return result

    async def health_check(self) -> bool:
        """Check if OpenMemory server is healthy.

        Returns:
            True if server is responsive
        """
        try:
            await self._request("GET", "/health")
            return True
        except OpenMemoryError:
            return False


def get_openmemory_adapter() -> OpenMemoryAdapter:
    """Get OpenMemory adapter instance (singleton pattern).

    Returns:
        OpenMemoryAdapter instance configured from environment variables
    """
    return OpenMemoryAdapter()

