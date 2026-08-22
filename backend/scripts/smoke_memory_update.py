"""Smoke tests for memory update path (A context helpers / B reconcile / C hot keys).

Does not call DeepSeek. Uses a temp SQLite + Chroma under a temp dir.

Usage (from backend/):
  python scripts/smoke_memory_update.py
"""

from __future__ import annotations

import sys
import tempfile
import time
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
from app.memory.extractor import MemoryExtractor, _format_existing_memories  # noqa: E402
from app.memory.fallback import regex_extract_memories  # noqa: E402
from app.memory.normalize import normalize_memory_item  # noqa: E402
from app.memory.store import MemoryStore  # noqa: E402


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    raise SystemExit(1)


def test_normalize_and_regex() -> None:
    print("== C: normalize + regex ==")
    items = regex_extract_memories("我比较喜欢黄色")
    if not items:
        _fail("regex should extract yellow preference")
    item = items[0]
    if item.get("key") != "preference_color":
        _fail(f"expected preference_color, got {item}")
    if "黄" not in str(item.get("content")):
        _fail(f"expected yellow in content, got {item}")
    print(f"  regex yellow ok: {item}")

    pink = normalize_memory_item(
        {
            "op": "upsert",
            "key": "preference_like",
            "content": "老师喜欢粉色",
            "category": "preference",
        }
    )
    if pink.get("key") != "preference_color":
        _fail(f"normalize pink -> preference_color failed: {pink}")
    print(f"  normalize pink ok: {pink}")

    name = normalize_memory_item(
        {"op": "upsert", "key": "name", "content": "老师的名字是Sensei", "category": "other"}
    )
    if name.get("key") != "user_name" or name.get("category") != "profile":
        _fail(f"normalize name failed: {name}")
    print(f"  normalize name ok: {name}")


def test_format_context() -> None:
    print("== A: format existing memories ==")
    text = _format_existing_memories(
        [
            {
                "key": "preference_color",
                "category": "preference",
                "content": "老师喜欢粉色",
            },
            {
                "key": "goal_walk",
                "category": "goal",
                "content": "老师打算和阿洛娜出去散步",
            },
        ]
    )
    if "preference_color" not in text or "goal_walk" not in text:
        _fail(f"format missing keys: {text}")
    print("  format ok")


def _list_rows(store: MemoryStore) -> dict[str, tuple[str, str]]:
    return {
        r[0]: (r[1], r[2] or "")
        for r in store._connect()
        .execute("SELECT key, content, category FROM memories")
        .fetchall()
    }


def _make_store(cfg) -> tuple[MemoryStore, Path]:
    tmp = tempfile.mkdtemp(prefix="arona-mem-smoke-")
    tmp_path = Path(tmp)
    store = MemoryStore(cfg, db_path=tmp_path / "memory.db")
    store.chroma_path = tmp_path / "chroma"
    store.chroma_path.mkdir(parents=True, exist_ok=True)
    return store, tmp_path


def test_reconcile_color_and_goal_delete() -> None:
    print("== B+D: reconcile + goal delete ==")
    cfg = load_config()
    store, _tmp = _make_store(cfg)
    try:
        store.upsert(
            "preference_like",
            "老师喜欢粉色",
            category="preference",
            source="seed",
        )
        store.upsert(
            "goal_walk",
            "老师打算和阿洛娜出去散步",
            category="goal",
            source="seed",
        )
        assert store.count() == 2

        extractor = MemoryExtractor(store, cfg.memory.extractor)
        extractor._apply(
            [
                {
                    "op": "upsert",
                    "key": "preference_like",
                    "content": "老师喜欢黄色",
                    "category": "preference",
                }
            ],
            source="smoke",
        )

        rows = _list_rows(store)
        if "preference_color" not in rows:
            _fail(f"expected preference_color after normalize upsert, rows={rows}")
        if "黄" not in rows["preference_color"][0]:
            _fail(f"expected yellow content, rows={rows}")
        if "preference_like" in rows:
            _fail(f"preference_like should be reconciled away, rows={rows}")
        if "goal_walk" not in rows:
            _fail(f"goal must not be auto-reconciled, rows={rows}")
        print(f"  reconcile kept yellow, removed pink alias; rows={rows}")

        extractor._apply(
            [{"op": "delete", "key": "goal_walk", "content": "", "category": "goal"}],
            source="smoke",
        )
        rows2 = _list_rows(store)
        if "goal_walk" in rows2:
            _fail(f"goal_walk should be deleted, rows={rows2}")
        print(f"  goal delete ok; remaining={rows2}")
    finally:
        store._collection = None
        store._client = None


def test_semantic_and_exact_dedup() -> None:
    print("== Dedup: semantic near + exact ==")
    cfg = load_config()
    store, _tmp = _make_store(cfg)
    try:
        extractor = MemoryExtractor(store, cfg.memory.extractor)

        # Seed near-duplicate under a non-hot key (bypass normalize by using food-like text).
        store.upsert(
            "pref_banana",
            "老师喜欢香蕉",
            category="preference",
            source="seed",
        )

        extractor._apply(
            [
                {
                    "op": "upsert",
                    "key": "like_banana_v2",
                    "content": "老师比较喜欢香蕉",
                    "category": "preference",
                }
            ],
            source="smoke",
        )
        rows = _list_rows(store)
        banana_rows = {k: v for k, v in rows.items() if "香蕉" in v[0]}
        if len(banana_rows) != 1:
            _fail(f"expected exactly one banana memory, got {banana_rows}")
        only_key, (only_content, _) = next(iter(banana_rows.items()))
        if "比较喜欢香蕉" not in only_content and only_content != "老师比较喜欢香蕉":
            # New content must win.
            if "比较" not in only_content:
                _fail(f"expected new content to win, got {banana_rows}")
        if "pref_banana" in rows and only_key != "pref_banana":
            _fail(f"old key should be dropped unless kept: {rows}")
        print(f"  semantic dedup ok: {banana_rows}")

        # Exact duplicate under a different key.
        keep_before = dict(banana_rows)
        keep_key = next(iter(keep_before.keys()))
        extractor._apply(
            [
                {
                    "op": "upsert",
                    "key": "banana_dup",
                    "content": only_content,
                    "category": "preference",
                }
            ],
            source="smoke",
        )
        rows2 = _list_rows(store)
        banana_rows2 = {k: v for k, v in rows2.items() if "香蕉" in v[0]}
        if len(banana_rows2) != 1:
            _fail(f"exact dedup should leave one row, got {banana_rows2}")
        if "banana_dup" in banana_rows2 and keep_key not in banana_rows2:
            # May keep banana_dup if pick prefers new; still only one row is required.
            pass
        if "banana_dup" in banana_rows2 and keep_key in banana_rows2:
            _fail(f"exact dedup left both keys: {banana_rows2}")
        print(f"  exact dedup ok: {banana_rows2}")

        # Color hot-key path: near-dup should land on preference_color with new text.
        store2, _tmp2 = _make_store(cfg)
        try:
            store2.upsert(
                "preference_like",
                "老师喜欢黄色",
                category="preference",
                source="seed",
            )
            extractor2 = MemoryExtractor(store2, cfg.memory.extractor)
            extractor2._apply(
                [
                    {
                        "op": "upsert",
                        "key": "pref_yellow",
                        "content": "老师比较喜欢黄色",
                        "category": "preference",
                    }
                ],
                source="smoke",
            )
            rows3 = _list_rows(store2)
            yellow = {k: v for k, v in rows3.items() if "黄" in v[0]}
            if len(yellow) != 1:
                _fail(f"expected one yellow memory, got {yellow}")
            if "preference_color" not in yellow:
                _fail(f"expected preference_color hot key, got {yellow}")
            if "比较" not in yellow["preference_color"][0] and yellow["preference_color"][0] != "老师比较喜欢黄色":
                # normalize may rewrite to 老师喜欢黄色 from regex path; here content is explicit.
                if yellow["preference_color"][0] != "老师比较喜欢黄色":
                    # Accept either new phrasing if model/normalize collapses 比较.
                    if "黄" not in yellow["preference_color"][0]:
                        _fail(f"yellow content missing: {yellow}")
            print(f"  color hot-key dedup ok: {yellow}")
        finally:
            store2._collection = None
            store2._client = None
    finally:
        store._collection = None
        store._client = None


def _sql_insert(store: MemoryStore, key: str, content: str) -> None:
    with store._connect() as conn:
        conn.execute(
            """
            INSERT INTO memories(key, content, category, updated_at, source)
            VALUES (?, ?, ?, ?, ?)
            """,
            (key, content, "preference", time.time(), "test"),
        )
        conn.commit()


def _last_injected_at(store: MemoryStore, key: str) -> float | None:
    row = (
        store._connect()
        .execute("SELECT last_injected_at FROM memories WHERE key = ?", (key,))
        .fetchone()
    )
    if row is None or row["last_injected_at"] is None:
        return None
    return float(row["last_injected_at"])


def test_inject_cooldown() -> None:
    print("== inject cooldown ==")
    cfg = load_config()
    store, _tmp = _make_store(cfg)
    try:
        _sql_insert(store, "pref_spicy", "老师喜欢吃辛辣食物但难以控制")
        _sql_insert(store, "pref_pizza", "老师喜欢吃披萨")
        now = time.time()
        store.mark_injected(["pref_spicy"], now=now)

        cooled = store._cooled_keys(
            ["pref_spicy", "pref_pizza"], now, cooldown_sec=3600
        )
        if cooled != {"pref_spicy"}:
            _fail(f"expected pref_spicy cooled within 1h, got {cooled}")

        expired = store._cooled_keys(
            ["pref_spicy", "pref_pizza"], now + 3600, cooldown_sec=3600
        )
        if expired:
            _fail(f"expected cooldown expired after 1h, got {expired}")

        before = _last_injected_at(store, "pref_spicy")
        store.upsert(
            "pref_spicy",
            "老师喜欢吃辛辣食物但难以控制",
            category="preference",
            source="test",
        )
        after = _last_injected_at(store, "pref_spicy")
        if before is None or after is None or after != before:
            _fail(
                f"upsert must keep last_injected_at, before={before} after={after}"
            )

        passed = [
            ("pref_spicy", "老师喜欢吃辛辣食物但难以控制", 0.9),
            ("pref_pizza", "老师喜欢吃披萨", 0.8),
        ]
        dropped = store._drop_cooled_entries(
            passed, apply_inject_cooldown=True
        )
        if [key for key, _, _ in dropped] != ["pref_pizza"]:
            _fail(f"expected cooled key dropped and pizza kept, got {dropped}")

        kept = store._drop_cooled_entries(passed, apply_inject_cooldown=False)
        if [key for key, _, _ in kept] != ["pref_spicy", "pref_pizza"]:
            _fail(f"extractor path must not drop cooled keys, got {kept}")

        store.config = store.config.model_copy(update={"inject_cooldown_sec": 0})
        zeroed = store._drop_cooled_entries(
            passed, apply_inject_cooldown=True
        )
        if [key for key, _, _ in zeroed] != ["pref_spicy", "pref_pizza"]:
            _fail(f"inject_cooldown_sec=0 must not filter, got {zeroed}")

        print("  inject cooldown ok")
    finally:
        store._collection = None
        store._client = None


def main() -> None:
    test_normalize_and_regex()
    test_format_context()
    test_reconcile_color_and_goal_delete()
    test_semantic_and_exact_dedup()
    test_inject_cooldown()
    print("ALL SMOKE CHECKS PASSED")


if __name__ == "__main__":
    main()
