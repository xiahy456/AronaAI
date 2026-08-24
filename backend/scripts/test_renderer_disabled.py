"""Unit tests for model.enabled=false (planner draft as content, no GGUF).

Run from backend/:
  python scripts/test_renderer_disabled.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import AppConfig, ModelConfig  # noqa: E402
from app.logging_utils import (  # noqa: E402
    begin_trace,
    format_interactive_log,
    reset_trace,
)
from app.orchestrator import Orchestrator  # noqa: E402
from app.planner.schema import IntentCard  # noqa: E402
from app.protocol import msg_chat_response  # noqa: E402

DRAFT = "老师好，我在这儿。"


def _fail(msg: str) -> None:
    raise AssertionError(msg)


def _intent() -> IntentCard:
    card = IntentCard.from_dict(
        {
            "draft": DRAFT,
            "arona_emotion": "smile",
            "followup_ok": False,
            "reply_ok": True,
            "user_act": "other",
        }
    )
    if card is None:
        _fail("IntentCard.from_dict returned None")
    return card


def _orchestrator(*, enabled: bool) -> Orchestrator:
    config = AppConfig(model=ModelConfig(enabled=enabled))
    model = MagicMock()
    model.generate.side_effect = AssertionError("generate must not be called")
    return Orchestrator(
        config,
        model=model,
        conversations=MagicMock(),
        memory_store=MagicMock(),
        extractor=MagicMock(),
        knowledge=MagicMock(),
    )


def test_model_enabled_defaults_true() -> None:
    print("== ModelConfig.enabled defaults to true ==")
    if ModelConfig().enabled is not True:
        _fail("ModelConfig.enabled should default to True")
    if AppConfig().model.enabled is not True:
        _fail("AppConfig.model.enabled should default to True")
    print("  ok")


def test_compose_uses_draft_when_disabled() -> None:
    print("== disabled renderer uses planner draft and skips generate ==")
    reset_trace()
    begin_trace(
        started_at=1.0,
        request_json='{"type":"chat","content":"好"}',
    )
    orch = _orchestrator(enabled=False)
    full, context_used = asyncio.run(
        orch._compose_reply(
            session_id="s1",
            intent=_intent(),
            user_text="好",
            history=[],
            memories=[],
            knowledge=[],
            context_parts=["planner"],
            emotion="smile",
        )
    )
    if full != DRAFT:
        _fail(f"content should be planner draft, got {full!r}")
    if "renderer" in context_used.split("+"):
        _fail(f"context_used should not include renderer: {context_used}")
    orch.model.generate.assert_not_called()
    payload = msg_chat_response(
        full,
        context_used=context_used,
        emotion="smile",
    )
    block = format_interactive_log(payload, elapsed=0.12)
    if "renderer_text:\n(none)" not in block:
        _fail(f"interactive log renderer_text should be (none):\n{block}")
    if f'"content": "{DRAFT}"' not in block:
        _fail(f"interactive log response content should be draft:\n{block}")
    reset_trace()
    print("  ok")


def test_compose_unavailable_when_disabled_and_no_intent() -> None:
    print("== disabled renderer without intent cannot generate ==")
    orch = _orchestrator(enabled=False)
    full, _context_used = asyncio.run(
        orch._compose_reply(
            session_id="s1",
            intent=None,
            user_text="好",
            history=[],
            memories=[],
            knowledge=[],
            context_parts=["planner"],
        )
    )
    if full is not None:
        _fail(f"expected None when planner missed, got {full!r}")
    orch.model.generate.assert_not_called()
    print("  ok")


def test_compose_calls_generate_when_enabled() -> None:
    print("== enabled renderer still calls generate ==")
    rewritten = "嗯，老师，我在。"
    config = AppConfig(model=ModelConfig(enabled=True))
    model = MagicMock()
    model.generate.return_value = rewritten
    orch = Orchestrator(
        config,
        model=model,
        conversations=MagicMock(),
        memory_store=MagicMock(),
        extractor=MagicMock(),
        knowledge=MagicMock(),
    )
    full, context_used = asyncio.run(
        orch._compose_reply(
            session_id="s1",
            intent=_intent(),
            user_text="好",
            history=[],
            memories=[],
            knowledge=[],
            context_parts=["planner"],
            emotion="smile",
        )
    )
    if full != rewritten:
        _fail(f"expected renderer output, got {full!r}")
    if "renderer" not in context_used.split("+"):
        _fail(f"context_used should include renderer: {context_used}")
    model.generate.assert_called_once()
    print("  ok")


def main() -> None:
    try:
        test_model_enabled_defaults_true()
        test_compose_uses_draft_when_disabled()
        test_compose_unavailable_when_disabled_and_no_intent()
        test_compose_calls_generate_when_enabled()
    finally:
        reset_trace()
    print("ALL PASS")


if __name__ == "__main__":
    main()
