# -*- coding: utf-8 -*-
"""训练集抽样探针：对比模型回复与训练金标，辅助判断欠拟合/过拟合。"""

from __future__ import annotations

import json
import logging
import random
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rules import check_reply

logger = logging.getLogger("arona_eval.train_probe")

_ROLE_MAP = {
    "human": "user",
    "user": "user",
    "gpt": "assistant",
    "assistant": "assistant",
    "system": "system",
}


def _normalize_chars(text: str) -> str:
    t = (text or "").strip().lower()
    t = re.sub(r"\s+", "", t)
    return t


def char_jaccard(a: str, b: str) -> float:
    """字符 bigram Jaccard，作与金标的粗粒度相似度。"""
    sa = _normalize_chars(a)
    sb = _normalize_chars(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    ga = {sa[i : i + 2] for i in range(max(1, len(sa) - 1))}
    gb = {sb[i : i + 2] for i in range(max(1, len(sb) - 1))}
    if len(sa) == 1:
        ga = {sa}
    if len(sb) == 1:
        gb = {sb}
    inter = len(ga & gb)
    union = len(ga | gb)
    return round(inter / union, 4) if union else 0.0


def exact_match(a: str, b: str) -> bool:
    return _normalize_chars(a) == _normalize_chars(b)


def parse_sharegpt_row(obj: Dict[str, Any], line_no: int) -> Optional[Dict[str, Any]]:
    """从一条 ShareGPT 样本抽出最后一轮 human 提问 + 之前历史 + gpt 金标。"""
    conv = obj.get("conversations") or []
    if not isinstance(conv, list) or not conv:
        return None

    messages: List[Dict[str, str]] = []
    for turn in conv:
        if not isinstance(turn, dict):
            continue
        role = _ROLE_MAP.get(str(turn.get("from") or "").lower())
        value = str(turn.get("value") or "").strip()
        if not role or not value:
            continue
        messages.append({"role": role, "content": value})

    # 找最后一条 assistant 作为金标，其前一条 user 作为提问
    last_asst_i = None
    for i in range(len(messages) - 1, -1, -1):
        if messages[i]["role"] == "assistant":
            last_asst_i = i
            break
    if last_asst_i is None or last_asst_i == 0:
        return None
    if messages[last_asst_i - 1]["role"] != "user":
        return None

    gold = messages[last_asst_i]["content"]
    prompt = messages[last_asst_i - 1]["content"]
    history = messages[: last_asst_i - 1]
    return {
        "id": f"train_{line_no:04d}",
        "category": "train_probe",
        "prompt": prompt,
        "history": history,
        "gold": gold,
        "source_line": line_no,
        "expect": {
            "must_not_contain": ["<think>", "</think>"],
            "facts": ["no_think", "no_action_paren"],
        },
    }


def load_train_probe_cases(
    train_file: Path,
    *,
    n: int = 24,
    seed: int = 3407,
) -> List[Dict[str, Any]]:
    """从训练集 JSONL 抽样 n 条可解析样本。"""
    rows: List[Tuple[int, Dict[str, Any]]] = []
    with train_file.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                rows.append((i, obj))

    parsed: List[Dict[str, Any]] = []
    for line_no, obj in rows:
        case = parse_sharegpt_row(obj, line_no)
        if case:
            parsed.append(case)

    if not parsed:
        raise ValueError(f"训练集无可解析样本: {train_file}")

    rng = random.Random(seed)
    if n >= len(parsed):
        sampled = list(parsed)
        rng.shuffle(sampled)
    else:
        sampled = rng.sample(parsed, n)

    # 稳定排序，方便报告阅读
    sampled.sort(key=lambda c: int(c.get("source_line") or 0))
    logger.info(
        "训练集探针抽样 %d / %d 条 (seed=%s) from %s",
        len(sampled),
        len(parsed),
        seed,
        train_file,
    )
    return sampled


def merge_train_probe_results(
    cases: List[Dict[str, Any]],
    base_out: Dict[str, Dict[str, Any]],
    lora_out: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for case in cases:
        cid = str(case["id"])
        gold = str(case.get("gold") or "")
        base_reply = (base_out.get(cid) or {}).get("reply", "")
        lora_reply = (lora_out.get(cid) or {}).get("reply", "")
        expect = case.get("expect") or {}

        base_rule = check_reply(base_reply, expect)
        lora_rule = check_reply(lora_reply, expect)
        base_sim = char_jaccard(base_reply, gold)
        lora_sim = char_jaccard(lora_reply, gold)

        results.append(
            {
                "id": cid,
                "category": "train_probe",
                "prompt": case.get("prompt"),
                "history": case.get("history") or [],
                "gold": gold,
                "source_line": case.get("source_line"),
                "base_reply": base_reply,
                "lora_reply": lora_reply,
                "base_elapsed": (base_out.get(cid) or {}).get("elapsed"),
                "lora_elapsed": (lora_out.get(cid) or {}).get("elapsed"),
                "base_rule": base_rule.to_dict(),
                "lora_rule": lora_rule.to_dict(),
                "delta_rule": round(lora_rule.score - base_rule.score, 2),
                "base_gold_sim": base_sim,
                "lora_gold_sim": lora_sim,
                "delta_gold_sim": round(lora_sim - base_sim, 4),
                "base_exact": exact_match(base_reply, gold),
                "lora_exact": exact_match(lora_reply, gold),
            }
        )
    return results


def build_train_probe_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not results:
        return {"n": 0}

    def _avg(key: str) -> Optional[float]:
        vals = [float(r[key]) for r in results if r.get(key) is not None]
        return round(sum(vals) / len(vals), 4) if vals else None

    base_sim = _avg("base_gold_sim")
    lora_sim = _avg("lora_gold_sim")
    br = [
        float((r.get("base_rule") or {}).get("score"))
        for r in results
        if (r.get("base_rule") or {}).get("score") is not None
    ]
    lr = [
        float((r.get("lora_rule") or {}).get("score"))
        for r in results
        if (r.get("lora_rule") or {}).get("score") is not None
    ]

    return {
        "n": len(results),
        "base_gold_sim_avg": base_sim,
        "lora_gold_sim_avg": lora_sim,
        "delta_gold_sim": round(lora_sim - base_sim, 4)
        if base_sim is not None and lora_sim is not None
        else None,
        "base_exact_rate": round(
            sum(1 for r in results if r.get("base_exact")) / len(results), 4
        ),
        "lora_exact_rate": round(
            sum(1 for r in results if r.get("lora_exact")) / len(results), 4
        ),
        "base_rule_avg": round(sum(br) / len(br), 2) if br else None,
        "lora_rule_avg": round(sum(lr) / len(lr), 2) if lr else None,
        "note": (
            "gold_sim 为与训练集金标的字符 bigram Jaccard。"
            "结合 held-out 单轮/多轮表现解读："
            "训练集高相似+泛化差→过拟合；训练集低相似+泛化差→欠拟合；"
            "两端都较好→拟合良好。"
        ),
    }
