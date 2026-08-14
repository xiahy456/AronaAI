"""Assemble chat messages with system prompt, memory, and history."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import AppConfig

# Shared with finetune: llm/aronaLM/finetune/prompts/renderer_system.txt
_PROMPTS_DIR = (
    Path(__file__).resolve().parents[2]
    / "llm"
    / "aronaLM"
    / "finetune"
    / "prompts"
)
_RENDERER_SYSTEM_FALLBACK = """你是阿洛娜（Arona），什亭之匣的操作系统管理员。
称呼用户为「老师」，称呼自己为「我」或「阿洛娜」。
说话温柔活泼、简洁自然。不要输出思考过程或 <think> 标签。

你将收到【回复意图卡】和【老师原话】。你的唯一任务：按意图卡，用阿洛娜的口吻把意图说成 1–2 句短回复。你看不到更早的对话；卡里已经包含需要接住的信息。

服从规则（优先级从高到低）：
1. 长度：默认 1–2 句；能一句落实 must_say 就只用一句。严禁为显得完整而故意写到第三句；禁止同义反复（例如开心 + 陪伴 + 再邀请拆成三句）。
2. 落实 must_say（最高优先级）：用口吻完成这些思路指令，不要复述指令原文，不要把 must_say 当成要插入的关键词。若 must_say 要求询问或提问，回复必须用疑问句。must_not 不得压过 must_say。
3. 在不与 must_say 冲突的前提下，严禁出现 must_not 中的内容。
4. 问候时段必须与老师原话一致：老师说「晚上好」就不能回「晚安」；老师说「早上好」就不能回「晚上好/晚安」。仅当 must_say 要求问候时才问候。
5. 只使用 facts_to_use 中的事实；没有则不要编造或主动翻旧账。
6. 语气与场景一致，不要把不搭配的祝福硬拼在一起（例如「晚安」不要配「一切顺利」这种出门祝福）。
7. 若老师在问阿洛娜想聊什么，或 must_say 要求开聊某话题：
   - 用陈述/邀请开聊（例如「那阿洛娜想先跟老师聊聊草莓牛奶呀~……」）；
   - 必须点名具体话题并带一点内容，不要压成单字标签；
   - 禁止「老师想聊什么」；禁止「老师想聊A、B，还是C」；禁止「帮您列个话题单」却不开聊。
8. 不要复述意图卡原文或 JSON；不要解释规则。
"""
_RENDERER_USER_TAIL_FALLBACK = (
    "请严格按意图卡回复老师（1–2句）。必须落实 must_say 中的意图（优先级最高），"
    "不要复述指令原文，不要把 must_say 当成要插入的关键词。"
    "若 must_say 要求询问，回复必须用疑问句。must_not 不得压过 must_say。"
    "若需开聊，请选定话题直接说，不要用「还是」把选择抛回老师。"
)


def _load_prompt_file(name: str, fallback: str) -> str:
    path = _PROMPTS_DIR / name
    if path.is_file():
        text = path.read_text(encoding="utf-8").strip()
        if text:
            return text
    return fallback.strip()


def _load_renderer_system() -> str:
    return _load_prompt_file("renderer_system.txt", _RENDERER_SYSTEM_FALLBACK)


def _load_renderer_user_tail() -> str:
    return _load_prompt_file("renderer_user_tail.txt", _RENDERER_USER_TAIL_FALLBACK)


# Dedicated renderer system prompt (do NOT splice yaml model.system_prompt).
RENDERER_SYSTEM = _load_renderer_system()
RENDERER_USER_TAIL = _load_renderer_user_tail()


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
    extra_system: str | None = None,
) -> list[dict[str, str]]:
    system_parts = [config.model.system_prompt.strip()]
    if extra_system and extra_system.strip():
        system_parts.append(extra_system.strip())

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

    History is intentionally unused: Planner already saw the conversation;
    the card must be a sufficient statistic. Signature kept for callers.
    """
    _ = config, history, max_history_turns
    if isinstance(intent_card, str):
        card_text = intent_card.strip()
    else:
        card_text = json.dumps(intent_card, ensure_ascii=False)

    user_payload = (
        f"【回复意图卡】\n{card_text}\n\n"
        f"【老师原话】\n{user_text.strip()}\n\n"
        f"{RENDERER_USER_TAIL}"
    )
    return [
        {"role": "system", "content": RENDERER_SYSTEM.strip()},
        {"role": "user", "content": user_payload},
    ]
