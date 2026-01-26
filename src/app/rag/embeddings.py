from __future__ import annotations

import logging
from typing import List

try:
    from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]
except ImportError:
    SentenceTransformer = None

logger = logging.getLogger(__name__)

_EMBEDDING_MODEL: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer | None:
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is None and SentenceTransformer is not None:
        try:
            _EMBEDDING_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception as e:
            logger.warning(f"Failed to load embedding model: {e}")
    return _EMBEDDING_MODEL


def generate_embedding(text: str) -> List[float]:
    model = get_embedding_model()
    if model is None:
        raise RuntimeError("Embedding model not available")
    return model.encode(text, convert_to_numpy=True).tolist()


def generate_embeddings(texts: List[str]) -> List[List[float]]:
    model = get_embedding_model()
    if model is None:
        raise RuntimeError("Embedding model not available")
    return model.encode(texts, convert_to_numpy=True).tolist()
