from typing import List, Optional
from uuid import UUID

import structlog

from api.metrics import rag_queries_total
from api.services.vector_service import VectorService
from api.services.memory_service import MemoryService

logger = structlog.get_logger()


class RAGService:
    """Answer questions using retrieved chunks with citation payloads and long-term memory."""

    def __init__(
        self,
        vector_service: VectorService,
        llm_adapter,
        memory_service: Optional[MemoryService] = None,
    ):
        self.vector_service = vector_service
        self.llm_adapter = llm_adapter
        self.memory_service = memory_service or MemoryService()

    async def answer_question(
        self,
        query: str,
        user_id: UUID,
        content_type: Optional[str] = None,
        max_sources: int = 5,
        use_memory: bool = True,
    ) -> dict:
        # Retrieve document/note context from Qdrant
        results = await self.vector_service.search(
            query=query,
            user_id=user_id,
            content_type=content_type,
            limit=max_sources,
            min_score=0.1,
        )

        rag_queries_total.inc()

        # Retrieve conversation context from OpenMemory
        memory_context = ""
        if use_memory and self.memory_service.is_enabled():
            memory_context = await self.memory_service.get_conversation_context(
                user_id=user_id,
                current_query=query,
                max_memories=10,
            )

        # Build document/note context
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

        document_context = "\n\n".join(context_parts) if context_parts else ""

        # Build comprehensive prompt with both document and memory context
        prompt_parts = []
        prompt_parts.append("Answer the following question based on the provided context.")

        if document_context:
            prompt_parts.append(f"\n## Document Context:\n{document_context}")

        if memory_context:
            prompt_parts.append(f"\n## Conversation History (Previous Interactions):\n{memory_context}")

        if not document_context and not memory_context:
            # No context available
            answer = "I couldn't find any relevant information to answer your question."
            logger.info(
                "rag_answer_generated_no_context",
                user_id=str(user_id),
            )
            return {
                "answer": answer,
                "citations": [],
                "sources_used": 0,
                "memory_used": False,
            }

        prompt_parts.append(f"""
Question: {query}

Instructions:
- Provide a clear, concise answer based on the context
- Reference specific document sources using [Source N] notation when applicable
- Consider previous conversation history for continuity
- Be honest if the context is insufficient
- Do not make up information not in the context

Answer:""")

        prompt = "\n".join(prompt_parts)
        response = await self.llm_adapter.complete(prompt)

        # Store this conversation turn in OpenMemory for future context
        if use_memory and self.memory_service.is_enabled():
            metadata = {
                "sources_used": len(results),
                "query_type": "rag_question",
            }
            await self.memory_service.store_conversation(
                user_id=user_id,
                user_message=query,
                assistant_message=response,
                metadata=metadata,
            )

        logger.info(
            "rag_answer_generated",
            user_id=str(user_id),
            sources_used=len(results),
            memory_used=bool(memory_context),
            answer_preview=response[:120],
        )

        return {
            "answer": response,
            "citations": citations,
            "sources_used": len(results),
            "memory_used": bool(memory_context),
        }
