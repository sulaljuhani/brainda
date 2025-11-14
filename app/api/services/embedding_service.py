import asyncio
from functools import lru_cache
from typing import Iterable, List, Optional

import structlog

from common.embeddings import MODEL_NAME, generate_embedding

logger = structlog.get_logger()


@lru_cache(maxsize=1)
def _get_model(model_name: str):
    """Cached model loader to avoid reloading the model on every instantiation."""
    try:
        from sentence_transformers import SentenceTransformer

        normalized = model_name.split(":")[0]
        model = SentenceTransformer(normalized)
        logger.info("embedding_model_loaded", model=model.__class__.__name__)
        return model
    except Exception as exc:
        logger.warning(
            "embedding_model_load_failed",
            reason=str(exc),
            model_name=model_name,
        )
        return None


class EmbeddingService:
    """
    Wrap SentenceTransformer when available, otherwise fall back to the
    deterministic mock embedding used throughout the project.
    """

    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name
        # Use cached model loader instead of loading on every instantiation
        self._model = _get_model(model_name)

    async def _encode(self, texts: Iterable[str]) -> List[List[float]]:
        text_list = list(texts)
        if not self._model:
            return [generate_embedding(text) for text in text_list]

        loop = asyncio.get_running_loop()
        encode = lambda: self._model.encode(
            text_list, show_progress_bar=False, batch_size=16
        )
        vectors = await loop.run_in_executor(None, encode)
        return [vector.tolist() for vector in vectors]

    async def embed(self, text: str) -> List[float]:
        return (await self.embed_batch([text]))[0]

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return await self._encode(texts)
