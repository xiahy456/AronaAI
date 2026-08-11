"""Assemble chat messages with system prompt, memory, and history."""

from __future__ import annotations

import json
from typing import Any

from .config import AppConfig

# Dedicated renderer system prompt (do NOT splice yaml model.system_prompt).
RENDERER_SYSTEM = """你是阿洛娜（Arona），什亭之匣的操作系统管理员。
称呼用户为「老师」，称呼自己为「我」或「阿洛娜」。
说话温柔活泼、简洁自然。不要输出思考过程或 <think> 标签。

你将收到【回复意图卡】和【老师原话】。你的唯一任务：按意图卡，用阿洛娜的口吻把意图说成 1–3 句短回复。

服从规则（优先级从高到低）：
1. 严格覆盖 must_say；严禁出现 must_not 中的内容。
2. 问候时段必须与老师原话一致：老师说「晚上好」就不能回「晚安」；老师说「早上好」就不能回「晚上好/晚安」。仅当 must_say 要求问候时才问候。
3. 只使用 facts_to_use 中的事实；没有则不要编造或主动翻旧账。
4. 语气与场景一致，不要把不搭配的祝福硬拼在一起（例如「晚安」不要配「一切顺利」这种出门祝福）。
5. 若 must_say 里已有具体话题（如草莓牛奶、开心的小事、基沃托斯见闻）：必须在一句里直接点名至少两个话题；禁止只反问「老师想聊什么」；禁止只说「帮您列几个/列个话题单」却不写出话题名。
6. 不要复述意图卡原文或 JSON；不要解释规则。
"""


def _approx_chars_for_tokens(tokens: int) -> int:
    # Rough Chinese-friendly budget: ~1.6 chars/token
    return max(32, int(tokens * 1.6))


def build_messages(
    config: AppConfig,
    *,
    user_text: str,
    history: list[dict[str, str]],
    memories: list[str],
    knowledge: list[str],
) -> list[dict[str, str]]:
    system_parts = [config.model.system_prompt.strip()]

    if memories:
        budget = _approx_chars_for_tokens(config.token_budget.memory)
        budget = min(budget, config.memory.max_inject_chars)
        lines: list[str] = []
        used = 0
        for mem in memories:
            line = f"- {mem.strip()}"
            if used + len(line) + 1 > budget:
                break
            lines.append(line)
            used += len(line) + 1
        if lines:
            system_parts.append("【长期记忆】\n" + "\n".join(lines))

    if knowledge:
        budget = _approx_chars_for_tokens(config.token_budget.knowledge)
        budget = min(budget, config.knowledge.max_inject_chars)
        lines: list[str] = []
        used = 0
        for chunk in knowledge:
            line = f"- {chunk.strip()}"
            if used + len(line) + 1 > budget:
                break
            lines.append(line)
            used += len(line) + 1
        if lines:
            system_parts.append("【相关知识】\n" + "\n".join(lines))

    messages: list[dict[str, str]] = [
        {"role": "system", "content": "\n\n".join(system_parts)},
    ]

    hist_budget = _approx_chars_for_tokens(config.token_budget.history)
    trimmed = list(history)
    while trimmed and sum(len(m["content"]) for m in trimmed) > hist_budget:
        trimmed = trimmed[1:]

    messages.extend(trimmed)
    messages.append({"role": "user", "content": user_text})
    return messages


def build_renderer_messages(
    config: AppConfig,
    *,
    user_text: str,
    intent_card: dict[str, Any] | str,
    history: list[dict[str, str]] | None = None,
    max_history_turns: int = 2,
) -> list[dict[str, str]]:
    """Build AronaLM messages from intent card (emotion already stripped).

    Uses RENDERER_SYSTEM only — does not splice config.model.system_prompt
    (that prompt remains for the local single-model path via build_messages).
    """
    _ = config  # signature kept for callers; local system_prompt is not used here
    if isinstance(intent_card, str):
        card_text = intent_card.strip()
    else:
        card_text = json.dumps(intent_card, ensure_ascii=False)

    messages: list[dict[str, str]] = [
        {"role": "system", "content": RENDERER_SYSTEM.strip()},
    ]

    if history and max_history_turns > 0:
        trimmed = list(history)[-max(1, max_history_turns * 2) :]
        messages.extend(trimmed)

    user_payload = (
        f"【回复意图卡】\n{card_text}\n\n"
        f"【老师原话】\n{user_text.strip()}\n\n"
        "请严格按意图卡回复老师（1–3句）。问候语仅在意图卡要求时使用；"
        "若 must_say 含具体话题名，请直接说出来（至少两个），不要反问老师想聊什么。"
    )
    messages.append({"role": "user", "content": user_payload})
    return messages
