import asyncio
from pathlib import Path
from typing import Any, Dict, List, Tuple

import structlog

from api.metrics import document_parsing_duration_seconds

logger = structlog.get_logger()


class ParsingService:
    """Wrapper around Unstructured.io chunking with safe fallbacks."""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    async def parse_document(
        self, file_path: Path, mime_type: str
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, lambda: self._parse_sync(file_path, mime_type)
        )

    def _parse_sync(
        self, file_path: Path, mime_type: str
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        try:
            from unstructured.chunking.title import chunk_by_title
            from unstructured.partition.auto import partition

            with document_parsing_duration_seconds.time():
                elements = partition(
                    filename=str(file_path), include_page_breaks=True, strategy="auto"
                )
            doc_metadata = {
                "total_elements": len(elements),
                "element_types": sorted({getattr(e, "category", "unknown") for e in elements}),
            }
            chunks = chunk_by_title(
                elements,
                max_characters=self.chunk_size * 4,
                combine_text_under_n_chars=100,
                new_after_n_chars=self.chunk_size * 3,
            )

            processed: List[Dict[str, Any]] = []
            for idx, chunk in enumerate(chunks):
                text = str(chunk).strip()
                if not text:
                    continue

                metadata = getattr(chunk, "metadata", None)
                # ElementMetadata uses attribute access, not dictionary access
                page_number = None
                if metadata is not None:
                    page_number = getattr(metadata, "page_number", None) or getattr(metadata, "page", None)
                processed.append(
                    {
                        "text": text,
                        "tokens": max(1, len(text) // 4),
                        "metadata": {
                            "page": page_number,
                            "ordinal": idx,
                            "type": getattr(chunk, "category", "unknown"),
                        },
                    }
                )

            logger.info(
                "document_chunked",
                file_path=str(file_path),
                chunk_count=len(processed),
                mime_type=mime_type,
            )
            return processed, doc_metadata
        except Exception as exc:  # pragma: no cover - optional deps
            if mime_type == "application/pdf":
                logger.error(
                    "parsing_pdf_failed",
                    file_path=str(file_path),
                    error=str(exc),
                )
                raise
            logger.warning(
                "parsing_service_fallback",
                file_path=str(file_path),
                error=str(exc),
            )
            with document_parsing_duration_seconds.time():
                text = file_path.read_text(errors="ignore")
            tokens = text.split()
            processed: List[Dict[str, Any]] = []
            idx = 0
            for start in range(0, len(tokens), self.chunk_size - self.chunk_overlap):
                end = start + self.chunk_size
                chunk_tokens = tokens[start:end]
                if not chunk_tokens:
                    continue
                chunk_text = " ".join(chunk_tokens)
                processed.append(
                    {
                        "text": chunk_text,
                        "tokens": len(chunk_tokens),
                        # Use 1-based ordinal for page to satisfy downstream consumers.
                        "metadata": {"page": idx + 1, "ordinal": idx, "type": "text"},
                    }
                )
                idx += 1

            metadata = {"total_elements": len(tokens), "element_types": ["fallback_text"]}
            return processed, metadata
