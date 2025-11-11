import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import structlog
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from api.metrics import (
    chunks_created_total,
    embedding_duration_seconds,
    vector_search_duration_seconds,
)
from api.services.embedding_service import EmbeddingService

logger = structlog.get_logger()


class VectorService:
    """Shared access to the unified Qdrant collection."""

    def __init__(self, embedding_service: Optional[EmbeddingService] = None):
        self.collection_name = os.getenv("QDRANT_COLLECTION", "knowledge_base")
        self.client = QdrantClient(url=os.getenv("QDRANT_URL"))
        self.embedding_service = embedding_service or EmbeddingService()
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        """Ensure the vector collection exists with proper error handling."""
        try:
            # Get existing collections
            collections_response = self.client.get_collections()
            existing_collections = [c.name for c in collections_response.collections]

            # Check if collection already exists
            if self.collection_name in existing_collections:
                logger.info("vector_collection_exists", name=self.collection_name)
                return

            # Import here to avoid circular dependencies
            from qdrant_client.http.models import Distance, VectorParams

            # Create the collection
            logger.info("creating_vector_collection", name=self.collection_name)
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )
            logger.info("vector_collection_created", name=self.collection_name)

            # Verify collection was created
            collections_response = self.client.get_collections()
            existing_collections = [c.name for c in collections_response.collections]
            if self.collection_name not in existing_collections:
                logger.error("vector_collection_verification_failed", name=self.collection_name)
                raise RuntimeError(f"Failed to create or verify collection: {self.collection_name}")

        except Exception as e:
            logger.error("vector_collection_error", name=self.collection_name, error=str(e))
            raise

    async def upsert_document_chunks(
        self,
        document_id: UUID,
        user_id: UUID,
        chunks: List[Dict[str, Any]],
        document_title: str,
    ) -> None:
        texts = [chunk["text"] for chunk in chunks]
        with embedding_duration_seconds.labels(source_type="document").time():
            embeddings = await self.embedding_service.embed_batch(texts)

        points = []
        now = datetime.utcnow().isoformat() + "Z"
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            payload = {
                "embedding_model": self.embedding_service.model_name,
                "content_type": "document_chunk",
                "source_id": str(document_id),
                "title": document_title,
                "user_id": str(user_id),
                "chunk_index": idx,
                "parent_document_id": str(document_id),
                "text": chunk["text"],
                "tokens": chunk.get("tokens"),
                "page": (chunk.get("metadata") or {}).get("page"),
                "created_at": now,
                "embedded_at": now,
            }
            points.append(
                qmodels.PointStruct(id=str(uuid4()), vector=embedding, payload=payload)
            )

        self.client.upsert(collection_name=self.collection_name, points=points)
        chunks_created_total.labels(source_type="document").inc(len(points))
        logger.info(
            "chunks_embedded",
            document_id=str(document_id),
            chunk_count=len(points),
            collection=self.collection_name,
        )

    async def search(
        self,
        query: str,
        user_id: UUID,
        content_type: Optional[str] = None,
        limit: int = 10,
        min_score: float = 0.1,
    ) -> List[Dict[str, Any]]:
        query_embedding = await self.embedding_service.embed(query)
        must_conditions = [
            qmodels.FieldCondition(
                key="user_id", match=qmodels.MatchValue(value=str(user_id))
            )
        ]
        if content_type:
            must_conditions.append(
                qmodels.FieldCondition(
                    key="content_type",
                    match=qmodels.MatchValue(value=content_type),
                )
            )

        query_filter = qmodels.Filter(must=must_conditions)

        with vector_search_duration_seconds.time():
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                query_filter=query_filter,
                limit=limit,
                score_threshold=min_score,
            )

        formatted = []
        for res in results:
            excerpt = (res.payload.get("text") or "")[:200]
            formatted.append(
                {
                    "id": res.payload.get("source_id"),
                    "content_type": res.payload.get("content_type"),
                    "title": res.payload.get("title"),
                    "excerpt": excerpt + ("..." if len(excerpt) == 200 else ""),
                    "score": res.score,
                    "payload": {
                        "user_id": res.payload.get("user_id"),
                    },
                    "metadata": {
                        "chunk_index": res.payload.get("chunk_index"),
                        "page": res.payload.get("page"),
                        "parent_document_id": res.payload.get(
                            "parent_document_id"
                        ),
                        "created_at": res.payload.get("created_at"),
                    },
                }
            )
        return formatted

    async def delete_document(self, document_id: UUID) -> None:
        selector = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="parent_document_id",
                    match=qmodels.MatchValue(value=str(document_id)),
                )
            ]
        )
        self.client.delete(collection_name=self.collection_name, points_selector=selector)
        logger.info("document_vectors_deleted", document_id=str(document_id))
