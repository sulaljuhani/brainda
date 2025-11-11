import asyncio
from typing import Iterable, List, Optional

import structlog

from common.embeddings import MODEL_NAME, generate_embedding

logger = structlog.get_logger()


class EmbeddingService:
    """
    Wrap SentenceTransformer when available, otherwise fall back to the
    deterministic mock embedding used throughout the project.
    """

    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name
        self._model = None
        try:
            from sentence_transformers import SentenceTransformer

            normalized = model_name.split(":")[0]
            self._model = SentenceTransformer(normalized)
            logger.info("embedding_service_loaded", model=self._model.__class__.__name__)
        except Exception as exc:  # pragma: no cover - depends on optional dep
            logger.warning(
                "embedding_service_fallback",
                reason=str(exc),
                model_name=model_name,
            )
            self._model = None

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
