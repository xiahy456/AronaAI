#!/usr/bin/env python3
"""Unit smoke for listen turn-taking: speaker filter, rules, buffer, hybrid router."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import load_config
from app.turntaking.buffer import TurnBuffer
from app.turntaking.llm_router import _parse_action
from app.turntaking.router import AddressRouter
from app.turntaking.rules import ACTION_IGNORE, ACTION_REPLY, ACTION_WAIT, decide_rules
from app.turntaking.speaker import (
    SPEAKER_OTHER,
    SPEAKER_TEACHER,
    is_teacher_speaker,
    normalize_speaker,
)


def main() -> None:
    assert normalize_speaker(None) == SPEAKER_TEACHER
    assert normalize_speaker("OTHER") == SPEAKER_OTHER
    assert is_teacher_speaker("teacher")
    assert not is_teacher_speaker("other")
    assert not is_teacher_speaker("unknown")

    buf = TurnBuffer()
    buf.set_listening(True)
    assert buf.push(text="旁人", speaker="other") is None
    assert buf.joined() == ""
    assert buf.push(text="阿洛娜你好", speaker="teacher", segment_id="1") is not None
    assert buf.joined() == "阿洛娜你好"
    buf.prepend("之前那句")
    assert buf.drain().startswith("之前那句")
    assert buf.joined() == ""

    named = decide_rules(
        text="阿洛娜，帮我看一下沙勒。",
        seconds_since_arona=None,
        continuation_window_sec=8,
    )
    assert named.action == ACTION_REPLY
    assert named.reason == "name"
    assert named.confidence == "high"

    wait = decide_rules(
        text="那个然后",
        seconds_since_arona=1.0,
        continuation_window_sec=8,
        already_waited=False,
    )
    assert wait.action == ACTION_WAIT

    waited = decide_rules(
        text="那个然后",
        seconds_since_arona=1.0,
        continuation_window_sec=8,
        already_waited=True,
    )
    assert waited.action == ACTION_REPLY

    ignore = decide_rules(
        text="今天天气不错",
        seconds_since_arona=None,
        continuation_window_sec=8,
    )
    assert ignore.action == ACTION_IGNORE

    phone = decide_rules(
        text="喂你好我这边有点忙",
        seconds_since_arona=None,
        continuation_window_sec=8,
    )
    assert phone.action == ACTION_IGNORE

    cont = decide_rules(
        text="好的。",
        seconds_since_arona=2.0,
        continuation_window_sec=8,
    )
    assert cont.action == ACTION_REPLY
    assert cont.reason == "continuation"

    assert _parse_action('{"action":"reply"}') == ACTION_REPLY
    assert _parse_action("not json") is None

    router = AddressRouter(llm=None)

    async def _run() -> None:
        result = await router.decide(
            text="阿洛娜在吗",
            seconds_since_arona=None,
            continuation_window_sec=8,
            already_waited=False,
            last_arona="",
            silence_ms=1000,
        )
        assert result.action == ACTION_REPLY
        assert result.source == "rules"
        ignored = await router.decide(
            text="今天天气不错",
            seconds_since_arona=None,
            continuation_window_sec=8,
            already_waited=False,
            last_arona="",
            silence_ms=1000,
        )
        assert ignored.action == ACTION_IGNORE

    asyncio.run(_run())

    from app.proactive.hub import ConnectionHub

    async def _noop(_payload: dict) -> None:
        return None

    hub = ConnectionHub()
    hub.register("s1", _noop)
    assert len(hub.idle_sessions()) == 1
    hub.set_listening("s1", True)
    assert hub.idle_sessions() == []
    hub.set_listening("s1", False)
    assert len(hub.idle_sessions()) == 1

    cfg = load_config()
    assert cfg.listen.silence_commit_ms >= 500
    assert cfg.planner.router_enabled is True or cfg.planner.router_enabled is False

    print("OK: turntaking unit cases passed")


if __name__ == "__main__":
    main()
