"""Diagnose knowledge RAG filter stages on the 30-case eval set.

For each query, dump every Chroma neighbor with similarity/overlap, then
record which stage dropped it: min_score, score_margin, lexical, top_k.

Also runs small ablations (no lexical / wider margin / top_k=3) on the
same embeddings so later planning can see what the current knobs cost.

Usage (from backend/):
  python scripts/diagnose_knowledge_rag.py
  python scripts/diagnose_knowledge_rag.py --json-out logs/rag_diagnose.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

from app.config import load_config  # noqa: E402
from app.knowledge import (  # noqa: E402
    KnowledgeRetriever,
    ScoredKnowledgeHit,
    _lexical_tokens,
    filter_knowledge_hits,
    ingest_corpus,
)
from eval_knowledge_rag import CASES, _evaluate_case, _known_titles  # noqa: E402

DROP_MIN = "min_score"
DROP_MARGIN = "score_margin"
DROP_LEX = "lexical_zero_overlap"
DROP_TOPK = "top_k_cut"
KEPT = "kept"


def _stage_drop_reasons(
    raw: list[ScoredKnowledgeHit],
    *,
    min_score: float,
    score_margin: float,
    top_k: int,
) -> dict[str, str]:
    """Map title -> first stage that dropped it (or kept)."""
    reasons: dict[str, str] = {h.title: DROP_MIN for h in raw}
    passed = [h for h in raw if h.similarity >= min_score]
    for hit in passed:
        reasons[hit.title] = DROP_MARGIN
    if not passed:
        return reasons
    passed.sort(key=lambda h: (-h.similarity, -h.overlap, h.title))
    top_score = passed[0].similarity
    in_margin = [h for h in passed if h.similarity >= top_score - max(0.0, score_margin)]
    for hit in in_margin:
        reasons[hit.title] = DROP_LEX
    if in_margin:
        lexical_kept = [in_margin[0]]
        reasons[in_margin[0].title] = DROP_TOPK
        for hit in in_margin[1:]:
            if hit.overlap > 0:
                lexical_kept.append(hit)
                reasons[hit.title] = DROP_TOPK
            else:
                reasons[hit.title] = DROP_LEX
        final = lexical_kept[: max(1, int(top_k))]
        for hit in final:
            reasons[hit.title] = KEPT
        for hit in lexical_kept[max(1, int(top_k)) :]:
            reasons[hit.title] = DROP_TOPK
    return reasons


def _collect_raw(
    retriever: KnowledgeRetriever,
    query: str,
) -> tuple[list[ScoredKnowledgeHit], list[str]]:
    retriever._ensure_backend()
    assert retriever._collection is not None and retriever._encoder is not None
    count = int(retriever._collection.count())
    n_results = max(1, count)
    q_emb = retriever._encoder.encode_query(query)
    result = retriever._collection.query(
        query_embeddings=[q_emb],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )
    documents = (result.get("documents") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    query_tokens = sorted(_lexical_tokens(query))
    raw: list[ScoredKnowledgeHit] = []
    for doc, dist, meta in zip(documents, distances, metadatas):
        similarity = 1.0 - float(dist)
        meta_dict = meta if isinstance(meta, dict) else {}
        title = str(meta_dict.get("title") or "").strip()
        body = str(meta_dict.get("body") or "").strip()
        text = f"{title}：{body}" if title and body else (body or (doc or "").strip())
        if not text:
            continue
        overlap = len(set(query_tokens) & _lexical_tokens(f"{title}\n{body or text}"))
        raw.append(
            ScoredKnowledgeHit(
                similarity=similarity,
                title=title or text[:40],
                text=text,
                overlap=overlap,
            )
        )
    raw.sort(key=lambda h: (-h.similarity, -h.overlap, h.title))
    return raw, query_tokens


def _pack_hits(hits: list[ScoredKnowledgeHit]) -> list[dict[str, object]]:
    return [
        {
            "title": h.title,
            "similarity": round(h.similarity, 4),
            "overlap": h.overlap,
        }
        for h in hits
    ]


def _eval_from_hits(
    case: dict[str, object],
    hits: list[ScoredKnowledgeHit],
    known: list[str],
    top_k: int,
) -> dict[str, object]:
    result = _evaluate_case(
        case=case,
        hit_texts=[h.text for h in hits],
        known=known,
        top_k=top_k,
    )
    return {
        "ok": result.ok,
        "note": result.note,
        "hit_titles": result.hit_titles,
        "fp": result.fp,
        "fn": result.fn,
        "precision": result.precision,
        "recall": result.recall,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json-out",
        type=Path,
        default=BACKEND_DIR / "logs" / "rag_diagnose.json",
    )
    args = parser.parse_args()

    config = load_config()
    try:
        n = ingest_corpus(config, rebuild=False)
        print(f"ingest ensured: {n} chunks")
    except Exception as exc:
        print(f"FAIL: ingest: {exc}", file=sys.stderr)
        return 1

    config.knowledge.enabled = True
    config.knowledge.query_cache_enabled = False
    retriever = KnowledgeRetriever(config)
    known = _known_titles(config.knowledge_corpus_abs_path)
    min_score = float(config.knowledge.min_score)
    margin = float(config.knowledge.score_margin)
    top_k = int(config.knowledge.retrieve_top_k)

    ablations = {
        "current": {"min_score": min_score, "score_margin": margin, "top_k": top_k},
        "no_lexical": {"min_score": min_score, "score_margin": margin, "top_k": top_k, "lexical": False},
        "margin_0.15": {"min_score": min_score, "score_margin": 0.15, "top_k": top_k},
        "top_k_3": {"min_score": min_score, "score_margin": margin, "top_k": 3},
        "min_score_0.50": {"min_score": 0.50, "score_margin": margin, "top_k": top_k},
    }

    cases_out: list[dict[str, object]] = []
    problem_counter: dict[str, int] = {}

    print(
        f"min_score={min_score} score_margin={margin} top_k={top_k} chunks={len(known)}"
    )
    print()

    for case in CASES:
        query = str(case["query"])
        raw, q_tokens = _collect_raw(retriever, query)
        reasons = _stage_drop_reasons(
            raw, min_score=min_score, score_margin=margin, top_k=top_k
        )
        current_hits = filter_knowledge_hits(
            raw, min_score=min_score, score_margin=margin, top_k=top_k
        )
        current_eval = _eval_from_hits(case, current_hits, known, top_k)
        expect = [str(t) for t in (case.get("expect") or [])]

        gold_trace: list[dict[str, object]] = []
        for title in expect:
            hit = next((h for h in raw if h.title == title), None)
            gold_trace.append(
                {
                    "title": title,
                    "similarity": round(hit.similarity, 4) if hit else None,
                    "overlap": hit.overlap if hit else None,
                    "drop": reasons.get(title, "not_in_candidates"),
                }
            )

        false_trace: list[dict[str, object]] = []
        for hit in current_hits:
            if hit.title not in set(expect):
                false_trace.append(
                    {
                        "title": hit.title,
                        "similarity": round(hit.similarity, 4),
                        "overlap": hit.overlap,
                        "drop": KEPT,
                    }
                )

        ablation_eval: dict[str, dict[str, object]] = {}
        for name, spec in ablations.items():
            hits = list(raw)
            if spec.get("lexical", True) is False:
                boosted = [
                    ScoredKnowledgeHit(h.similarity, h.title, h.text, max(h.overlap, 1))
                    for h in hits
                ]
                hits = boosted
            filtered = filter_knowledge_hits(
                hits,
                min_score=float(spec["min_score"]),
                score_margin=float(spec["score_margin"]),
                top_k=int(spec["top_k"]),
            )
            ablation_eval[name] = _eval_from_hits(
                case, filtered, known, int(spec["top_k"])
            )
            ablation_eval[name]["hit_titles"] = [h.title for h in filtered]

        row = {
            "id": case["id"],
            "bucket": case["bucket"],
            "query": query,
            "query_tokens": q_tokens,
            "expect": expect,
            "current": current_eval,
            "gold_trace": gold_trace,
            "false_kept": false_trace,
            "candidates": [
                {
                    "title": h.title,
                    "similarity": round(h.similarity, 4),
                    "overlap": h.overlap,
                    "drop": reasons.get(h.title, DROP_MIN),
                }
                for h in raw
            ],
            "ablation": ablation_eval,
        }
        cases_out.append(row)

        note = str(current_eval["note"])
        problem_counter[note] = problem_counter.get(note, 0) + 1
        mark = "PASS" if current_eval["ok"] else "FAIL"
        print(f"[{mark}] {case['id']} {note} tokens={q_tokens}")
        print(f"  Q: {query}")
        print(f"  expect={expect} hits={current_eval['hit_titles']}")
        if gold_trace:
            print(
                "  gold:",
                ", ".join(
                    f"{g['title']} sim={g['similarity']} ov={g['overlap']} {g['drop']}"
                    for g in gold_trace
                ),
            )
        if false_trace:
            print(
                "  false_kept:",
                ", ".join(
                    f"{g['title']} sim={g['similarity']} ov={g['overlap']}"
                    for g in false_trace
                ),
            )
        dropped_gold = [g for g in gold_trace if g["drop"] != KEPT]
        if dropped_gold:
            print(
                "  drop_gold:",
                ", ".join(f"{g['title']}->{g['drop']}" for g in dropped_gold),
            )
        print()

    ablation_summary: dict[str, dict[str, int]] = {}
    for name in ablations:
        ok_n = sum(1 for row in cases_out if row["ablation"][name]["ok"])
        ablation_summary[name] = {
            "pass": ok_n,
            "fail": len(cases_out) - ok_n,
        }

    drop_gold_counts: dict[str, int] = {}
    for row in cases_out:
        for g in row["gold_trace"]:
            if g["drop"] != KEPT:
                key = str(g["drop"])
                drop_gold_counts[key] = drop_gold_counts.get(key, 0) + 1

    payload = {
        "config": {
            "min_score": min_score,
            "score_margin": margin,
            "retrieve_top_k": top_k,
            "titles": known,
        },
        "notes": problem_counter,
        "gold_drop_stages": drop_gold_counts,
        "ablation_pass": ablation_summary,
        "cases": cases_out,
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("=== notes ===")
    for key, value in sorted(problem_counter.items()):
        print(f"  {key}: {value}")
    print("=== gold dropped by stage ===")
    for key, value in sorted(drop_gold_counts.items()):
        print(f"  {key}: {value}")
    print("=== ablation pass/30 ===")
    for name, stats in ablation_summary.items():
        print(f"  {name}: {stats['pass']}/30")
    print(f"\njson: {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
