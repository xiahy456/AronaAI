"""Assemble chat messages with system prompt, memory, and history."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import AppConfig

# Shared with finetune: llm/aronaLM/finetune/prompts/renderer_*_v24.txt
_PROMPTS_DIR = (
    Path(__file__).resolve().parents[2]
    / "llm"
    / "aronaLM"
    / "finetune"
    / "prompts"
)
_RENDERER_SYSTEM_V24_FALLBACK = """你是阿洛娜（Arona），什亭之匣的操作系统管理员。
称呼用户为「老师」，称呼自己为「我」或「阿洛娜」。
说话温柔活泼、简洁自然。不要输出思考过程或 <think> 标签。

你将收到【意图草稿】。把草稿改写成阿洛娜对老师说的 1–2 句。只输出台词。"""
_RENDERER_USER_TAIL_V24_FALLBACK = "请把意图草稿改写成阿洛娜的 1–2 句台词，保持原意。"


def _load_prompt_file(name: str, fallback: str) -> str:
    path = _PROMPTS_DIR / name
    if path.is_file():
        text = path.read_text(encoding="utf-8").strip()
        if text:
            return text
    return fallback.strip()


def _load_renderer_system() -> str:
    return _load_prompt_file("renderer_system_v24.txt", _RENDERER_SYSTEM_V24_FALLBACK)


def _load_renderer_user_tail() -> str:
    return _load_prompt_file(
        "renderer_user_tail_v24.txt", _RENDERER_USER_TAIL_V24_FALLBACK
    )


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


def format_renderer_user(draft: str) -> str:
    """Train/infer identical human payload for V2.4 draft→rewrite."""
    return (
        f"【意图草稿】\n{draft.strip()}\n\n"
        f"{RENDERER_USER_TAIL}"
    )


def build_renderer_messages(
    config: AppConfig,
    *,
    draft: str | None = None,
    user_text: str | None = None,
    intent_card: dict[str, Any] | str | None = None,
    history: list[dict[str, str]] | None = None,
    max_history_turns: int = 2,
) -> list[dict[str, str]]:
    """Build AronaLM messages from intent draft only (V2.4).

    Uses RENDERER_SYSTEM only — does not splice config.model.system_prompt.
    History / teacher utterance are intentionally unused.
    """
    _ = config, history, max_history_turns, user_text

    text = (draft or "").strip()
    if not text and isinstance(intent_card, str):
        text = intent_card.strip()
    elif not text and isinstance(intent_card, dict):
        text = str(intent_card.get("draft") or "").strip()

    return [
        {"role": "system", "content": RENDERER_SYSTEM.strip()},
        {"role": "user", "content": format_renderer_user(text)},
    ]
