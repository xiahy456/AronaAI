# -*- coding: utf-8 -*-
"""8 轮多轮会话评测：首问固定，追问按议程由 DeepSeek 生成（防带偏）。"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from judge import ExtractorApiConfig, chat_completion_json
from rules import check_reply

logger = logging.getLogger("arona_eval.multi")

TURNS = 8

FOLLOWUP_SYSTEM = """你是评测脚本中的「老师」发言生成器。根据固定议程生成下一句老师要对阿洛娜说的话。
只输出 JSON：{"utterance":"老师要说的一句中文"}

硬性规则：
1. utterance 必须推进【本轮议程】，不得改写或跳过议程主题。
2. 若阿洛娜上一轮答非所问、胡言、跑题或语义不通：忽略其错误内容，按本轮议程继续追问；可一句简短纠正后立刻回到议程，禁止顺着幻觉往下聊。
3. 只生成老师的话，不要扮演阿洛娜，不要解释评测目的。
4. 口语自然，一两句即可，不要太长。
5. 不要输出除 JSON 外的任何文字。
"""


def load_multi_sessions(path) -> List[Dict[str, Any]]:
    import json
    from pathlib import Path

    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"multi_sessions 应为 JSON 数组: {p}")
    for s in data:
        agenda = s.get("agenda") or []
        if len(agenda) != TURNS:
            raise ValueError(
                f"session {s.get('id')} agenda 长度应为 {TURNS}，实际 {len(agenda)}"
            )
        if not (s.get("opening") or "").strip():
            raise ValueError(f"session {s.get('id')} 缺少 opening")
    return data


def _agenda_keywords(agenda_item: str) -> List[str]:
    # 粗粒度中文/英文词片段，用于跑题启发式
    parts = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z_]{3,}|\d+", agenda_item or "")
    stop = {"说明", "询问", "给出", "反馈", "表示", "顺便", "追问", "确认", "改口", "再说", "请她", "告诉"}
    return [p for p in parts if p not in stop][:8]


def detect_off_topic(reply: str, agenda_item: str, user_utterance: str) -> bool:
    """启发式：回复与议程/用户话几乎无关键词交集则视为可能跑题。"""
    text = (reply or "").strip()
    if not text or text.startswith("[ERROR]"):
        return True
    keys = set(_agenda_keywords(agenda_item) + _agenda_keywords(user_utterance))
    if not keys:
        return False
    hits = sum(1 for k in keys if k.lower() in text.lower() or k in text)
    return hits == 0


def generate_followup(
    api: ExtractorApiConfig,
    *,
    goal: str,
    agenda_item: str,
    turn_index: int,
    user_utterances: List[str],
    last_assistant_reply: str,
) -> tuple[str, Optional[str]]:
    """生成下一轮老师发言。返回 (utterance, error)。"""
    user_lines = "\n".join(f"{i+1}. {u}" for i, u in enumerate(user_utterances)) or "（无）"
    payload = (
        f"【会话目标】{goal}\n"
        f"【本轮序号】{turn_index}/{TURNS}\n"
        f"【本轮议程】{agenda_item}\n"
        f"【老师已说（主线）】\n{user_lines}\n\n"
        f"【阿洛娜上一轮回复（仅供语气参考，若跑题请忽略）】\n"
        f"{last_assistant_reply or '（无）'}\n\n"
        "请生成老师下一句。"
    )
    parsed, err = chat_completion_json(
        api,
        system=FOLLOWUP_SYSTEM,
        user=payload,
        temperature=0.4,
        max_tokens=256,
    )
    if err or parsed is None:
        return "", err or "empty_response"
    utter = str(parsed.get("utterance") or "").strip()
    if not utter:
        return "", "empty_utterance"
    return utter, None


def _fallback_utterance(agenda_item: str) -> str:
    return f"阿洛娜，关于「{agenda_item}」这件事，你怎么看？"


def run_multi_session(
    model,
    tokenizer,
    session: Dict[str, Any],
    *,
    api: Optional[ExtractorApiConfig],
    system_prompt: Optional[str],
    max_new_tokens: int,
    temperature: float,
    top_p: float,
    do_sample: bool,
    enable_thinking: bool,
    build_messages,
    generate_reply,
    label: str = "model",
) -> Dict[str, Any]:
    """对单个 session 跑满 8 轮，返回 transcript 与规则分。"""
    session_id = str(session.get("id") or "multi")
    goal = str(session.get("goal") or "")
    agenda: List[str] = list(session.get("agenda") or [])
    opening = str(session.get("opening") or "").strip()
    expect = session.get("expect") or {}

    history: List[Dict[str, str]] = []
    user_utterances: List[str] = []
    turns_out: List[Dict[str, Any]] = []
    rule_scores: List[float] = []
    warnings: List[str] = []

    for turn_i in range(1, TURNS + 1):
        agenda_item = agenda[turn_i - 1]
        if turn_i == 1:
            user_text = opening
            followup_error = None
        else:
            if api is None or not api.enabled:
                user_text = _fallback_utterance(agenda_item)
                followup_error = "api_unavailable_fallback"
                warnings.append(f"turn{turn_i}:followup_fallback")
            else:
                last_reply = ""
                if turns_out:
                    last_reply = str(turns_out[-1].get("assistant") or "")
                user_text, followup_error = generate_followup(
                    api,
                    goal=goal,
                    agenda_item=agenda_item,
                    turn_index=turn_i,
                    user_utterances=user_utterances,
                    last_assistant_reply=last_reply,
                )
                if followup_error or not user_text:
                    user_text = _fallback_utterance(agenda_item)
                    warnings.append(f"turn{turn_i}:followup_error:{followup_error}")
                    followup_error = followup_error or "empty"

        user_utterances.append(user_text)
        messages = build_messages(history, user_text, system_prompt)
        try:
            reply, elapsed = generate_reply(
                model,
                tokenizer,
                messages,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                do_sample=do_sample,
                enable_thinking=enable_thinking,
            )
        except Exception as e:
            logger.error("[%s] %s turn%d 生成失败: %s", label, session_id, turn_i, e)
            reply, elapsed = f"[ERROR] {e}", 0.0

        rule = check_reply(reply, expect)
        rule_scores.append(rule.score)
        off_topic = detect_off_topic(reply, agenda_item, user_text)
        if off_topic:
            warnings.append(f"turn{turn_i}:assistant_off_topic")

        turn_rec = {
            "turn": turn_i,
            "agenda": agenda_item,
            "user": user_text,
            "assistant": reply,
            "elapsed": elapsed,
            "rule": rule.to_dict(),
            "off_topic": off_topic,
            "followup_error": followup_error,
        }
        turns_out.append(turn_rec)
        logger.info(
            "[%s] %s turn %d/%d rule=%.1f off_topic=%s",
            label,
            session_id,
            turn_i,
            TURNS,
            rule.score,
            off_topic,
        )

        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": reply})

    avg_rule = round(sum(rule_scores) / len(rule_scores), 2) if rule_scores else None
    return {
        "id": session_id,
        "category": session.get("category") or "multi_session",
        "goal": goal,
        "opening": opening,
        "agenda": agenda,
        "turns": turns_out,
        "rule_avg": avg_rule,
        "warnings": warnings,
        "n_off_topic": sum(1 for t in turns_out if t.get("off_topic")),
        "label": label,
    }


def merge_multi_sessions(
    base_sessions: List[Dict[str, Any]],
    lora_sessions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """按 id 合并 Base / LoRA 多轮结果。"""
    lora_map = {s.get("id"): s for s in lora_sessions}
    merged: List[Dict[str, Any]] = []
    for b in base_sessions:
        sid = b.get("id")
        l = lora_map.get(sid) or {}
        br = b.get("rule_avg")
        lr = l.get("rule_avg")
        delta = None
        if br is not None and lr is not None:
            delta = round(float(lr) - float(br), 2)
        # 对齐轮次并排
        paired_turns = []
        b_turns = {t["turn"]: t for t in (b.get("turns") or [])}
        l_turns = {t["turn"]: t for t in (l.get("turns") or [])}
        for i in range(1, TURNS + 1):
            bt = b_turns.get(i) or {}
            lt = l_turns.get(i) or {}
            paired_turns.append(
                {
                    "turn": i,
                    "agenda": bt.get("agenda") or lt.get("agenda"),
                    "base_user": bt.get("user"),
                    "lora_user": lt.get("user"),
                    "base_assistant": bt.get("assistant"),
                    "lora_assistant": lt.get("assistant"),
                    "base_rule": bt.get("rule"),
                    "lora_rule": lt.get("rule"),
                    "base_off_topic": bt.get("off_topic"),
                    "lora_off_topic": lt.get("off_topic"),
                }
            )
        merged.append(
            {
                "id": sid,
                "category": b.get("category") or l.get("category") or "multi_session",
                "goal": b.get("goal") or l.get("goal"),
                "opening": b.get("opening") or l.get("opening"),
                "agenda": b.get("agenda") or l.get("agenda"),
                "base_rule_avg": br,
                "lora_rule_avg": lr,
                "delta_rule": delta,
                "base_n_off_topic": b.get("n_off_topic"),
                "lora_n_off_topic": l.get("n_off_topic"),
                "base_warnings": b.get("warnings") or [],
                "lora_warnings": l.get("warnings") or [],
                "turns": paired_turns,
                "base_raw": b,
                "lora_raw": l,
            }
        )
    # LoRA-only sessions（无 compare 时 base 可能为空列表，由调用方保证）
    return merged


def build_multi_summary(merged: List[Dict[str, Any]]) -> Dict[str, Any]:
    base_avgs = [float(m["base_rule_avg"]) for m in merged if m.get("base_rule_avg") is not None]
    lora_avgs = [float(m["lora_rule_avg"]) for m in merged if m.get("lora_rule_avg") is not None]
    br = round(sum(base_avgs) / len(base_avgs), 2) if base_avgs else None
    lr = round(sum(lora_avgs) / len(lora_avgs), 2) if lora_avgs else None
    return {
        "n_sessions": len(merged),
        "turns_per_session": TURNS,
        "base_rule_avg": br,
        "lora_rule_avg": lr,
        "delta_rule": round(lr - br, 2) if br is not None and lr is not None else None,
        "base_off_topic_total": sum(int(m.get("base_n_off_topic") or 0) for m in merged),
        "lora_off_topic_total": sum(int(m.get("lora_n_off_topic") or 0) for m in merged),
    }
