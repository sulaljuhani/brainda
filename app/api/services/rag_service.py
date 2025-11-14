from typing import List, Optional
from uuid import UUID

import structlog

from api.metrics import rag_queries_total
from api.services.vector_service import VectorService

logger = structlog.get_logger()


class RAGService:
    """Answer questions using retrieved chunks with citation payloads."""

    def __init__(self, vector_service: VectorService, llm_adapter):
        self.vector_service = vector_service
        self.llm_adapter = llm_adapter

    async def answer_question(
        self,
        query: str,
        user_id: UUID,
        content_type: Optional[str] = None,
        max_sources: int = 5,
    ) -> dict:
        results = await self.vector_service.search(
            query=query,
            user_id=user_id,
            content_type=content_type,
            limit=max_sources,
            min_score=0.1,
        )

        rag_queries_total.inc()

        if not results:
            return {
                "answer": "I couldn't find any relevant information to answer your question.",
                "citations": [],
                "sources_used": 0,
            }

        context_parts: List[str] = []
        citations: List[dict] = []
        for idx, result in enumerate(results, start=1):
            context_parts.append(f"[Source {idx}] {result['excerpt']}")
            citation = {
                "type": result["content_type"].replace("_chunk", ""),
                "id": str(result["id"]),
                "title": result["title"],
                "excerpt": result["excerpt"][:150] + "...",
            }
            chunk_index = result["metadata"].get("chunk_index")
            if chunk_index is not None:
                citation["chunk_index"] = chunk_index
            page = result["metadata"].get("page")
            if page:
                citation["location"] = f"p.{page}"
            citations.append(citation)

        context = "\n\n".join(context_parts)
        prompt = f"""Answer the following question based on the provided context. If the context doesn't contain enough information, say so.

Context:
{context}

Question: {query}

Instructions:
- Provide a clear, concise answer
- Reference specific sources using [Source N] notation
- Be honest if the context is insufficient
- Do not make up information not in the context

Answer:"""

        response = await self.llm_adapter.complete(prompt)
        logger.info(
            "rag_answer_generated",
            user_id=str(user_id),
            sources_used=len(results),
            answer_preview=response[:120],
        )
        return {"answer": response, "citations": citations, "sources_used": len(results)}
