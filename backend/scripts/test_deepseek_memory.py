"""Integration test: DeepSeek memory extraction -> SQLite store.

Loads API settings from backend/config.yaml, writes to an isolated temp DB,
disables regex fallback so success proves the DeepSeek path.

Usage (from backend/):
  python scripts/test_deepseek_memory.py
"""

from __future__ import annotations

import argparse
import asyncio
import sqlite3
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

from app.config import load_config  # noqa: E402
from app.memory.extractor import MemoryExtractor  # noqa: E402
from app.memory.store import MemoryStore  # noqa: E402

USER_INPUTS = [
    "我的生日是8月2号。",
    "我不是很喜欢吃蔬菜。",
    "浅蓝色感觉不错，我很喜欢。",
    "记得8月31号的时候提醒我交稿。",
]

# Soft content checks — DeepSeek phrasing may vary.
EXPECTED_HINTS = [
    ("生日 / 8月2", ("生日", "8月2", "八月二", "8月2号")),
    ("不喜欢蔬菜", ("蔬菜", "不喜欢", "不是很喜欢")),
    ("喜欢浅蓝色", ("浅蓝", "蓝色", "浅蓝")),
    ("8月31交稿提醒", ("8月31", "八月31", "交稿", "提醒")),
]


def _list_memories(db_path: Path) -> list[sqlite3.Row]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            "SELECT key, content, category, source, updated_at FROM memories ORDER BY updated_at"
        ).fetchall()
    finally:
        conn.close()


def _print_rows(rows: list[sqlite3.Row]) -> None:
    if not rows:
        print("(no rows)")
        return
    for i, row in enumerate(rows, 1):
        print(
            f"  {i}. key={row['key']!r} category={row['category']!r} "
            f"source={row['source']!r}\n     content={row['content']!r}"
        )


def _content_blob(rows: list[sqlite3.Row]) -> str:
    return "\n".join(str(r["content"] or "") for r in rows)


def _assert_hints(blob: str) -> list[str]:
    missing: list[str] = []
    for label, keywords in EXPECTED_HINTS:
        if not any(k in blob for k in keywords):
            missing.append(label)
    return missing


async def run_test(*, keep_db: Path | None = None) -> int:
    config = load_config()
    ext_cfg = config.memory.extractor
    if not ext_cfg.enabled:
        print("FAIL: memory.extractor.enabled is false", file=sys.stderr)
        return 1
    if not ext_cfg.api_key or ext_cfg.api_key == "YOUR_DEEPSEEK_API_KEY":
        print("FAIL: set memory.extractor.api_key in config.yaml", file=sys.stderr)
        return 1

    # Force DeepSeek-only path (no regex camouflage).
    ext_cfg = ext_cfg.model_copy(update={"fallback": "none"})

    if keep_db is not None:
        db_path = keep_db
        if db_path.exists():
            db_path.unlink()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        cleanup = False
    else:
        tmp = tempfile.NamedTemporaryFile(prefix="arona_mem_ds_", suffix=".db", delete=False)
        tmp.close()
        db_path = Path(tmp.name)
        cleanup = True

    print(f"DB: {db_path}")
    print(f"API: {ext_cfg.base_url} model={ext_cfg.model}")
    print(f"Inputs ({len(USER_INPUTS)}):")
    for text in USER_INPUTS:
        print(f"  - {text}")

    store = MemoryStore(db_path)
    extractor = MemoryExtractor(store, ext_cfg)
    await extractor.start()
    try:
        for text in USER_INPUTS:
            transcript = f"老师: {text}"
            await extractor.enqueue(transcript=transcript, user_text=text)
        await asyncio.wait_for(extractor._queue.join(), timeout=ext_cfg.timeout_sec * len(USER_INPUTS) + 30)
    finally:
        await extractor.stop()

    rows = _list_memories(db_path)
    print(f"\nStored {len(rows)} memories:")
    _print_rows(rows)

    failures: list[str] = []
    if not rows:
        failures.append("no memories written (DeepSeek returned empty or call failed)")
    else:
        sources = {str(r["source"] or "") for r in rows}
        if sources != {"deepseek"}:
            failures.append(f"expected all source=deepseek, got {sorted(sources)}")

        missing = _assert_hints(_content_blob(rows))
        if missing:
            failures.append("missing expected topics in content: " + ", ".join(missing))

    if cleanup and db_path.exists():
        try:
            db_path.unlink()
        except OSError:
            pass

    if failures:
        print("\nFAIL:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print("\nPASS: DeepSeek extraction wrote memories to SQLite.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Test DeepSeek memory extract -> DB")
    parser.add_argument(
        "--keep-db",
        type=Path,
        default=None,
        help="Optional path to keep the test DB (default: temp file, deleted after run)",
    )
    args = parser.parse_args()
    return asyncio.run(run_test(keep_db=args.keep_db))


if __name__ == "__main__":
    raise SystemExit(main())
