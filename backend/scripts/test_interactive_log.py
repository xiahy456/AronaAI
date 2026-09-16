"""Unit tests for interactive information log formatting (no GGUF).

Run from backend/:
  python scripts/test_interactive_log.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.image_input import redact_image_fields  # noqa: E402
from app.logging_utils import (  # noqa: E402
    begin_trace,
    format_interactive_log,
    format_llm_exchange,
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


def test_format_listen_transcript_request() -> None:
    print("== listen transcript request is pretty-printed ==")
    reset_trace()
    content = "这就导致一个什么问题呢？就是导致。"
    begin_trace(
        started_at=1.0,
        request_json=json.dumps(
            {"type": "transcript", "content": content},
            ensure_ascii=False,
        ),
    )
    block = format_interactive_log(
        {"type": "chat_response", "content": "老师，您慢慢说。"},
        elapsed=0.5,
    )
    if "request:\n(none)" in block:
        _fail("listen request should not be (none)")
    if '"type": "transcript"' not in block:
        _fail(f"request should show transcript type:\n{block}")
    if f'"content": "{content}"' not in block:
        _fail(f"request should pretty-print listen content:\n{block}")
    reset_trace()
    print("  ok")


def test_format_renderer_disabled_is_none() -> None:
    print("== renderer off: renderer_text is (none), content is draft ==")
    reset_trace()
    draft = "老师好，我在这儿。"
    begin_trace(
        started_at=1.0,
        request_json='{"type":"chat","content":"好"}',
    )
    update_trace(
        planner_prompt=[{"role": "system", "content": "你是规划参谋"}],
        planner_json='{"draft":"老师好，我在这儿。","arona_emotion":"smile","followup_ok":false}',
    )
    payload = {
        "type": "chat_response",
        "content": draft,
        "context_used": "climate+planner",
        "latency": 0.4,
        "emotion": "smile",
    }
    block = format_interactive_log(payload, elapsed=0.4)
    if "renderer_text:\n(none)" not in block:
        _fail(f"disabled renderer should log renderer_text (none):\n{block}")
    if "renderer_prompt:\n(none)" not in block:
        _fail(f"disabled renderer should log renderer_prompt (none):\n{block}")
    if f'"content": "{draft}"' not in block:
        _fail(f"response content should be planner draft:\n{block}")
    reset_trace()
    print("  ok")


def test_format_llm_exchange_indent_and_sections() -> None:
    print("== format_llm_exchange indent / prompt / response ==")
    messages = [
        {"role": "system", "content": "你是电脑操作路由器"},
        {"role": "user", "content": "【老师本段】打开记事本写今天日期"},
    ]
    block = format_llm_exchange(
        title="computer_use route",
        prompt=messages,
        response='{"computer_use": true}',
        extra={"computer_use": True},
    )
    if not block.startswith("computer_use route:\n"):
        _fail(f"title should start the block:\n{block}")
    if "\n" not in block:
        _fail(f"block should be multi-line:\n{block}")
    if "prompt:\n" not in block:
        _fail(f"missing prompt section:\n{block}")
    if "response:\n" not in block:
        _fail(f"missing response section:\n{block}")
    if "\n\nresponse:\n" not in block:
        _fail(f"blank line before response:\n{block}")
    if '"role": "system"' not in block or "  " not in block:
        _fail(f"prompt JSON should be indented:\n{block}")
    if '"computer_use": true' not in block:
        _fail(f"response JSON should be pretty-printed:\n{block}")
    if "computer_use: true" not in block:
        _fail(f"extra bool should render as true/false:\n{block}")
    if "reasoning:" in block:
        _fail(f"absent reasoning should omit the section:\n{block}")
    print("  ok")


def test_format_llm_exchange_optional_reasoning() -> None:
    print("== format_llm_exchange optional reasoning ==")
    with_reason = format_llm_exchange(
        title="computer_use vision",
        prompt=[{"role": "user", "content": "截图"}],
        response='{"action":"wait","ms":0}',
        reasoning="先看桌面再点开始菜单。",
    )
    if "\n\nreasoning:\n先看桌面再点开始菜单。\n\nresponse:\n" not in with_reason:
        _fail(f"reasoning should sit between prompt and response:\n{with_reason}")
    blank = format_llm_exchange(
        title="computer_use vision",
        prompt=[],
        response="not json at all",
        reasoning="   ",
    )
    if "reasoning:" in blank:
        _fail(f"blank reasoning should be omitted:\n{blank}")
    if "not json at all" not in blank:
        _fail(f"non-JSON response should stay as text:\n{blank}")
    print("  ok")


def test_format_llm_exchange_redacts_data_url() -> None:
    print("== format_llm_exchange redacts screenshot data_url ==")
    payload = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "看屏幕"},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
                    },
                },
            ],
        }
    ]
    raw_url = payload[0]["content"][1]["image_url"]["url"]
    block = format_llm_exchange(
        title="computer_use vision",
        prompt=redact_image_fields(payload),
        response='{"action":"done"}',
    )
    if raw_url in block:
        _fail("raw data URL must not appear in the log")
    if "data:image/png;base64," in block:
        _fail("data URL prefix must not appear after redact")
    if "[redacted data_url" not in block or "chars]" not in block:
        _fail(f"expected redacted data_url placeholder:\n{block}")
    if "看屏幕" not in block:
        _fail(f"text part of prompt should remain:\n{block}")
    if "Authorization" in block or "api_key" in block:
        _fail(f"must not log credentials:\n{block}")
    print("  ok")


def main() -> None:
    try:
        test_pretty_json()
        test_format_interactive_log_block()
        test_format_missing_fields_are_none()
        test_format_listen_transcript_request()
        test_format_renderer_disabled_is_none()
        test_format_llm_exchange_indent_and_sections()
        test_format_llm_exchange_optional_reasoning()
        test_format_llm_exchange_redacts_data_url()
    finally:
        reset_trace()
    print("ALL PASS")


if __name__ == "__main__":
    main()
