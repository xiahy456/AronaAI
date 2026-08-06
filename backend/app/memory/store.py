"""SQLite + FTS5 long-term memory store."""

from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path

import jieba

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> str:
    tokens = [t.strip() for t in jieba.cut_for_search(text or "") if t.strip()]
    return " ".join(tokens)


class MemoryStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
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

    def delete(self, key: str) -> None:
        key = (key or "").strip()
        if not key:
            return
        with self._connect() as conn:
            conn.execute("DELETE FROM memories WHERE key = ?", (key,))
            conn.execute("DELETE FROM memories_fts WHERE key = ?", (key,))
            conn.commit()
        logger.info("Memory delete key=%s", key)

    @staticmethod
    def _fts_quote(token: str) -> str:
        cleaned = token.replace('"', " ").strip()
        if not cleaned:
            return ""
        return f'"{cleaned}"'

    def retrieve(self, query: str, top_k: int = 3) -> list[str]:
        query = (query or "").strip()
        if not query:
            return []

        tokens = [self._fts_quote(t) for t in _tokenize(query).split() if t]
        tokens = [t for t in tokens if t]
        if not tokens:
            return []

        and_q = " ".join(tokens)
        or_q = " OR ".join(tokens)

        with self._connect() as conn:
            rows = self._fts_search(conn, and_q, top_k)
            if not rows and or_q != and_q:
                rows = self._fts_search(conn, or_q, top_k)

        return [r["content"] for r in rows]

    @staticmethod
    def _fts_search(conn: sqlite3.Connection, match_query: str, top_k: int) -> list[sqlite3.Row]:
        try:
            return conn.execute(
                """
                SELECT m.content
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

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM memories").fetchone()
            return int(row["c"] if row else 0)
