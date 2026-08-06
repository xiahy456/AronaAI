"""Empty knowledge RAG stub for future corpus."""

from __future__ import annotations

from .config import KnowledgeConfig


class KnowledgeRetriever:
    def __init__(self, config: KnowledgeConfig | None = None) -> None:
        self.enabled = bool(config and config.enabled)

    def retrieve(self, query: str, top_k: int = 3) -> list[str]:
        if not self.enabled:
            return []
        # Future: Chroma + BGE retrieval
        _ = (query, top_k)
        return []
