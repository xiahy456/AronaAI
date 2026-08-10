"""Chroma + local BGE vector knowledge retriever."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import AppConfig, KnowledgeConfig
from .embeddings import LocalBgeEncoder

logger = logging.getLogger(__name__)

_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


@dataclass
class KnowledgeChunk:
    id: str
    title: str
    body: str
    source: str

    @property
    def embed_text(self) -> str:
        return f"【{self.title}】\n{self.body}"


def _slug(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^\w\u4e00-\u9fff\-]+", "", text, flags=re.UNICODE)
    return text or "chunk"


def parse_markdown_file(path: Path) -> list[KnowledgeChunk]:
    raw = path.read_text(encoding="utf-8")
    matches = list(_HEADING_RE.finditer(raw))
    if not matches:
        return []

    file_slug = _slug(path.stem)
    chunks: list[KnowledgeChunk] = []
    for i, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        body = raw[start:end].strip()
        body = re.sub(r"^#\s+.*$", "", body, flags=re.MULTILINE).strip()
        if not title or not body:
            continue
        chunk_id = f"{file_slug}__{_slug(title)}"
        chunks.append(
            KnowledgeChunk(
                id=chunk_id,
                title=title,
                body=body,
                source=path.name,
            )
        )
    return chunks


def load_corpus(corpus_dir: Path) -> list[KnowledgeChunk]:
    if not corpus_dir.is_dir():
        raise FileNotFoundError(f"Knowledge corpus directory not found: {corpus_dir}")
    chunks: list[KnowledgeChunk] = []
    for path in sorted(corpus_dir.glob("*.md")):
        chunks.extend(parse_markdown_file(path))
    return chunks


class KnowledgeRetriever:
    def __init__(
        self,
        app_config: AppConfig,
        encoder: LocalBgeEncoder | None = None,
    ) -> None:
        self.app_config = app_config
        self.config: KnowledgeConfig = app_config.knowledge
        self.enabled = bool(self.config.enabled)
        self.corpus_dir = app_config.knowledge_corpus_abs_path
        self.chroma_path = app_config.knowledge_chroma_abs_path
        self.embedding_path = app_config.knowledge_embedding_abs_path
        self._collection: Any | None = None
        self._encoder: LocalBgeEncoder | None = encoder
        self._client: Any | None = None

    def _ensure_backend(self) -> None:
        if self._collection is not None and self._encoder is not None:
            return

        import chromadb
        from chromadb.config import Settings

        self.chroma_path.mkdir(parents=True, exist_ok=True)
        if self._encoder is None:
            self._encoder = LocalBgeEncoder(self.embedding_path)
        self._client = chromadb.PersistentClient(
            path=str(self.chroma_path),
            settings=Settings(anonymized_telemetry=False),
        )
        # No embedding_function: we pass embeddings explicitly (query vs doc differ for BGE).
        self._collection = self._client.get_or_create_collection(
            name=self.config.collection,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "Knowledge Chroma ready collection=%s path=%s",
            self.config.collection,
            self.chroma_path,
        )

    def warmup(self) -> None:
        """Eagerly load BGE + Chroma so first RAG retrieve is not cold."""
        if not self.enabled:
            return
        self._ensure_backend()

    def retrieve(self, query: str, top_k: int | None = None) -> list[str]:
        if not self.enabled:
            return []
        query = (query or "").strip()
        if not query:
            return []

        k = top_k if top_k is not None else self.config.retrieve_top_k
        k = max(1, int(k))

        try:
            self._ensure_backend()
        except Exception:
            logger.exception("Knowledge backend init failed")
            return []

        assert self._collection is not None and self._encoder is not None
        try:
            q_emb = self._encoder.encode_queries([query])[0]
            result = self._collection.query(
                query_embeddings=[q_emb],
                n_results=k,
                include=["documents", "metadatas", "distances"],
            )
        except Exception:
            logger.exception("Knowledge retrieve failed for query=%r", query)
            return []

        documents = (result.get("documents") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]

        hits: list[str] = []
        scored: list[tuple[float, str]] = []
        for doc, dist, meta in zip(documents, distances, metadatas):
            similarity = 1.0 - float(dist)
            if similarity < self.config.min_score:
                continue
            title = (meta or {}).get("title") if isinstance(meta, dict) else None
            display_body = (meta or {}).get("body") if isinstance(meta, dict) else None
            if display_body:
                text = f"{title}：{display_body}" if title else str(display_body)
            else:
                text = (doc or "").strip()
            if text:
                hits.append(text)
                scored.append((similarity, title or text[:40]))
        logger.info(
            "knowledge retrieve query=%r candidates=%d hits=%d min_score=%.3f scores=%s",
            query,
            len(documents),
            len(hits),
            self.config.min_score,
            [(round(s, 3), t) for s, t in scored],
        )
        return hits

    def ingest(self, *, rebuild: bool = False) -> int:
        """Load Markdown corpus into Chroma. Returns number of upserted chunks."""
        chunks = load_corpus(self.corpus_dir)
        if not chunks:
            logger.warning("No knowledge chunks found under %s", self.corpus_dir)
            return 0

        import chromadb
        from chromadb.config import Settings

        self.chroma_path.mkdir(parents=True, exist_ok=True)
        if self._encoder is None:
            self._encoder = LocalBgeEncoder(self.embedding_path)
        self._client = chromadb.PersistentClient(
            path=str(self.chroma_path),
            settings=Settings(anonymized_telemetry=False),
        )

        if rebuild:
            try:
                self._client.delete_collection(self.config.collection)
                logger.info("Deleted Chroma collection %s", self.config.collection)
            except Exception:
                pass
            self._collection = None

        self._collection = self._client.get_or_create_collection(
            name=self.config.collection,
            metadata={"hnsw:space": "cosine"},
        )

        ids = [c.id for c in chunks]
        documents = [c.embed_text for c in chunks]
        metadatas = [
            {"title": c.title, "body": c.body, "source": c.source}
            for c in chunks
        ]
        embeddings = self._encoder.encode_documents(documents)
        self._collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )
        logger.info(
            "Ingested %d knowledge chunks into %s",
            len(chunks),
            self.config.collection,
        )
        return len(chunks)


def ingest_corpus(app_config: AppConfig, *, rebuild: bool = False) -> int:
    """Module-level helper for scripts (works even if knowledge.enabled is false)."""
    retriever = KnowledgeRetriever(app_config)
    return retriever.ingest(rebuild=rebuild)
