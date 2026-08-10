"""Shared local BGE encoder for knowledge and memory retrieval."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# BGE-zh retrieval query instruction (short query -> passage).
BGE_QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："


class LocalBgeEncoder:
    """Local sentence-transformers BGE encoder (no HuggingFace download)."""

    def __init__(self, model_path: Path) -> None:
        if not model_path.is_dir():
            raise FileNotFoundError(
                f"Local BGE model not found: {model_path}. "
                "Check knowledge.embedding_model_path (expected ../models/bge-small-zh-v1.5)."
            )
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
