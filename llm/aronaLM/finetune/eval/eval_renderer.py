#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rule-based Renderer hard-case eval (intent card -> reply).

Supports llama-cpp GGUF (production-like) or printing dry-run cards.

Examples:
  python eval/eval_renderer.py --gguf ../../../models/AronaLM-Generator-V2.0/AronaLM-Generator-V2.0.Q4_K_M.gguf
  python eval/eval_renderer.py --gguf ../../../models/AronaLM-Renderer-V2.1/AronaLM-Renderer-V2.1.Q4_K_M.gguf
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

FINETUNE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(FINETUNE_ROOT / "data-process"))
from renderer_format import format_human, load_renderer_system  # noqa: E402

CASES_PATH = Path(__file__).resolve().parent / "renderer_cases.json"
REPORTS_DIR = Path(__file__).resolve().parent / "reports"


def _choice_bounce(text: str) -> bool:
    if "话题单" in text:
        return True
    if "还是" in text and ("想聊" in text or "还是" in text and ("？" in text or "?" in text)):
        # heuristic: choice questions bouncing to teacher
        if any(x in text for x in ("想聊", "要不要", "还是选", "A、B", "还是C")):
            return True
    if "老师想聊" in text and ("还是" in text or "还是" in text):
        return True
    return "帮您列" in text


def score_reply(reply: str, expect: dict) -> tuple[bool, list[str]]:
    fails: list[str] = []
    reply = (reply or "").strip()
    if not reply:
        return False, ["empty_reply"]

    must_any = expect.get("must_contain_any") or []
    if must_any and not any(x in reply for x in must_any):
        fails.append(f"missing_any:{must_any}")

    for ban in expect.get("must_not_contain") or []:
        if ban and ban in reply:
            fails.append(f"banned:{ban}")

    if expect.get("forbid_choice_bounce") and _choice_bounce(reply):
        fails.append("choice_bounce")

    return len(fails) == 0, fails


def load_llm(gguf: Path, n_ctx: int = 2048):
    from llama_cpp import Llama

    return Llama(
        model_path=str(gguf),
        n_ctx=n_ctx,
        n_gpu_layers=-1,
        verbose=False,
    )


def generate(llm, user_payload: str, max_tokens: int = 128) -> str:
    system = load_renderer_system()
    out = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_payload},
        ],
        temperature=0.7,
        top_p=0.85,
        max_tokens=max_tokens,
    )
    return (out["choices"][0]["message"]["content"] or "").strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=CASES_PATH)
    parser.add_argument("--gguf", type=Path, required=True)
    parser.add_argument("--tag", type=str, default="")
    parser.add_argument("--max-tokens", type=int, default=128)
    args = parser.parse_args()

    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    gguf = args.gguf
    if not gguf.is_file():
        # allow relative to finetune/
        alt = (FINETUNE_ROOT / gguf).resolve()
        if alt.is_file():
            gguf = alt
        else:
            raise FileNotFoundError(gguf)

    print(f"Loading {gguf} ...")
    llm = load_llm(gguf)

    rows = []
    passed = 0
    for case in cases:
        human = format_human(case["user_text"], case["intent_card"])
        reply = generate(llm, human, max_tokens=args.max_tokens)
        ok, fails = score_reply(reply, case.get("expect") or {})
        passed += int(ok)
        rows.append(
            {
                "id": case["id"],
                "category": case.get("category"),
                "user_text": case["user_text"],
                "reply": reply,
                "pass": ok,
                "fails": fails,
            }
        )
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {case['id']}: {reply[:60]}{'...' if len(reply)>60 else ''}")
        if fails:
            print(f"       fails={fails}")

    total = len(rows)
    rate = passed / total if total else 0.0
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tag = args.tag or gguf.stem
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "tag": tag,
        "gguf": str(gguf),
        "passed": passed,
        "total": total,
        "pass_rate": rate,
        "cases": rows,
    }
    out_json = REPORTS_DIR / f"renderer_eval_{tag}_{stamp}.json"
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md = [
        f"# Renderer eval `{tag}`",
        "",
        f"- GGUF: `{gguf}`",
        f"- Pass: **{passed}/{total}** ({rate:.0%})",
        "",
        "| id | pass | reply | fails |",
        "|---|---|---|---|",
    ]
    for r in rows:
        reply_esc = (r["reply"] or "").replace("|", "\\|").replace("\n", " ")
        md.append(
            f"| {r['id']} | {'Y' if r['pass'] else 'N'} | {reply_esc} | {','.join(r['fails'])} |"
        )
    out_md = REPORTS_DIR / f"renderer_eval_{tag}_{stamp}.md"
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"\nPass {passed}/{total} ({rate:.0%})")
    print(f"Wrote {out_json}")
    print(f"Wrote {out_md}")
    if rate < 0.7:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
