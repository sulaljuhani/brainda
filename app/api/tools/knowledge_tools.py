from typing import Optional
from uuid import UUID

import structlog

from api.services.rag_service import RAGService
from api.services.vector_service import VectorService
from api.adapters.llm_adapter import get_llm_adapter
from api.metrics import tool_calls_total

logger = structlog.get_logger()

KNOWLEDGE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": "Semantic search across notes and uploaded documents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "content_type": {
                        "type": "string",
                        "enum": ["note", "document_chunk", "all"],
                        "description": "Filter by content type",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of matches",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "answer_question",
            "description": "Answer questions using RAG across personal knowledge.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "content_type": {
                        "type": "string",
                        "enum": ["note", "document", "all"],
                        "description": "Restrict retrieval scope",
                    },
                },
                "required": ["question"],
            },
        },
    },
]


async def execute_knowledge_tool(
    tool_name: str,
    arguments: dict,
    user_id: UUID,
) -> dict:
    """Execute knowledge-related tool calls for the LLM orchestration layer."""
    try:
        vector_service = VectorService()

        if tool_name == "search_knowledge_base":
            content_type = arguments.get("content_type")
            if content_type == "all":
                content_type = None
            results = await vector_service.search(
                query=arguments["query"],
                user_id=user_id,
                content_type=content_type,
                limit=arguments.get("limit", 10),
            )
            tool_calls_total.labels(tool_name=tool_name, status="success").inc()
            return {"success": True, "data": {"results": results}}

        if tool_name == "answer_question":
            content_type = arguments.get("content_type")
            if content_type == "document":
                content_type = "document_chunk"
            elif content_type == "all":
                content_type = None

            rag_service = RAGService(vector_service, get_llm_adapter())
            result = await rag_service.answer_question(
                query=arguments["question"],
                user_id=user_id,
                content_type=content_type,
            )
            tool_calls_total.labels(tool_name=tool_name, status="success").inc()
            return {"success": True, "data": result}

        tool_calls_total.labels(
            tool_name=tool_name or "unknown",
            status="error",
        ).inc()
        return {
            "success": False,
            "error": {"code": "UNKNOWN_TOOL", "message": f"Tool {tool_name} not implemented"},
        }

    except Exception as exc:  # pragma: no cover
        logger.error("knowledge_tool_failed", tool=tool_name, error=str(exc))
        tool_calls_total.labels(
            tool_name=tool_name or "unknown",
            status="error",
        ).inc()
        return {
            "success": False,
            "error": {"code": "INTERNAL_ERROR", "message": str(exc)},
        }
