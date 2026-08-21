"""Chroma + local BGE vector knowledge retriever."""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jieba

from .config import AppConfig, KnowledgeConfig
from .embeddings import LocalBgeEncoder, cosine_similarity

logger = logging.getLogger(__name__)

_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_PUNCT_RE = re.compile(r"^[\W_]+$", re.UNICODE)

# Function words plus default persona names that collapse all lore chunks.
_LEXICAL_STOPWORDS = frozenset(
    {
        "的",
        "了",
        "是",
        "在",
        "有",
        "和",
        "与",
        "或",
        "也",
        "都",
        "就",
        "而",
        "及",
        "等",
        "被",
        "把",
        "让",
        "给",
        "对",
        "从",
        "向",
        "到",
        "为",
        "以",
        "于",
        "着",
        "过",
        "很",
        "更",
        "最",
        "还",
        "又",
        "再",
        "才",
        "已",
        "已经",
        "会",
        "能",
        "可以",
        "要",
        "想",
        "我",
        "你",
        "他",
        "她",
        "它",
        "我们",
        "你们",
        "他们",
        "这",
        "那",
        "这个",
        "那个",
        "什么",
        "哪",
        "哪个",
        "怎么",
        "怎样",
        "如何",
        "吗",
        "呢",
        "啊",
        "吧",
        "呀",
        "哦",
        "嗯",
        "嘛",
        "哈",
        "啦",
        "哟",
        "不",
        "没",
        "没有",
        "不是",
        "一个",
        "一些",
        "一下",
        "一样",
        "阿洛娜",
        "阿罗娜",
        "arona",
        "アロナ",
        "老师",
        "您",
    }
)


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


def _lexical_tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    for raw in jieba.cut_for_search(text or ""):
        token = raw.strip()
        if not token:
            continue
        lowered = token.lower()
        if lowered in _LEXICAL_STOPWORDS or token in _LEXICAL_STOPWORDS:
            continue
        if _PUNCT_RE.match(token):
            continue
        tokens.add(lowered)
    return tokens


@dataclass
class ScoredKnowledgeHit:
    similarity: float
    title: str
    text: str
    overlap: int


def filter_knowledge_hits(
    hits: list[ScoredKnowledgeHit],
    *,
    min_score: float,
    score_margin: float,
    top_k: int,
) -> list[ScoredKnowledgeHit]:
    """Drop weak neighbors: absolute score, gap to best hit, then lexical extras."""
    passed = [h for h in hits if h.similarity >= min_score]
    if not passed:
        return []
    passed.sort(key=lambda h: (-h.similarity, -h.overlap, h.title))
    top_score = passed[0].similarity
    margin = max(0.0, float(score_margin))
    passed = [h for h in passed if h.similarity >= top_score - margin]
    if len(passed) > 1:
        kept = [passed[0]]
        for hit in passed[1:]:
            if hit.overlap > 0:
                kept.append(hit)
        passed = kept
    k = max(1, int(top_k))
    return passed[:k]


@dataclass
class _QueryCacheEntry:
    embedding: list[float]
    hits: list[str]
    top_k: int
    collection_n: int


class SemanticHitCache:
    """In-process nearest-neighbor cache of filtered knowledge hit texts."""

    def __init__(self, *, size: int, min_cosine: float) -> None:
        self.size = max(1, int(size))
        self.min_cosine = float(min_cosine)
        self._entries: list[_QueryCacheEntry] = []
        self._lock = threading.Lock()

    def get(
        self,
        embedding: list[float],
        *,
        top_k: int,
        collection_n: int,
    ) -> tuple[list[str], float] | None:
        with self._lock:
            best: _QueryCacheEntry | None = None
            best_cos = -1.0
            for entry in self._entries:
                if entry.top_k != top_k or entry.collection_n != collection_n:
                    continue
                cos = cosine_similarity(embedding, entry.embedding)
                if cos >= self.min_cosine and cos > best_cos:
                    best = entry
                    best_cos = cos
            if best is None:
                return None
            self._entries.remove(best)
            self._entries.append(best)
            return list(best.hits), best_cos

    def put(
        self,
        embedding: list[float],
        hits: list[str],
        *,
        top_k: int,
        collection_n: int,
    ) -> None:
        with self._lock:
            self._entries.append(
                _QueryCacheEntry(
                    embedding=list(embedding),
                    hits=list(hits),
                    top_k=int(top_k),
                    collection_n=int(collection_n),
                )
            )
            overflow = len(self._entries) - self.size
            if overflow > 0:
                del self._entries[:overflow]

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)


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
        self._query_cache = SemanticHitCache(
            size=int(self.config.query_cache_size),
            min_cosine=float(self.config.query_cache_min_cosine),
        )

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
        jieba.initialize()
        self._ensure_backend()

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        query_embedding: list[float] | None = None,
    ) -> list[str]:
        if not self.enabled:
            return []
        query = (query or "").strip()
        if not query:
            return []

        k = top_k if top_k is not None else self.config.retrieve_top_k
        k = max(1, int(k))
        candidate_k = max(k, int(self.config.candidate_top_k))

        try:
            self._ensure_backend()
        except Exception:
            logger.exception("Knowledge backend init failed")
            return []

        assert self._collection is not None and self._encoder is not None
        try:
            count = int(self._collection.count())
        except Exception:
            logger.exception("Knowledge collection count failed")
            return []
        if count <= 0:
            logger.info("knowledge retrieve query=%r skipped empty chroma", query)
            return []
        n_results = min(candidate_k, count)

        try:
            q_emb = (
                query_embedding
                if query_embedding is not None
                else self._encoder.encode_query(query)
            )
            cache_on = bool(self.config.query_cache_enabled)
            if cache_on:
                cached = self._query_cache.get(
                    q_emb, top_k=k, collection_n=count
                )
                if cached is not None:
                    hits, cosine = cached
                    logger.info(
                        "knowledge retrieve cache=hit cosine=%.3f query=%r hits=%d",
                        cosine,
                        query,
                        len(hits),
                    )
                    return hits
            result = self._collection.query(
                query_embeddings=[q_emb],
                n_results=n_results,
                include=["documents", "metadatas", "distances"],
            )
        except Exception:
            logger.exception("Knowledge retrieve failed for query=%r", query)
            return []

        documents = (result.get("documents") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        query_tokens = _lexical_tokens(query)

        raw_hits: list[ScoredKnowledgeHit] = []
        for doc, dist, meta in zip(documents, distances, metadatas):
            similarity = 1.0 - float(dist)
            meta_dict = meta if isinstance(meta, dict) else {}
            title = str(meta_dict.get("title") or "").strip()
            display_body = str(meta_dict.get("body") or "").strip()
            if display_body:
                text = f"{title}：{display_body}" if title else display_body
            else:
                text = (doc or "").strip()
            if not text:
                continue
            overlap = len(query_tokens & _lexical_tokens(f"{title}\n{display_body or text}"))
            raw_hits.append(
                ScoredKnowledgeHit(
                    similarity=similarity,
                    title=title or text[:40],
                    text=text,
                    overlap=overlap,
                )
            )

        filtered = filter_knowledge_hits(
            raw_hits,
            min_score=float(self.config.min_score),
            score_margin=float(self.config.score_margin),
            top_k=k,
        )
        hits = [h.text for h in filtered]
        logger.info(
            "knowledge retrieve cache=miss query=%r candidates=%d hits=%d min_score=%.3f "
            "score_margin=%.3f scores=%s",
            query,
            len(documents),
            len(filtered),
            self.config.min_score,
            self.config.score_margin,
            [(round(h.similarity, 3), h.title, h.overlap) for h in filtered],
        )
        if bool(self.config.query_cache_enabled):
            self._query_cache.put(q_emb, hits, top_k=k, collection_n=count)
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
            self._query_cache.clear()

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
        self._query_cache.clear()
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
