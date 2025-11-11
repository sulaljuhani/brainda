import hashlib
import random
from typing import List

VECTOR_DIMENSIONS = 384
MODEL_NAME = "all-MiniLM-L6-v2:1"


def _seed_from_text(text: str) -> int:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return int.from_bytes(digest, byteorder="big", signed=False)


def generate_embedding(text: str, dimensions: int = VECTOR_DIMENSIONS) -> List[float]:
    """Return a deterministic pseudo-embedding for the provided text."""
    if not text:
        text = ""
    rng = random.Random(_seed_from_text(text))
    return [rng.uniform(-1.0, 1.0) for _ in range(dimensions)]
