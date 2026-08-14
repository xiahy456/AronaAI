#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LLM-judge whether a handwritten gold reply fulfills a Planner-style card.

Updates review/queue.jsonl verdict fields. On repair_card, rewrites card only.

  python data-process/judge_renderer_gold.py
  python data-process/judge_renderer_gold.py --only-empty
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm_client import chat_json  # noqa: E402
from renderer_format import BASE_MUST_NOT  # noqa: E402

FINETUNE_ROOT = Path(__file__).resolve().parent.parent
QUEUE_PATH = FINETUNE_ROOT / "data" / "raw" / "normal" / "review" / "queue.jsonl"

JUDGE_SYSTEM = """你在判定一条 Renderer 训练样本能不能当金标入训。
金标对白是人手写的，不要改写它。卡是 Planner 风格的思路指令。

判定「落实」：回复是否完成了每条 must_say 的意图，不是指令原文是否出现在回复里。
「表明自己是管理员」落实为「我是……管理员」算过。

形态：must_say 必须像思路句，不能是词碎片或三条并列「聊一聊」。
句类：must_say 要求询问 ⇒ 回复应提问；回复在提问 ⇒ 卡不要禁提问收尾。
must_say 优先：同一张卡不能既要求询问又写「用提问收尾」。
抛回老师（「A还是B？」让老师选）与「把问题抛回老师」冲突则 fail。
口吻要像阿洛娜；过假的工具幻觉（已备份 37 个文件等）标 tool_claim。

只输出 JSON：
{
  "verdict": "pass" | "fail" | "repair_card",
  "reasons": ["..."],
  "must_say_covered": true,
  "speech_act_aligned": true,
  "must_say_not_vacuous": true,
  "must_say_outranks_must_not": true,
  "persona_ok": true,
  "tool_claim": false,
  "suggested_card": null
}
repair_card 时 suggested_card 必须给出完整卡（同字段），且仍能被当前金标落实。
"""


def _mechanical_ok(rec: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if not str(rec.get("user_text") or "").strip():
        fails.append("empty_user")
    if not str(rec.get("gold") or "").strip():
        fails.append("empty_gold")
    card = rec.get("card")
    if not isinstance(card, dict) or not card:
        fails.append("empty_card")
        return fails
    must = card.get("must_say")
    if not isinstance(must, list) or not must:
        fails.append("empty_must_say")
    return fails


def judge_one(rec: dict[str, Any]) -> dict[str, Any]:
    mech = _mechanical_ok(rec)
    if mech:
        rec["verdict"] = "fail"
        rec["reasons"] = mech
        rec.setdefault("flags", [])
        if "mechanical_fail" not in rec["flags"]:
            rec["flags"].append("mechanical_fail")
        return rec
    payload = {
        "user_text": rec["user_text"],
        "gold_reply": rec["gold"],
        "card": rec.get("card") or {},
        "fixed_must_not": BASE_MUST_NOT,
    }
    parsed = chat_json(
        system=JUDGE_SYSTEM,
        user=json.dumps(payload, ensure_ascii=False),
        temperature=0.1,
        max_tokens=900,
    )
    if not isinstance(parsed, dict):
        raise ValueError("judge did not return an object")
    verdict = str(parsed.get("verdict") or "fail").strip().lower()
    if verdict not in {"pass", "fail", "repair_card"}:
        verdict = "fail"
    reasons = parsed.get("reasons")
    if not isinstance(reasons, list):
        reasons = [str(reasons)]
    rec["verdict"] = verdict
    rec["reasons"] = [str(x) for x in reasons]
    rec["judge"] = {
        "must_say_covered": bool(parsed.get("must_say_covered")),
        "speech_act_aligned": bool(parsed.get("speech_act_aligned")),
        "must_say_not_vacuous": bool(parsed.get("must_say_not_vacuous")),
        "must_say_outranks_must_not": bool(parsed.get("must_say_outranks_must_not")),
        "persona_ok": bool(parsed.get("persona_ok")),
        "tool_claim": bool(parsed.get("tool_claim")),
    }
    suggested = parsed.get("suggested_card")
    if verdict == "repair_card" and isinstance(suggested, dict) and suggested:
        must_say = suggested.get("must_say")
        if isinstance(must_say, list):
            suggested["must_say"] = [str(x).strip() for x in must_say if str(x).strip()][:2]
        suggested["length"] = "1-2句"
        rec["card"] = suggested
        rec.setdefault("flags", [])
        if "card_repaired" not in rec["flags"]:
            rec["flags"].append("card_repaired")
    if rec.get("judge", {}).get("tool_claim"):
        rec.setdefault("flags", [])
        if "tool_claim" not in rec["flags"]:
            rec["flags"].append("tool_claim")
    rec.setdefault("status", "pending")
    return rec


def _read_queue(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if isinstance(rec, dict):
            rows.append(rec)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, default=QUEUE_PATH)
    parser.add_argument("--only-empty", action="store_true")
    parser.add_argument("--rejudge-repaired", action="store_true")
    parser.add_argument("--sleep", type=float, default=0.15)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    if not args.queue.is_file():
        raise SystemExit(f"queue missing: {args.queue}")

    rows = _read_queue(args.queue)
    done = 0
    for rec in rows:
        if args.limit and done >= args.limit:
            break
        has_verdict = str(rec.get("verdict") or "").strip() in {
            "pass",
            "fail",
            "repair_card",
        }
        if args.only_empty and has_verdict:
            continue
        rid = rec.get("id")
        print(f"judge {rid} ...", flush=True)
        try:
            judge_one(rec)
            if (
                args.rejudge_repaired
                and rec.get("verdict") == "repair_card"
                and rec.get("card")
            ):
                rec["verdict"] = ""
                judge_one(rec)
        except Exception as exc:
            rec["verdict"] = "fail"
            rec["reasons"] = [f"judge_error:{exc}"]
            rec.setdefault("flags", [])
            rec["flags"].append("judge_error")
            print(f"  FAIL {rid}: {exc}", flush=True)
        done += 1
        with args.queue.open("w", encoding="utf-8") as f:
            for item in rows:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        if args.sleep > 0:
            time.sleep(args.sleep)

    with args.queue.open("w", encoding="utf-8") as f:
        for rec in rows:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    counts: dict[str, int] = {}
    for rec in rows:
        v = str(rec.get("verdict") or "unset")
        counts[v] = counts.get(v, 0) + 1
    print(f"Wrote {args.queue} judged={done} counts={counts}", flush=True)


if __name__ == "__main__":
    main()
