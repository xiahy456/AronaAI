#!/usr/bin/env python3
"""Unit tests for phase-0 computer-use probe (no GGUF, no network).

Run from backend/:
  python scripts/test_computer_use_unit.py
"""

from __future__ import annotations

import asyncio
import base64
import sys
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.computer_use import (  # noqa: E402
    ACTION_WHITELIST,
    PROBE_ALIAS,
    PROBE_TOKEN,
    ComputerUseObservation,
    ProbeResult,
    SchemaError,
    is_probe_text,
    parse_action,
    parse_observation,
    parse_screen,
    probe_actions,
    probe_reply_text,
    run_probe,
    terminal_messages,
)
from app.protocol import (  # noqa: E402
    TYPE_COMPUTER_USE_ACTION,
    msg_computer_use_action,
    msg_computer_use_done,
)

_JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 16 + b"\xff\xd9"
_JPEG_B64 = base64.b64encode(_JPEG).decode("ascii")


def _fail(msg: str) -> None:
    raise AssertionError(msg)


def _valid_screen() -> dict[str, Any]:
    return {
        "origin_x": 0, "origin_y": 0,
        "phys_w": 1920, "phys_h": 1080,
        "img_w": 1280, "img_h": 720,
    }


def _ok_obs(run_id: str, step: int) -> ComputerUseObservation:
    return ComputerUseObservation(
        run_id=run_id, step=step, ok=True, error="",
        screen=parse_screen(_valid_screen()), image=None,
    )


# -- Token recognition --

def test_probe_token_recognition() -> None:
    print("== probe token recognition ==")
    if not is_probe_text(PROBE_TOKEN):
        _fail(f"should accept {PROBE_TOKEN!r}")
    if not is_probe_text(PROBE_ALIAS):
        _fail(f"should accept alias {PROBE_ALIAS!r}")
    if not is_probe_text("  __cu_probe__  "):
        _fail("should strip whitespace")
    if is_probe_text("not a probe"):
        _fail("should reject normal text")
    if is_probe_text(""):
        _fail("should reject empty")
    if is_probe_text(None):
        _fail("should reject None")
    if not is_probe_text("__custom__", "__custom__"):
        _fail("should accept custom token")
    # Default aliases are always recognized; custom token is additive
    if not is_probe_text("__cu_probe__", "__custom__"):
        _fail("default alias should still be recognized with custom token")
    print("  ok")


# -- Action whitelist --

def test_action_whitelist() -> None:
    print("== action whitelist ==")
    expected = {
        "move", "click", "double_click", "right_click",
        "scroll", "type", "key", "wait", "done",
    }
    if ACTION_WHITELIST != expected:
        _fail(f"whitelist mismatch: {ACTION_WHITELIST}")
    print("  ok")


def test_parse_action_move() -> None:
    print("== parse action move ==")
    action = parse_action({"action": "move", "x": 0.5, "y": 0.5})
    if action.action != "move":
        _fail(f"action={action.action}")
    if action.x != 0.5 or action.y != 0.5:
        _fail(f"x={action.x} y={action.y}")
    print("  ok")


def test_parse_action_wait() -> None:
    print("== parse action wait ==")
    action = parse_action({"action": "wait", "ms": 400})
    if action.ms != 400:
        _fail(f"ms={action.ms}")
    print("  ok")


def test_parse_action_key() -> None:
    print("== parse action key ==")
    action = parse_action({"action": "key", "combo": "escape"})
    if action.combo != "escape":
        _fail(f"combo={action.combo}")
    print("  ok")


def test_parse_action_rejects_unknown() -> None:
    print("== parse action rejects unknown ==")
    for bad in [
        {"action": "drag", "x": 0.5, "y": 0.5},
        {"action": "click"},
        {"action": "key"},
        {"action": "wait", "ms": -1},
        {"action": "type"},
        {"action": "scroll", "x": 0.5, "y": 0.5},
        None,
    ]:
        try:
            parse_action(bad)  # type: ignore[arg-type]
            _fail(f"should reject {bad!r}")
        except SchemaError:
            pass
    print("  ok")


def test_parse_action_rejects_bad_coord_space() -> None:
    print("== parse action rejects bad coord_space ==")
    try:
        parse_action({"action": "move", "x": 0.5, "y": 0.5, "coord_space": "pixels"})
        _fail("should reject unknown coord_space")
    except SchemaError:
        pass
    print("  ok")


# -- Observation parsing --

def test_parse_observation_ok() -> None:
    print("== parse observation ok ==")
    obs = parse_observation({
        "run_id": "rid", "step": 1, "ok": True, "error": "",
        "screen": _valid_screen(),
        "image": {"mime": "image/jpeg", "data": _JPEG_B64},
    })
    if obs.run_id != "rid":
        _fail(f"run_id={obs.run_id}")
    if not obs.ok:
        _fail(f"ok={obs.ok}")
    if obs.screen is None:
        _fail("screen is None")
    if obs.image is None:
        _fail("image is None")
    print("  ok")


def test_parse_observation_missing_screen_fails() -> None:
    print("== parse observation missing screen fails ==")
    obs = parse_observation({"run_id": "rid", "step": 1, "ok": True})
    if obs.ok:
        _fail("ok should be False when screen missing")
    if obs.error != "invalid_screen":
        _fail(f"error={obs.error}")
    print("  ok")


def test_parse_observation_rejects_missing_run_id() -> None:
    print("== parse observation rejects missing run_id ==")
    try:
        parse_observation({"step": 1, "ok": True})
        _fail("should reject missing run_id")
    except SchemaError:
        pass
    print("  ok")


def test_parse_screen_partial() -> None:
    print("== parse screen partial ==")
    if parse_screen(None) is not None:
        _fail("None should return None")
    if parse_screen({}) is not None:
        _fail("empty dict should return None")
    screen = parse_screen({
        "origin_x": -1920, "origin_y": 0,
        "phys_w": 1920, "phys_h": 1080,
        "img_w": 1280, "img_h": 720,
    })
    if screen is None:
        _fail("should parse valid screen")
    if screen.origin_x != -1920:
        _fail(f"origin_x={screen.origin_x}")
    print("  ok")


# -- Probe actions: three steps --

def test_probe_actions_order() -> None:
    print("== probe actions order ==")
    actions = probe_actions()
    if len(actions) != 3:
        _fail(f"expected 3 actions, got {len(actions)}")
    if actions[0].action != "move":
        _fail(f"step 1 action={actions[0].action}")
    if actions[0].x != 0.5 or actions[0].y != 0.5:
        _fail(f"step 1 x={actions[0].x} y={actions[0].y}")
    if actions[1].action != "wait":
        _fail(f"step 2 action={actions[1].action}")
    if actions[1].ms != 400:
        _fail(f"step 2 ms={actions[1].ms}")
    if actions[2].action != "key":
        _fail(f"step 3 action={actions[2].action}")
    if actions[2].combo != "escape":
        _fail(f"step 3 combo={actions[2].combo}")
    print("  ok")


# -- Probe loop: success --

def test_run_probe_success() -> None:
    print("== run_probe success ==")
    sent: list[dict[str, Any]] = []

    async def send(payload: dict[str, Any]) -> None:
        sent.append(payload)

    async def wait_obs(run_id: str, step: int) -> ComputerUseObservation | None:
        return _ok_obs(run_id, step)

    result = asyncio.run(run_probe(
        send=send, wait_observation=wait_obs,
        run_id="test-rid", max_steps=8,
    ))
    if not result.ok:
        _fail(f"ok={result.ok} reason={result.reason}")
    if result.run_id != "test-rid":
        _fail(f"run_id={result.run_id}")
    if result.steps_completed != 3:
        _fail(f"steps_completed={result.steps_completed}")
    if len(sent) != 3:
        _fail(f"sent {len(sent)} actions, expected 3")
    for i, payload in enumerate(sent, start=1):
        if payload["type"] != TYPE_COMPUTER_USE_ACTION:
            _fail(f"payload {i} type={payload['type']}")
        if payload["run_id"] != "test-rid":
            _fail(f"payload {i} run_id={payload['run_id']}")
        if payload["step"] != i:
            _fail(f"payload {i} step={payload['step']}")
    if sent[0]["action"] != "move":
        _fail(f"action 1={sent[0]['action']}")
    if sent[1]["action"] != "wait":
        _fail(f"action 2={sent[1]['action']}")
    if sent[2]["action"] != "key":
        _fail(f"action 3={sent[2]['action']}")
    print("  ok")


# -- Probe loop: timeout --

def test_run_probe_timeout() -> None:
    print("== run_probe timeout ==")
    sent: list[dict[str, Any]] = []

    async def send(payload: dict[str, Any]) -> None:
        sent.append(payload)

    async def wait_obs(run_id: str, step: int) -> ComputerUseObservation | None:
        return None

    result = asyncio.run(run_probe(
        send=send, wait_observation=wait_obs,
        run_id="timeout-rid", max_steps=8,
    ))
    if result.ok:
        _fail("ok should be False on timeout")
    if result.reason != "timeout":
        _fail(f"reason={result.reason}")
    if len(sent) != 1:
        _fail(f"sent {len(sent)} actions, expected 1")
    print("  ok")


# -- Probe loop: observation failure --

def test_run_probe_observation_failure() -> None:
    print("== run_probe observation failure ==")
    sent: list[dict[str, Any]] = []

    async def send(payload: dict[str, Any]) -> None:
        sent.append(payload)

    async def wait_obs(run_id: str, step: int) -> ComputerUseObservation | None:
        return ComputerUseObservation(
            run_id=run_id, step=step, ok=False,
            error="sendinput_failed", screen=None, image=None,
        )

    result = asyncio.run(run_probe(
        send=send, wait_observation=wait_obs,
        run_id="fail-rid", max_steps=8,
    ))
    if result.ok:
        _fail("ok should be False")
    if result.reason != "observation_failed":
        _fail(f"reason={result.reason}")
    if len(sent) != 1:
        _fail(f"sent {len(sent)} actions, expected 1")
    print("  ok")


# -- Probe loop: run_id mismatch --

def test_run_probe_run_id_mismatch() -> None:
    print("== run_probe run_id mismatch ==")
    sent: list[dict[str, Any]] = []

    async def send(payload: dict[str, Any]) -> None:
        sent.append(payload)

    async def wait_obs(run_id: str, step: int) -> ComputerUseObservation | None:
        return ComputerUseObservation(
            run_id="wrong-rid", step=step, ok=True,
            error="", screen=parse_screen(_valid_screen()), image=None,
        )

    result = asyncio.run(run_probe(
        send=send, wait_observation=wait_obs,
        run_id="correct-rid", max_steps=8,
    ))
    if result.ok:
        _fail("ok should be False on mismatch")
    if result.reason != "observation_failed":
        _fail(f"reason={result.reason}")
    print("  ok")


# -- Probe loop: abort --

def test_run_probe_abort() -> None:
    print("== run_probe abort ==")
    sent: list[dict[str, Any]] = []

    async def send(payload: dict[str, Any]) -> None:
        sent.append(payload)

    async def wait_obs(run_id: str, step: int) -> ComputerUseObservation | None:
        return _ok_obs(run_id, step)

    def abort_check() -> bool:
        return len(sent) >= 1

    result = asyncio.run(run_probe(
        send=send, wait_observation=wait_obs,
        run_id="abort-rid", max_steps=8,
        abort_check=abort_check,
    ))
    if result.ok:
        _fail("ok should be False on abort")
    if result.reason != "cancelled":
        _fail(f"reason={result.reason}")
    if len(sent) > 1:
        _fail(f"sent {len(sent)} actions, expected at most 1")
    print("  ok")


# -- Probe loop: max_steps zero --

def test_run_probe_max_steps_zero() -> None:
    print("== run_probe max_steps zero ==")
    sent: list[dict[str, Any]] = []

    async def send(payload: dict[str, Any]) -> None:
        sent.append(payload)

    async def wait_obs(run_id: str, step: int) -> ComputerUseObservation | None:
        return _ok_obs(run_id, step)

    result = asyncio.run(run_probe(
        send=send, wait_observation=wait_obs,
        run_id="max-rid", max_steps=0,
    ))
    if result.ok:
        _fail("ok should be False with max_steps=0")
    if result.reason != "max_steps":
        _fail(f"reason={result.reason}")
    if len(sent) != 0:
        _fail(f"sent {len(sent)} actions, expected 0")
    print("  ok")


# -- Terminal messages --

def test_terminal_messages_success() -> None:
    print("== terminal messages success ==")
    result = ProbeResult(
        ok=True, summary="probe complete",
        run_id="rid", steps_completed=3, reason="complete",
    )
    msgs = terminal_messages(result)
    if len(msgs) != 2:
        _fail(f"expected 2 messages, got {len(msgs)}")
    if msgs[0]["type"] != "computer_use_done":
        _fail(f"msg 0 type={msgs[0]['type']}")
    if msgs[0]["ok"] is not True:
        _fail(f"msg 0 ok={msgs[0]['ok']}")
    if msgs[1]["type"] != "chat_response":
        _fail(f"msg 1 type={msgs[1]['type']}")
    if msgs[1]["content"] != "键鼠探针跑完了。":
        _fail(f"msg 1 content={msgs[1]['content']!r}")
    print("  ok")


def test_terminal_messages_timeout() -> None:
    print("== terminal messages timeout ==")
    result = ProbeResult(
        ok=False, summary="timeout",
        run_id="rid", steps_completed=0, reason="timeout",
    )
    msgs = terminal_messages(result)
    if msgs[0]["ok"] is not False:
        _fail(f"done ok={msgs[0]['ok']}")
    if msgs[1]["content"] != "键鼠探针没有跑完。":
        _fail(f"content={msgs[1]['content']!r}")
    print("  ok")


def test_terminal_messages_cancelled() -> None:
    print("== terminal messages cancelled ==")
    result = ProbeResult(
        ok=False, summary="cancelled",
        run_id="rid", steps_completed=0, reason="cancelled",
    )
    msgs = terminal_messages(result)
    if msgs[1]["content"] != "键鼠探针已取消。":
        _fail(f"content={msgs[1]['content']!r}")
    print("  ok")


# -- Protocol helpers --

def test_msg_computer_use_action() -> None:
    print("== msg_computer_use_action ==")
    msg = msg_computer_use_action({"action": "move", "x": 0.5})
    if msg["type"] != TYPE_COMPUTER_USE_ACTION:
        _fail(f"type={msg['type']}")
    if msg["action"] != "move":
        _fail(f"action={msg['action']}")
    print("  ok")


def test_msg_computer_use_done() -> None:
    print("== msg_computer_use_done ==")
    msg = msg_computer_use_done("rid", ok=True, summary="done")
    if msg["type"] != "computer_use_done":
        _fail(f"type={msg['type']}")
    if msg["run_id"] != "rid":
        _fail(f"run_id={msg['run_id']}")
    if msg["ok"] is not True:
        _fail(f"ok={msg['ok']}")
    print("  ok")


# -- Main --

def main() -> None:
    tests = [
        test_probe_token_recognition,
        test_action_whitelist,
        test_parse_action_move,
        test_parse_action_wait,
        test_parse_action_key,
        test_parse_action_rejects_unknown,
        test_parse_action_rejects_bad_coord_space,
        test_parse_observation_ok,
        test_parse_observation_missing_screen_fails,
        test_parse_observation_rejects_missing_run_id,
        test_parse_screen_partial,
        test_probe_actions_order,
        test_run_probe_success,
        test_run_probe_timeout,
        test_run_probe_observation_failure,
        test_run_probe_run_id_mismatch,
        test_run_probe_abort,
        test_run_probe_max_steps_zero,
        test_terminal_messages_success,
        test_terminal_messages_timeout,
        test_terminal_messages_cancelled,
        test_msg_computer_use_action,
        test_msg_computer_use_done,
    ]
    for test in tests:
        test()
    print()
    print(f"All {len(tests)} tests passed.")


if __name__ == "__main__":
    main()
