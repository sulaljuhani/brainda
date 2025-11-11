import os
import structlog

logger = structlog.get_logger()


class DummyLLMAdapter:
    """Fallback adapter that simply echoes a placeholder response."""

    def __init__(self):
        self.model = os.getenv("LLM_MODEL", "llama3")

    async def complete(self, prompt: str) -> str:
        logger.warning(
            "llm_adapter_placeholder_used",
            model=self.model,
        )
        return "Retrieval results are ready, but no LLM adapter is configured to draft an answer."


def get_llm_adapter():
    return DummyLLMAdapter()
