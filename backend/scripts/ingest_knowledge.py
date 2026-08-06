"""Ingest Markdown knowledge corpus into Chroma (local BGE embeddings)."""

from __future__ import annotations

import argparse
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
from app.knowledge import ingest_corpus  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest knowledge corpus into Chroma")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Delete existing collection and rebuild from corpus",
    )
    args = parser.parse_args()

    config = load_config()
    print(f"corpus:    {config.knowledge_corpus_abs_path}")
    print(f"chroma:    {config.knowledge_chroma_abs_path}")
    print(f"embedding: {config.knowledge_embedding_abs_path}")
    print(f"collection:{config.knowledge.collection}")
    print(f"rebuild:   {args.rebuild}")

    try:
        count = ingest_corpus(config, rebuild=args.rebuild)
    except FileNotFoundError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"FAIL: ingest error: {exc}", file=sys.stderr)
        return 1

    print(f"OK: upserted {count} chunks")
    return 0 if count > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
