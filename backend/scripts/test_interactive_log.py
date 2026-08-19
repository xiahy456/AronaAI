"""Unit tests for interactive information log formatting (no GGUF).

Run from backend/:
  python scripts/test_interactive_log.py
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.logging_utils import (  # noqa: E402
    begin_trace,
    format_interactive_log,
    pretty_json,
    reset_trace,
    update_trace,
)


def _fail(msg: str) -> None:
    raise AssertionError(msg)


def test_pretty_json() -> None:
    print("== pretty_json indent / none / fallback ==")
    pretty = pretty_json({"type": "chat", "content": "好"})
    if "\n" not in pretty or '"type": "chat"' not in pretty:
        _fail(f"object should be indented JSON: {pretty!r}")
    from_text = pretty_json('{"draft":"陪老师","followup_ok":false}')
    if "\n" not in from_text or '"draft": "陪老师"' not in from_text:
        _fail(f"JSON string should re-indent: {from_text!r}")
    if pretty_json(None) != "(none)":
        _fail("None should be (none)")
    if pretty_json("") != "(none)":
        _fail("empty string should be (none)")
    if pretty_json("老师慢慢来") != "老师慢慢来":
        _fail("plain text should stay as-is")
    print("  ok")


def test_format_interactive_log_block() -> None:
    print("== format_interactive_log sections and blanks ==")
    reset_trace()
    begin_trace(
        started_at=1.0,
        request_json='{"type":"chat","content":"好","options":{"use_rag":true}}',
    )
    update_trace(
        planner_prompt=[
            {"role": "system", "content": "你是规划参谋"},
            {"role": "user", "content": "【老师本轮消息】\n好"},
        ],
        planner_json='{"draft":"嗯嗯，我在这儿等您。","arona_emotion":"smile","followup_ok":false}',
        renderer_prompt=[
            {"role": "system", "content": "你是阿洛娜"},
            {"role": "user", "content": "【意图草稿】\n嗯嗯，我在这儿等您。"},
        ],
        renderer_text="嗯，我在这儿等您回来哦。",
    )
    payload = {
        "type": "chat_response",
        "content": "嗯，我在这儿等您回来哦。",
        "from_cache": False,
        "context_used": "climate+planner+renderer",
        "latency": 2.1,
        "emotion": "smile",
    }
    block = format_interactive_log(payload, elapsed=2.157)
    for label in (
        "interactive information:",
        "request:",
        "planner_prompt:",
        "planner_json:",
        "renderer_prompt:",
        "renderer_text:",
        "response:",
        "elapsed: 2.157s",
    ):
        if label not in block:
            _fail(f"missing {label!r} in:\n{block}")
    if "request:\n{\n" not in block:
        _fail(f"request JSON should start on next line:\n{block}")
    if '"content": "好"' not in block:
        _fail("request JSON should be pretty-printed")
    if '"followup_ok": false' not in block:
        _fail("planner_json should be pretty-printed")
    if "嗯，我在这儿等您回来哦。" not in block:
        _fail("renderer_text should appear")
    if "\n\nplanner_prompt:\n" not in block:
        _fail("blank line between request and planner_prompt")
    if "\n\nplanner_json:\n" not in block:
        _fail("blank line between planner_prompt and planner_json")
    if "\n\nrenderer_prompt:\n" not in block:
        _fail("blank line before renderer_prompt")
    if "\n\nrenderer_text:\n" not in block:
        _fail("blank line before renderer_text")
    if "\n\nresponse:\n" not in block:
        _fail("blank line before response")
    if "\n\nelapsed: 2.157s" not in block:
        _fail("blank line before elapsed")
    reset_trace()
    print("  ok")


def test_format_missing_fields_are_none() -> None:
    print("== missing planner/renderer are (none) ==")
    reset_trace()
    begin_trace(started_at=10.0, request_json=None)
    block = format_interactive_log(
        {"type": "chat_response", "content": "刚才没听清，请再说一次～"},
        elapsed=0.012,
    )
    if block.count("(none)") < 4:
        _fail(f"expected (none) for absent fields:\n{block}")
    if "request:\n(none)" not in block:
        _fail("system-initiated request should be (none)")
    if "renderer_text:\n(none)" not in block:
        _fail("empty renderer_text should be (none)")
    reset_trace()
    empty = format_interactive_log({"type": "chat_response", "content": ""}, elapsed=0.0)
    if "request:\n(none)" not in empty:
        _fail("no trace should still render (none) fields")
    print("  ok")


def main() -> None:
    try:
        test_pretty_json()
        test_format_interactive_log_block()
        test_format_missing_fields_are_none()
    finally:
        reset_trace()
    print("ALL PASS")


if __name__ == "__main__":
    main()
