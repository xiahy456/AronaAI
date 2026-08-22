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


def normalize_content_for_compare(text: str) -> str:
    """Normalize text for exact/batch dedup keys without changing stored content."""
    s = (text or "").strip()
    s = s.replace("\u3000", " ")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[。．.！!？?]+$", "", s)
    return s.strip()


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
                    source TEXT,
                    last_injected_at REAL
                )
                """
            )
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
                USING fts5(key, content, tokenize='unicode61')
                """
            )
            cols = {
                str(row[1])
                for row in conn.execute("PRAGMA table_info(memories)").fetchall()
            }
            if "last_injected_at" not in cols:
                conn.execute(
                    "ALTER TABLE memories ADD COLUMN last_injected_at REAL"
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

    def encode_query(self, text: str) -> list[float]:
        return self._ensure_encoder().encode_query(text)

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

    def mark_injected(
        self,
        keys: list[str],
        now: float | None = None,
    ) -> None:
        cleaned = [str(k).strip() for k in keys if str(k or "").strip()]
        if not cleaned:
            return
        ts = time.time() if now is None else float(now)
        placeholders = ",".join("?" for _ in cleaned)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE memories SET last_injected_at = ? WHERE key IN ({placeholders})",
                [ts, *cleaned],
            )
            conn.commit()
        logger.info("memory inject marked keys=%s ts=%.3f", cleaned, ts)

    def _cooled_keys(
        self,
        keys: list[str],
        now: float,
        cooldown_sec: float,
    ) -> set[str]:
        cleaned = [str(k).strip() for k in keys if str(k or "").strip()]
        if not cleaned or cooldown_sec <= 0:
            return set()
        cutoff = float(now) - float(cooldown_sec)
        placeholders = ",".join("?" for _ in cleaned)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT key FROM memories
                WHERE key IN ({placeholders})
                  AND last_injected_at IS NOT NULL
                  AND last_injected_at > ?
                """,
                [*cleaned, cutoff],
            ).fetchall()
        return {str(row["key"]) for row in rows}

    def _drop_cooled_entries(
        self,
        passed: list[tuple[str, str, float]],
        *,
        apply_inject_cooldown: bool,
    ) -> list[tuple[str, str, float]]:
        if not apply_inject_cooldown or not passed:
            return passed
        cooldown = float(self.config.inject_cooldown_sec)
        if cooldown <= 0:
            return passed
        cooled = self._cooled_keys(
            [key for key, _, _ in passed],
            time.time(),
            cooldown,
        )
        if not cooled:
            return passed
        remaining = [(k, c, s) for k, c, s in passed if k not in cooled]
        logger.info(
            "memory retrieve cooldown skipped keys=%s remaining=%d cooldown_sec=%.0f",
            sorted(cooled),
            len(remaining),
            cooldown,
        )
        return remaining

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

    def _categories_for_keys(self, keys: list[str]) -> dict[str, str]:
        if not keys:
            return {}
        placeholders = ",".join("?" for _ in keys)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT key, category FROM memories WHERE key IN ({placeholders})",
                keys,
            ).fetchall()
        out: dict[str, str] = {}
        for row in rows:
            cat = (row["category"] or "").strip()
            out[str(row["key"])] = cat or "other"
        return out

    def retrieve_entries(
        self,
        query: str,
        top_k: int = 3,
        query_embedding: list[float] | None = None,
        *,
        apply_inject_cooldown: bool = False,
    ) -> list[dict[str, Any]]:
        """Hybrid retrieve returning key/content/category/score dicts."""
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
            if query_embedding is None:
                query_embedding = self._ensure_encoder().encode_query(query)
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
        ]
        passed = self._drop_cooled_entries(
            passed,
            apply_inject_cooldown=apply_inject_cooldown,
        )[:top_k]

        categories = self._categories_for_keys([key for key, _, _ in passed])
        entries = [
            {
                "key": key,
                "content": content,
                "category": categories.get(key, "other"),
                "score": float(score),
            }
            for key, content, score in passed
        ]
        logger.info(
            "memory retrieve query=%r fts_keys=%d fts_scored=%d vec_hits=%d "
            "merged=%d hits=%d min_score=%.3f scores=%s items=%s",
            query,
            len(fts_keys),
            len(fts_scored),
            len(vec_hits),
            len(merged),
            len(entries),
            min_score,
            [(round(e["score"], 3), e["content"][:40]) for e in entries],
            [e["content"] for e in entries],
        )
        return entries

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        query_embedding: list[float] | None = None,
        *,
        apply_inject_cooldown: bool = False,
    ) -> list[str]:
        entries = self.retrieve_entries(
            query,
            top_k,
            query_embedding=query_embedding,
            apply_inject_cooldown=apply_inject_cooldown,
        )
        cooldown = float(self.config.inject_cooldown_sec)
        if apply_inject_cooldown and cooldown > 0 and entries:
            self.mark_injected([e["key"] for e in entries])
        return [e["content"] for e in entries]

    def find_exact_content(self, content: str) -> list[dict[str, Any]]:
        """Return rows whose stored content equals strip(content) or compare-normalized form."""
        raw = (content or "").strip()
        if not raw:
            return []
        norm = normalize_content_for_compare(raw)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT key, content, category FROM memories"
            ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            stored = str(row["content"] or "").strip()
            if stored == raw or normalize_content_for_compare(stored) == norm:
                out.append(
                    {
                        "key": str(row["key"]),
                        "content": stored,
                        "category": (str(row["category"] or "").strip() or "other"),
                        "score": 1.0,
                    }
                )
        return out

    def find_similar(
        self,
        content: str,
        *,
        exclude_key: str | None = None,
        top_k: int = 5,
        min_score: float = 0.82,
    ) -> list[dict[str, Any]]:
        """Vector-near neighbors of a memory content (for conflict reconcile)."""
        content = (content or "").strip()
        if not content:
            return []

        top_k = max(1, int(top_k))
        min_score = float(min_score)
        exclude = (exclude_key or "").strip()

        try:
            collection = self._ensure_chroma()
            count = int(collection.count())
            if count <= 0:
                return []
            encoder = self._ensure_encoder()
            # Compare memory-to-memory in document space.
            embedding = encoder.encode_documents([content])[0]
            n = min(top_k + (1 if exclude else 0), count)
            result = collection.query(
                query_embeddings=[embedding],
                n_results=n,
                include=["documents", "distances", "metadatas"],
            )
        except Exception:
            logger.exception("Memory find_similar failed content=%r", content[:80])
            return []

        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]

        entries: list[dict[str, Any]] = []
        for i, key in enumerate(ids):
            if not key or str(key) == exclude:
                continue
            dist = distances[i] if i < len(distances) else 1.0
            doc = documents[i] if i < len(documents) else ""
            meta = metadatas[i] if i < len(metadatas) else {}
            similarity = 1.0 - float(dist)
            if similarity < min_score:
                continue
            text = (doc or "").strip()
            if not text:
                continue
            meta = meta or {}
            category = str(meta.get("category") or "").strip() or "other"
            entries.append(
                {
                    "key": str(key),
                    "content": text,
                    "category": category,
                    "score": similarity,
                }
            )
            if len(entries) >= top_k:
                break

        if entries:
            # Prefer SQLite category when present (source of truth).
            cats = self._categories_for_keys([e["key"] for e in entries])
            for e in entries:
                if e["key"] in cats:
                    e["category"] = cats[e["key"]]

        logger.info(
            "memory find_similar exclude=%r min_score=%.3f hits=%d items=%s",
            exclude,
            min_score,
            len(entries),
            [(round(e["score"], 3), e["key"], e["content"][:40]) for e in entries],
        )
        return entries

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM memories").fetchone()
            return int(row["c"] if row else 0)

    def list_by_category(self, category: str) -> list[dict[str, Any]]:
        """Return stored memories in a category (SQLite is source of truth)."""
        cat = (category or "").strip()
        if not cat:
            return []
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT key, content, category, updated_at FROM memories "
                "WHERE category = ?",
                (cat,),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            key = str(row["key"] or "").strip()
            content = str(row["content"] or "").strip()
            if not key or not content:
                continue
            out.append(
                {
                    "key": key,
                    "content": content,
                    "category": str(row["category"] or "").strip() or "other",
                    "updated_at": float(row["updated_at"] or 0.0),
                }
            )
        return out
