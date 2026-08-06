"""Assemble chat messages with system prompt, memory, and history."""

from __future__ import annotations

from .config import AppConfig


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
        system_parts.append("【相关知识】\n" + "\n".join(f"- {k}" for k in knowledge))

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
