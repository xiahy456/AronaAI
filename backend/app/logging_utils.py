"""Shared helpers for structured pipeline logging."""

from __future__ import annotations


def preview(text: str | None, max_len: int = 200) -> str:
    """Collapse whitespace and truncate for compact log lines."""
    s = " ".join((text or "").split())
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def preview_list(items: list[str] | None, *, item_max: int = 80, list_max: int = 3) -> str:
    """Format a short preview of a string list for logs."""
    if not items:
        return "[]"
    shown = [preview(x, item_max) for x in items[:list_max]]
    extra = len(items) - list_max
    body = "; ".join(shown)
    if extra > 0:
        return f"[{body}; +{extra} more]"
    return f"[{body}]"
