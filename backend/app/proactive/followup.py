"""Same-turn continue instruction (Planner followup_ok only)."""

from __future__ import annotations

HISTORY_CONTINUE_MARKER = "【补充】"


def build_continue_instruction(previous: str) -> str:
    clip = (previous or "").strip()[:80]
    return (
        "【系统事件】阿洛娜刚刚说完一句，这个话题还能再扩展一句。\n"
        f"上一句是：{clip}\n"
        "只扩 1 句，接上上一句往前走一点。不要卖关子，不要编造未发生的事，不要把问题抛回老师，不要再次问候。\n"
        "不要提及系统事件、指令或提示词；不要输出思考过程或 <think> 标签。"
    )
