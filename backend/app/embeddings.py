"""Shared local BGE encoder for knowledge and memory retrieval."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# BGE-zh retrieval query instruction (short query -> passage).
BGE_QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Dot product; callers should pass L2-normalized BGE vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    return float(sum(x * y for x, y in zip(a, b)))


def bge_missing_reason(model_path: Path) -> str | None:
    """Return a user-facing reason if the local BGE directory is missing."""
    path = Path(model_path)
    if path.is_dir():
        return None
    return (
        f"Local BGE model not found: {path}. "
        "Place bge-small-zh-v1.5 under models/ (see models/README.md). "
        "Vector memory / knowledge RAG is disabled until then; SQLite FTS and Planner still work."
    )


class LocalBgeEncoder:
    """Local sentence-transformers BGE encoder (no HuggingFace download)."""

    def __init__(self, model_path: Path) -> None:
        missing = bge_missing_reason(model_path)
        if missing is not None:
            raise FileNotFoundError(missing)
        from sentence_transformers import SentenceTransformer

        logger.info("Loading local BGE embedding model from %s", model_path)
        self._model = SentenceTransformer(str(model_path), local_files_only=True)

    def encode_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [v.tolist() for v in vectors]

    def encode_queries(self, texts: list[str]) -> list[list[float]]:
        prompted = [f"{BGE_QUERY_INSTRUCTION}{q}" for q in texts]
        vectors = self._model.encode(
            prompted,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [v.tolist() for v in vectors]

    def encode_query(self, text: str) -> list[float]:
        return self.encode_queries([text])[0]
