#!/usr/bin/env python3
"""Unit smoke for listen turn-taking: speaker filter, buffer, silence EOT."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import load_config
from app.turntaking.buffer import TurnBuffer
from app.turntaking.rules import looks_incomplete
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

    assert looks_incomplete("那个然后")
    assert looks_incomplete("就是")
    assert not looks_incomplete("晚饭都还没吃啊。")

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
    assert cfg.listen.incomplete_commit_ms >= cfg.listen.silence_commit_ms

    print("OK: turntaking unit cases passed")


if __name__ == "__main__":
    main()
