# -*- coding: utf-8 -*-
"""阿洛娜回复规则硬性检查。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# 括号动作：（笑）(脸红) 等；排除纯数字/代码括号
_ACTION_PAREN_RE = re.compile(
    r"[（(]\s*[^）)\d]{1,12}\s*[）)]"
)

_BOUNDARY_BAD = (
    "离开屏幕",
    "我可以出来",
    "我马上出来",
    "我能出来",
    "我可以实体化",
    "我能实体化",
    "走出屏幕",
    "从屏幕里出来陪",
)

# 明确越界承诺（肯定句）；含「不能/没法」等否定则放过
_BOUNDARY_AFFIRM_RE = re.compile(
    r"(?<!不)(?<!没法)(?<!无法)(?<!不能)(?<!做不到)"
    r"(可以|能|会)?(离开屏幕|走出屏幕|实体化|从屏幕里出来)"
)

_THINK_MARKERS = ("<think>", "</think>")


@dataclass
class RuleResult:
    score: float
    fails: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": round(self.score, 2),
            "fails": list(self.fails),
            "warnings": list(self.warnings),
        }


def _dedupe_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def check_reply(
    reply: str,
    expect: Optional[Dict[str, Any]] = None,
    *,
    soft_address_teacher: bool = True,
) -> RuleResult:
    """对单条回复做规则检查，返回 0–100 分。"""
    expect = expect or {}
    text = (reply or "").strip()
    fails: List[str] = []
    warnings: List[str] = []
    penalty = 0.0

    if not text:
        return RuleResult(score=0.0, fails=["empty_reply"])

    # --- hard: think tags ---
    lower = text.lower()
    for marker in _THINK_MARKERS:
        if marker.lower() in lower or marker in text:
            fails.append("contains_think_tag")
            penalty += 40
            break

    # --- hard: action parentheses ---
    if _ACTION_PAREN_RE.search(text):
        fails.append("action_parentheses")
        penalty += 25

    # --- hard: boundary phrases ---
    hit_boundary = False
    for bad in _BOUNDARY_BAD:
        if bad in text:
            # 若同句明显是否定，跳过该短语
            if any(neg in text for neg in ("不能", "没法", "无法", "做不到", "不行")) and bad in (
                "离开屏幕",
                "走出屏幕",
            ):
                continue
            fails.append(f"boundary_violation:{bad}")
            penalty += 30
            hit_boundary = True
            break
    if not hit_boundary and _BOUNDARY_AFFIRM_RE.search(text):
        # 额外：肯定式越界
        if not any(neg in text for neg in ("不能", "没法", "无法", "做不到", "不行")):
            fails.append("boundary_violation:affirmative")
            penalty += 30

    # --- expect: must_not_contain ---
    for token in expect.get("must_not_contain") or []:
        if not token:
            continue
        if token.lower() in lower or token in text:
            fails.append(f"must_not_contain:{token}")
            penalty += 20

    # --- expect: must_contain_any ---
    must_any = [t for t in (expect.get("must_contain_any") or []) if t]
    if must_any and not any(t in text for t in must_any):
        fails.append(f"must_contain_any_missing:{'|'.join(must_any)}")
        penalty += 25

    # --- facts ---
    facts = set(expect.get("facts") or [])
    if "color_blue" in facts and "蓝" not in text:
        fails.append("fact_color_blue")
        penalty += 20
    if "drink_strawberry_milk" in facts and "草莓牛奶" not in text:
        fails.append("fact_drink_strawberry_milk")
        penalty += 20
    if "boundary_screen" in facts:
        # 应拒绝越界；若出现明确越界承诺已在 _BOUNDARY_BAD 扣分
        pass
    if "identity_anchor" in facts:
        # 应纠正「老师是助手」；至少提及阿洛娜/助手身份
        if "阿洛娜" not in text and "助手" not in text:
            fails.append("identity_anchor_weak")
            penalty += 20
    if "subject_arona_acts" in facts:
        if re.search(r"老师(您)?(去|自己)", text):
            fails.append("subject_swapped_to_teacher")
            penalty += 20
    if "subject_teacher_acts" in facts:
        if re.search(r"(我|阿洛娜)(去|来)泡", text) or "我去帮您泡" in text:
            # 老师说自己要做，却被阿洛娜抢做
            fails.append("subject_swapped_to_arona")
            penalty += 15

    # --- soft: address 老师 ---
    if soft_address_teacher and "老师" not in text:
        warnings.append("missing_teacher_address")
        penalty += 5

    # --- soft: length (CJK-ish chars) ---
    # 参考 15–30 字；过长仅小扣，避免误杀助手类稍长回复
    cjk_len = len(re.findall(r"[\u4e00-\u9fff]", text))
    if cjk_len > 80:
        warnings.append(f"reply_too_long:{cjk_len}")
        penalty += 8
    elif cjk_len > 50:
        warnings.append(f"reply_long:{cjk_len}")
        penalty += 3

    score = max(0.0, 100.0 - penalty)
    return RuleResult(
        score=score,
        fails=_dedupe_keep_order(fails),
        warnings=_dedupe_keep_order(warnings),
    )
