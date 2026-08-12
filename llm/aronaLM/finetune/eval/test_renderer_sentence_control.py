#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test Renderer V2.2 sentence-length control (target: 1–2 sentences).

Loads production-like GGUF + renderer system / intent-card prompt, generates
replies, and scores only sentence count (plus optional empty check).

Examples:
  python eval/test_renderer_sentence_control.py
  python eval/test_renderer_sentence_control.py --gguf ../../../models/AronaLM-Renderer-V2.2/AronaLM-Renderer-V2.2.Q4_K_M.gguf
  python eval/test_renderer_sentence_control.py --compare-v21
  python eval/test_renderer_sentence_control.py --repeats 3 --seed 42
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

FINETUNE_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = FINETUNE_ROOT.parents[2]
sys.path.insert(0, str(FINETUNE_ROOT / "data-process"))
from renderer_format import format_human, load_renderer_system  # noqa: E402

CASES_PATH = Path(__file__).resolve().parent / "sentence_control_cases.json"
REPORTS_DIR = Path(__file__).resolve().parent / "reports"
DEFAULT_V22 = REPO_ROOT / "models" / "AronaLM-Renderer-V2.2" / "AronaLM-Renderer-V2.2.Q4_K_M.gguf"
DEFAULT_V21 = REPO_ROOT / "models" / "AronaLM-Renderer-V2.1" / "AronaLM-Renderer-V2.1.Q4_K_M.gguf"


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def clean_reply(text: str) -> str:
    """Match backend model_loader.clean_model_output (think strip only)."""
    return _THINK_RE.sub("", text or "").strip()


def sentence_count(text: str) -> int:
    t = clean_reply(text)
    if not t:
        return 0
    parts = [p for p in re.split(r"(?<=[。！？!?~～])\s*", t) if p.strip()]
    return len(parts) if parts else 1


def resolve_gguf(path: Path) -> Path:
    if path.is_file():
        return path.resolve()
    alt = (FINETUNE_ROOT / path).resolve()
    if alt.is_file():
        return alt
    raise FileNotFoundError(path)


def load_llm(gguf: Path, n_ctx: int = 2048, n_gpu_layers: int = -1):
    from llama_cpp import Llama

    return Llama(
        model_path=str(gguf),
        n_ctx=n_ctx,
        n_gpu_layers=n_gpu_layers,
        verbose=False,
    )


def generate(
    llm,
    user_payload: str,
    *,
    max_tokens: int,
    temperature: float,
    top_p: float,
    seed: int | None,
) -> str:
    kwargs = {
        "messages": [
            {"role": "system", "content": load_renderer_system()},
            {"role": "user", "content": user_payload},
        ],
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
    }
    if seed is not None:
        kwargs["seed"] = seed
    out = llm.create_chat_completion(**kwargs)
    raw = (out["choices"][0]["message"]["content"] or "").strip()
    return clean_reply(raw)


def score_length(reply: str, expect: dict) -> tuple[bool, list[str], int]:
    fails: list[str] = []
    n = sentence_count(reply)
    if not (reply or "").strip():
        return False, ["empty_reply"], 0
    max_sents = int(expect.get("max_sentences", 2))
    min_sents = int(expect.get("min_sentences", 1))
    if n > max_sents:
        fails.append(f"too_many_sentences:{n}>{max_sents}")
    if n < min_sents:
        fails.append(f"too_few_sentences:{n}<{min_sents}")
    return len(fails) == 0, fails, n


def run_suite(
    llm,
    cases: list[dict],
    *,
    max_tokens: int,
    temperature: float,
    top_p: float,
    repeats: int,
    base_seed: int | None,
) -> dict:
    rows: list[dict] = []
    passed = 0
    total = 0
    sent_hist: Counter[int] = Counter()

    for case in cases:
        human = format_human(case["user_text"], case["intent_card"])
        expect = case.get("expect") or {}
        for r_i in range(repeats):
            seed = None if base_seed is None else base_seed + total
            reply = generate(
                llm,
                human,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                seed=seed,
            )
            ok, fails, n_sent = score_length(reply, expect)
            passed += int(ok)
            total += 1
            sent_hist[n_sent] += 1
            row = {
                "id": case["id"],
                "repeat": r_i,
                "category": case.get("category"),
                "user_text": case["user_text"],
                "reply": reply,
                "sentences": n_sent,
                "pass": ok,
                "fails": fails,
            }
            rows.append(row)
            status = "PASS" if ok else "FAIL"
            preview = reply.replace("\n", " ")
            if len(preview) > 72:
                preview = preview[:72] + "..."
            print(f"[{status}] {case['id']} r{r_i} sents={n_sent}: {preview}")
            if fails:
                print(f"       fails={fails}")

    rate = passed / total if total else 0.0
    return {
        "passed": passed,
        "total": total,
        "pass_rate": rate,
        "sentence_histogram": {str(k): v for k, v in sorted(sent_hist.items())},
        "avg_sentences": (sum(r["sentences"] for r in rows) / total) if total else 0.0,
        "overlong": [r for r in rows if any(f.startswith("too_many") for f in r["fails"])],
        "cases": rows,
    }


def write_report(tag: str, gguf: Path, meta: dict, result: dict) -> tuple[Path, Path]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    payload = {
        "tag": tag,
        "gguf": str(gguf),
        **meta,
        **{k: v for k, v in result.items() if k != "overlong"},
        "overlong_ids": [f"{r['id']}#r{r['repeat']}" for r in result["overlong"]],
    }
    out_json = REPORTS_DIR / f"sentence_control_{tag}_{stamp}.json"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    hist = result["sentence_histogram"]
    hist_line = ", ".join(f"{k}句×{v}" for k, v in hist.items()) or "(empty)"
    md = [
        f"# Sentence control `{tag}`",
        "",
        f"- GGUF: `{gguf}`",
        f"- Pass (≤2 sentences): **{result['passed']}/{result['total']}** ({result['pass_rate']:.0%})",
        f"- Avg sentences: **{result['avg_sentences']:.2f}**",
        f"- Histogram: {hist_line}",
        f"- max_tokens={meta['max_tokens']} temperature={meta['temperature']} repeats={meta['repeats']}",
        "",
        "| id | r | sents | pass | reply | fails |",
        "|---|---:|---:|---|---|---|",
    ]
    for r in result["cases"]:
        reply_esc = (r["reply"] or "").replace("|", "\\|").replace("\n", " ")
        md.append(
            f"| {r['id']} | {r['repeat']} | {r['sentences']} | "
            f"{'Y' if r['pass'] else 'N'} | {reply_esc} | {','.join(r['fails'])} |"
        )
    out_md = REPORTS_DIR / f"sentence_control_{tag}_{stamp}.md"
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")
    return out_json, out_md


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=CASES_PATH)
    parser.add_argument("--gguf", type=Path, default=DEFAULT_V22)
    parser.add_argument("--compare-v21", action="store_true", help="Also run V2.1 and print side-by-side rates")
    parser.add_argument("--v21-gguf", type=Path, default=DEFAULT_V21)
    parser.add_argument("--tag", type=str, default="v22")
    parser.add_argument("--max-tokens", type=int, default=72, help="Align with backend max_new_tokens")
    parser.add_argument("--temperature", type=float, default=0.6)
    parser.add_argument("--top-p", type=float, default=0.85)
    parser.add_argument("--repeats", type=int, default=1, help="Repeat each case (stochastic stress)")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--n-gpu-layers", type=int, default=-1)
    parser.add_argument("--pass-threshold", type=float, default=0.85, help="Exit 1 if pass_rate below this")
    args = parser.parse_args()

    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    if args.seed is not None:
        random.seed(args.seed)

    meta = {
        "cases_path": str(args.cases.resolve()),
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
        "top_p": args.top_p,
        "repeats": args.repeats,
        "seed": args.seed,
    }

    gguf = resolve_gguf(args.gguf)
    print(f"Loading {gguf} ...")
    llm = load_llm(gguf, n_gpu_layers=args.n_gpu_layers)
    result = run_suite(
        llm,
        cases,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        top_p=args.top_p,
        repeats=args.repeats,
        base_seed=args.seed,
    )
    del llm

    out_json, out_md = write_report(args.tag, gguf, meta, result)
    print(
        f"\n[{args.tag}] Pass {result['passed']}/{result['total']} "
        f"({result['pass_rate']:.0%}) avg_sents={result['avg_sentences']:.2f} "
        f"hist={result['sentence_histogram']}"
    )
    print(f"Wrote {out_json}")
    print(f"Wrote {out_md}")

    if args.compare_v21:
        v21 = resolve_gguf(args.v21_gguf)
        print(f"\nLoading compare {v21} ...")
        llm21 = load_llm(v21, n_gpu_layers=args.n_gpu_layers)
        result21 = run_suite(
            llm21,
            cases,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            top_p=args.top_p,
            repeats=args.repeats,
            base_seed=args.seed,
        )
        del llm21
        j21, m21 = write_report("v21", v21, meta, result21)
        print(
            f"\n[v21] Pass {result21['passed']}/{result21['total']} "
            f"({result21['pass_rate']:.0%}) avg_sents={result21['avg_sentences']:.2f} "
            f"hist={result21['sentence_histogram']}"
        )
        print(f"Wrote {j21}")
        print(f"Wrote {m21}")
        print(
            f"\nA/B: v22 {result['pass_rate']:.0%} (avg {result['avg_sentences']:.2f}) "
            f"vs v21 {result21['pass_rate']:.0%} (avg {result21['avg_sentences']:.2f})"
        )

    if result["pass_rate"] < args.pass_threshold:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
