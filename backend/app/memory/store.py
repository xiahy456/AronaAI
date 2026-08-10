"""SQLite + FTS5 + Chroma hybrid long-term memory store."""

from __future__ import annotations

import logging
import math
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

import jieba

from ..config import AppConfig, MemoryConfig
from ..embeddings import LocalBgeEncoder

logger = logging.getLogger(__name__)

# Function words / particles that caused false OR hits (e.g. 是 / 的).
_STOPWORDS = frozenset(
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
    }
)

_PUNCT_RE = re.compile(r"^[\W_]+$", re.UNICODE)


def _raw_tokens(text: str) -> list[str]:
    return [t.strip() for t in jieba.cut_for_search(text or "") if t.strip()]


def _is_stop_or_punct(token: str) -> bool:
    if not token:
        return True
    if token in _STOPWORDS:
        return True
    if _PUNCT_RE.match(token):
        return True
    return False


def _tokenize(text: str) -> str:
    """Jieba tokenize then drop stopwords/punctuation for FTS indexing/query."""
    tokens = [t for t in _raw_tokens(text) if not _is_stop_or_punct(t)]
    return " ".join(tokens)


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return float(sum(x * y for x, y in zip(a, b)))


class MemoryStore:
    def __init__(
        self,
        app_config: AppConfig,
        encoder: LocalBgeEncoder | None = None,
        *,
        db_path: Path | None = None,
    ) -> None:
        self.app_config = app_config
        self.config: MemoryConfig = app_config.memory
        self.db_path = Path(db_path) if db_path is not None else app_config.memory_db_abs_path
        self.chroma_path = app_config.memory_chroma_abs_path
        self.embedding_path = app_config.knowledge_embedding_abs_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._encoder = encoder
        self._collection: Any | None = None
        self._client: Any | None = None
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    key TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    category TEXT,
                    updated_at REAL NOT NULL,
                    source TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
                USING fts5(key, content, tokenize='unicode61')
                """
            )
            conn.commit()

    def _ensure_encoder(self) -> LocalBgeEncoder:
        if self._encoder is None:
            self._encoder = LocalBgeEncoder(self.embedding_path)
        return self._encoder

    def _ensure_chroma(self) -> Any:
        if self._collection is not None:
            return self._collection

        import chromadb
        from chromadb.config import Settings

        self.chroma_path.mkdir(parents=True, exist_ok=True)
        self._ensure_encoder()
        self._client = chromadb.PersistentClient(
            path=str(self.chroma_path),
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=self.config.collection,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "Memory Chroma ready collection=%s path=%s",
            self.config.collection,
            self.chroma_path,
        )
        return self._collection

    def warmup(self) -> None:
        """Eagerly build jieba + BGE + Chroma so first retrieve is not cold."""
        logger.info("Warming up jieba dictionary")
        jieba.initialize()
        _tokenize("预热")
        logger.info("jieba dictionary ready")
        try:
            self._ensure_chroma()
        except Exception:
            logger.exception("Memory Chroma warmup failed; will retry on first use")

    def upsert(
        self,
        key: str,
        content: str,
        category: str | None = None,
        source: str = "extractor",
    ) -> None:
        key = (key or "").strip()
        content = (content or "").strip()
        if not key or not content:
            return
        if len(content) > 200:
            content = content[:200]

        now = time.time()
        fts_body = _tokenize(f"{key} {content}")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO memories(key, content, category, updated_at, source)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    content=excluded.content,
                    category=excluded.category,
                    updated_at=excluded.updated_at,
                    source=excluded.source
                """,
                (key, content, category, now, source),
            )
            conn.execute("DELETE FROM memories_fts WHERE key = ?", (key,))
            conn.execute(
                "INSERT INTO memories_fts(key, content) VALUES (?, ?)",
                (key, fts_body),
            )
            conn.commit()
        logger.info("Memory upsert key=%s content=%s", key, content)
        self._chroma_upsert(key, content, category=category, source=source)

    def _chroma_upsert(
        self,
        key: str,
        content: str,
        *,
        category: str | None,
        source: str,
    ) -> None:
        try:
            collection = self._ensure_chroma()
            encoder = self._ensure_encoder()
            embedding = encoder.encode_documents([content])[0]
            collection.upsert(
                ids=[key],
                documents=[content],
                metadatas=[
                    {
                        "category": category or "",
                        "source": source or "",
                    }
                ],
                embeddings=[embedding],
            )
        except Exception:
            logger.exception("Memory Chroma upsert failed key=%s", key)

    def delete(self, key: str) -> None:
        key = (key or "").strip()
        if not key:
            return
        with self._connect() as conn:
            conn.execute("DELETE FROM memories WHERE key = ?", (key,))
            conn.execute("DELETE FROM memories_fts WHERE key = ?", (key,))
            conn.commit()
        logger.info("Memory delete key=%s", key)
        self._chroma_delete(key)

    def _chroma_delete(self, key: str) -> None:
        try:
            collection = self._ensure_chroma()
            collection.delete(ids=[key])
        except Exception:
            logger.exception("Memory Chroma delete failed key=%s", key)

    @staticmethod
    def _fts_quote(token: str) -> str:
        cleaned = token.replace('"', " ").strip()
        if not cleaned:
            return ""
        return f'"{cleaned}"'

    def _fts_candidate_keys(self, query: str, limit: int) -> list[str]:
        tokens = [self._fts_quote(t) for t in _tokenize(query).split() if t]
        tokens = [t for t in tokens if t]
        if not tokens:
            return []

        and_q = " ".join(tokens)
        or_q = " OR ".join(tokens)

        with self._connect() as conn:
            rows = self._fts_search(conn, and_q, limit)
            if not rows and len(tokens) >= 2 and or_q != and_q:
                rows = self._fts_search(conn, or_q, limit)
        return [str(r["key"]) for r in rows]

    @staticmethod
    def _fts_search(conn: sqlite3.Connection, match_query: str, top_k: int) -> list[sqlite3.Row]:
        try:
            return conn.execute(
                """
                SELECT m.key, m.content
                FROM memories_fts f
                JOIN memories m ON m.key = f.key
                WHERE memories_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (match_query, top_k),
            ).fetchall()
        except sqlite3.OperationalError as exc:
            logger.warning("FTS search failed for %r: %s", match_query, exc)
            return []

    def _vector_candidates(
        self,
        query_embedding: list[float],
        limit: int,
    ) -> dict[str, tuple[str, float]]:
        """Return key -> (content, similarity) from Chroma vector search."""
        collection = self._ensure_chroma()
        n = max(1, limit)
        # Chroma errors if n_results > collection size; clamp defensively.
        try:
            count = int(collection.count())
        except Exception:
            count = n
        if count <= 0:
            return {}
        n = min(n, count)

        result = collection.query(
            query_embeddings=[query_embedding],
            n_results=n,
            include=["documents", "distances"],
        )
        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]

        out: dict[str, tuple[str, float]] = {}
        for key, doc, dist in zip(ids, documents, distances):
            if not key:
                continue
            similarity = 1.0 - float(dist)
            content = (doc or "").strip()
            out[str(key)] = (content, similarity)
        return out

    def _score_fts_keys(
        self,
        keys: list[str],
        query_embedding: list[float],
    ) -> dict[str, tuple[str, float]]:
        """Score FTS keys that already have Chroma embeddings; drop legacy-only rows."""
        if not keys:
            return {}
        collection = self._ensure_chroma()
        try:
            got = collection.get(ids=keys, include=["documents", "embeddings"])
        except Exception:
            logger.exception("Memory Chroma get failed for FTS keys")
            return {}

        ids = got.get("ids") or []
        documents = got.get("documents")
        embeddings = got.get("embeddings")
        if documents is None:
            documents = []
        if embeddings is None:
            embeddings = []

        out: dict[str, tuple[str, float]] = {}
        for key, doc, emb in zip(ids, documents, embeddings):
            if not key or emb is None:
                continue
            # chromadb may return numpy arrays
            if hasattr(emb, "tolist"):
                emb_list = emb.tolist()
            else:
                emb_list = list(emb)
            if not emb_list or any(x is None for x in emb_list):
                continue
            if any(isinstance(x, float) and math.isnan(x) for x in emb_list):
                continue
            similarity = _cosine(query_embedding, emb_list)
            content = (doc or "").strip()
            if content:
                out[str(key)] = (content, similarity)
        return out

    def retrieve(self, query: str, top_k: int = 3) -> list[str]:
        query = (query or "").strip()
        if not query:
            return []

        top_k = max(1, int(top_k))
        candidate_k = max(top_k, int(self.config.candidate_top_k))
        min_score = float(self.config.min_score)

        try:
            collection = self._ensure_chroma()
            if int(collection.count()) <= 0:
                logger.info(
                    "memory retrieve query=%r skipped empty chroma",
                    query,
                )
                return []
            encoder = self._ensure_encoder()
            query_embedding = encoder.encode_queries([query])[0]
        except Exception:
            logger.exception("Memory retrieve backend init failed")
            return []

        try:
            vec_hits = self._vector_candidates(query_embedding, candidate_k)
        except Exception:
            logger.exception("Memory vector retrieve failed query=%r", query)
            vec_hits = {}

        fts_keys = self._fts_candidate_keys(query, candidate_k)
        try:
            fts_scored = self._score_fts_keys(fts_keys, query_embedding)
        except Exception:
            logger.exception("Memory FTS rescore failed query=%r", query)
            fts_scored = {}

        merged: dict[str, tuple[str, float]] = {}
        for key, (content, score) in vec_hits.items():
            merged[key] = (content, score)
        for key, (content, score) in fts_scored.items():
            prev = merged.get(key)
            if prev is None or score > prev[1]:
                merged[key] = (content, score)

        ranked = sorted(merged.items(), key=lambda item: item[1][1], reverse=True)
        passed = [
            (key, content, score)
            for key, (content, score) in ranked
            if score >= min_score and content
        ][:top_k]

        contents = [content for _, content, _ in passed]
        logger.info(
            "memory retrieve query=%r fts_keys=%d fts_scored=%d vec_hits=%d "
            "merged=%d hits=%d min_score=%.3f scores=%s items=%s",
            query,
            len(fts_keys),
            len(fts_scored),
            len(vec_hits),
            len(merged),
            len(contents),
            min_score,
            [(round(score, 3), content[:40]) for _, content, score in passed],
            contents,
        )
        return contents

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM memories").fetchone()
            return int(row["c"] if row else 0)
