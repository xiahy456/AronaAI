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
from app.knowledge import KnowledgeRetriever, ingest_corpus  # noqa: E402

QUERIES = [
    ("你是谁", ("阿洛娜", "操作系统")),
    ("什亭之匣是什么", ("什亭之匣", "Shittim")),
    ("基沃托斯是什么地方", ("基沃托斯", "学园")),
]


def main() -> int:
    config = load_config()
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

    failures: list[str] = []
    for query, keywords in QUERIES:
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

    if failures:
        print("\nFAIL:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print("\nPASS: knowledge RAG retrieval looks good.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
