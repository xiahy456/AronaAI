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
from app.embeddings import cosine_similarity  # noqa: E402
from app.knowledge import (  # noqa: E402
    KnowledgeRetriever,
    ScoredKnowledgeHit,
    SemanticHitCache,
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


def _test_query_cache_unit() -> list[str]:
    failures: list[str] = []
    if cosine_similarity([1.0, 0.0], [1.0, 0.0]) != 1.0:
        failures.append("cosine_similarity identical vectors")
    if cosine_similarity([1.0, 0.0], [0.0, 1.0]) != 0.0:
        failures.append("cosine_similarity orthogonal vectors")
    if cosine_similarity([1.0], [1.0, 0.0]) != 0.0:
        failures.append("cosine_similarity length mismatch")

    cache = SemanticHitCache(size=2, min_cosine=0.92)
    vec_a = [1.0, 0.0]
    vec_near = [0.96, 0.28]  # cosine ~ 0.96
    vec_far = [0.0, 1.0]
    cache.put(vec_a, ["lore-a"], top_k=2, collection_n=5)

    hit = cache.get(vec_a, top_k=2, collection_n=5)
    if hit is None or hit[0] != ["lore-a"]:
        failures.append(f"exact embedding hit: {hit}")

    near = cache.get(vec_near, top_k=2, collection_n=5)
    if near is None or near[0] != ["lore-a"]:
        failures.append(f"near embedding hit: {near}")

    if cache.get(vec_far, top_k=2, collection_n=5) is not None:
        failures.append("orthogonal embedding should miss")
    if cache.get(vec_a, top_k=3, collection_n=5) is not None:
        failures.append("different top_k should miss")
    if cache.get(vec_a, top_k=2, collection_n=9) is not None:
        failures.append("different collection_n should miss")

    cache.put([0.0, 1.0], ["lore-b"], top_k=2, collection_n=5)
    cache.put([0.7, 0.7], ["lore-c"], top_k=2, collection_n=5)
    if len(cache) != 2:
        failures.append(f"LRU size: expected 2, got {len(cache)}")
    if cache.get(vec_a, top_k=2, collection_n=5) is not None:
        failures.append("LRU should evict oldest entry")

    cache.clear()
    if len(cache) != 0 or cache.get(vec_far, top_k=2, collection_n=5) is not None:
        failures.append("clear should empty cache")
    return failures


class _CountingEncoder:
    def __init__(self) -> None:
        self.n = 0

    def encode_queries(self, texts: list[str]) -> list[list[float]]:
        self.n += 1
        return [[1.0, 0.0] for _ in texts]

    def encode_query(self, text: str) -> list[float]:
        return self.encode_queries([text])[0]

    def encode_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


class _FakeCollection:
    def count(self) -> int:
        return 1

    def query(self, **kwargs):  # noqa: ANN003
        return {"documents": [[]], "distances": [[]], "metadatas": [[]]}


def _test_retrieve_uses_provided_embedding(config) -> list[str]:
    failures: list[str] = []
    encoder = _CountingEncoder()
    retriever = KnowledgeRetriever(config, encoder=encoder)
    retriever.enabled = True
    retriever._encoder = encoder
    retriever._collection = _FakeCollection()
    original_cache = bool(retriever.config.query_cache_enabled)
    try:
        retriever.config.query_cache_enabled = False

        provided = [1.0, 0.0]
        retriever.retrieve("阿洛娜是谁", top_k=2, query_embedding=provided)
        retriever.retrieve("阿洛娜是谁", top_k=2, query_embedding=provided)
        if encoder.n != 0:
            failures.append(
                f"provided embedding should skip encode, got encode_queries={encoder.n}"
            )

        retriever.retrieve("阿洛娜是谁", top_k=2)
        if encoder.n != 1:
            failures.append(
                f"missing embedding should encode once, got encode_queries={encoder.n}"
            )

        retriever.config.query_cache_enabled = True
        retriever._query_cache.clear()
        encoder.n = 0
        retriever.retrieve("重复问题", top_k=2, query_embedding=provided)
        retriever.retrieve("近义问题", top_k=2, query_embedding=provided)
        if encoder.n != 0:
            failures.append("cached retrieve with provided embedding encoded")
        if len(retriever._query_cache) != 1:
            failures.append(
                f"cache size after put+hit: expected 1, got {len(retriever._query_cache)}"
            )

        retriever._query_cache.clear()
        if len(retriever._query_cache) != 0:
            failures.append("ingest-style clear left entries")
    finally:
        retriever.config.query_cache_enabled = original_cache
    return failures


def main() -> int:
    config = load_config()
    failures: list[str] = []
    failures.extend(_test_filter_unit())
    failures.extend(_test_clip_unit(config))
    failures.extend(_test_query_cache_unit())
    failures.extend(_test_retrieve_uses_provided_embedding(config))
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
