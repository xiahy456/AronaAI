"""Smoke test for knowledge RAG retrieval (local BGE + Chroma)."""

from __future__ import annotations

import sys
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
from app.knowledge import (  # noqa: E402
    KnowledgeRetriever,
    ScoredKnowledgeHit,
    filter_knowledge_hits,
    ingest_corpus,
)
from app.prompt import clip_inject_chunks, clip_knowledge_for_inject  # noqa: E402

POSITIVE_QUERIES = [
    ("阿洛娜是谁", ("阿洛娜", "操作系统")),
    ("什亭之匣是什么", ("什亭之匣", "Shittim")),
    ("基沃托斯是什么地方", ("基沃托斯", "学园")),
    ("阿洛娜的光环是什么颜色", ("光环", "圆环")),
]

OFFTOPIC_QUERY = "平时我不在的时候，阿洛娜在做什么呢"
OFFTOPIC_FORBIDDEN = ("服装", "内裤", "光环")

CHITCHAT_QUERIES = [
    "啊，抱歉，突然有任务要做了",
    "今天有一点点忙",
]


def _test_filter_unit() -> list[str]:
    failures: list[str] = []
    extras = filter_knowledge_hits(
        [
            ScoredKnowledgeHit(0.62, "职责", "职责：协助日常事务", overlap=1),
            ScoredKnowledgeHit(0.58, "服装", "服装：白色发带与内裤", overlap=0),
            ScoredKnowledgeHit(0.57, "光环", "光环：蓝色圆环", overlap=0),
        ],
        min_score=0.45,
        score_margin=0.08,
        top_k=2,
    )
    titles = [h.title for h in extras]
    if titles != ["职责"]:
        failures.append(f"lexical extras: expected ['职责'], got {titles}")

    weak = filter_knowledge_hits(
        [
            ScoredKnowledgeHit(0.40, "身份", "身份：操作系统管理员", overlap=0),
        ],
        min_score=0.45,
        score_margin=0.08,
        top_k=2,
    )
    if weak:
        failures.append(f"min_score: expected empty, got {[h.title for h in weak]}")

    margin = filter_knowledge_hits(
        [
            ScoredKnowledgeHit(0.70, "职责", "职责：协助日常事务", overlap=2),
            ScoredKnowledgeHit(0.55, "身份", "身份：操作系统管理员", overlap=1),
        ],
        min_score=0.45,
        score_margin=0.08,
        top_k=2,
    )
    if [h.title for h in margin] != ["职责"]:
        failures.append(f"score_margin: expected ['职责'], got {[h.title for h in margin]}")

    top_only = filter_knowledge_hits(
        [
            ScoredKnowledgeHit(0.60, "职责", "职责：协助日常事务", overlap=0),
            ScoredKnowledgeHit(0.58, "服装", "服装：白色发带", overlap=0),
        ],
        min_score=0.45,
        score_margin=0.08,
        top_k=2,
    )
    if [h.title for h in top_only] != ["职责"]:
        failures.append(
            f"keep top-1 with zero overlap: expected ['职责'], got {[h.title for h in top_only]}"
        )
    return failures


def _test_clip_unit(config) -> list[str]:
    failures: list[str] = []
    clipped = clip_inject_chunks(["abc", "defghij"], 8)
    if clipped != ["abc"]:
        failures.append(f"clip_inject_chunks: expected ['abc'], got {clipped}")

    a = "知识块甲"
    b = "知识块乙补充说明"
    original = config.knowledge.max_inject_chars
    config.knowledge.max_inject_chars = len(f"- {a}") + 3
    try:
        kept = clip_knowledge_for_inject(config, [a, b])
    finally:
        config.knowledge.max_inject_chars = original
    if kept != [a]:
        failures.append(f"clip_knowledge_for_inject: expected {[a]}, got {kept}")
    return failures


def main() -> int:
    config = load_config()
    failures: list[str] = []
    failures.extend(_test_filter_unit())
    failures.extend(_test_clip_unit(config))
    if failures:
        print("FAIL: unit filters", file=sys.stderr)
        for item in failures:
            print(f"  - {item}", file=sys.stderr)
        return 1
    print("unit filters: ok")

    # Ensure collection exists even if user has not run ingest yet.
    try:
        n = ingest_corpus(config, rebuild=False)
        print(f"ingest ensured: {n} chunks")
    except Exception as exc:
        print(f"FAIL: ingest: {exc}", file=sys.stderr)
        return 1

    # Force-enable for this smoke test regardless of config flag.
    config.knowledge.enabled = True
    retriever = KnowledgeRetriever(config)

    for query, keywords in POSITIVE_QUERIES:
        hits = retriever.retrieve(query, top_k=config.knowledge.retrieve_top_k)
        print(f"\nQ: {query}")
        if not hits:
            print("  (no hits)")
            failures.append(f"{query!r}: no hits")
            continue
        for i, hit in enumerate(hits, 1):
            print(f"  {i}. {hit[:120]}{'…' if len(hit) > 120 else ''}")
        blob = "\n".join(hits)
        if not any(k in blob for k in keywords):
            failures.append(f"{query!r}: expected one of {keywords}")

    print(f"\nQ: {OFFTOPIC_QUERY}")
    off_hits = retriever.retrieve(OFFTOPIC_QUERY, top_k=config.knowledge.retrieve_top_k)
    if not off_hits:
        print("  (no hits)")
    else:
        for i, hit in enumerate(off_hits, 1):
            print(f"  {i}. {hit[:120]}{'…' if len(hit) > 120 else ''}")
    off_blob = "\n".join(off_hits)
    for banned in OFFTOPIC_FORBIDDEN:
        if banned in off_blob:
            failures.append(f"{OFFTOPIC_QUERY!r}: unexpected {banned!r}")

    for query in CHITCHAT_QUERIES:
        hits = retriever.retrieve(query, top_k=config.knowledge.retrieve_top_k)
        print(f"\nQ: {query}")
        if not hits:
            print("  (no hits)")
        else:
            for i, hit in enumerate(hits, 1):
                print(f"  {i}. {hit[:120]}{'…' if len(hit) > 120 else ''}")
            print("  note: chitchat hits are recorded, not a hard failure")

    if failures:
        print("\nFAIL:", file=sys.stderr)
        for item in failures:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print("\nPASS: knowledge RAG retrieval looks good.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
