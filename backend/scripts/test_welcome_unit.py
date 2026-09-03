"""Unit tests for proactive welcome slots/state/instructions (no GGUF).

Run from backend/:
  python scripts/test_welcome_unit.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.proactive import (  # noqa: E402
    WelcomeState,
    build_welcome_instruction,
    resolve_slot,
    resolve_welcome_context,
)
from app.proactive.slots import REST_SLOTS  # noqa: E402


def _fail(msg: str) -> None:
    raise AssertionError(msg)


def test_resolve_slot_hours() -> None:
    print("== resolve_slot by hour ==")
    cases = [
        (0, "late_night"),
        (4, "late_night"),
        (5, "morning"),
        (8, "morning"),
        (9, "forenoon"),
        (11, "forenoon"),
        (12, "noon"),
        (13, "noon"),
        (14, "afternoon"),
        (17, "afternoon"),
        (18, "evening"),
        (22, "evening"),
        (23, "night"),
    ]
    for hour, expected in cases:
        dt = datetime(2026, 8, 13, hour, 30, 0)
        slot = resolve_slot(dt)
        if slot.slot_id != expected:
            _fail(f"hour={hour} expected={expected} got={slot.slot_id}")
        if slot.date_key != "2026-08-13":
            _fail(f"date_key mismatch for hour={hour}: {slot.date_key}")
    print("  ok")


def test_welcome_state_same_slot_and_cross_day() -> None:
    print("== WelcomeState first / mark / cross-day ==")
    state = WelcomeState()
    morning = datetime(2026, 8, 13, 7, 0, 0)
    slot, first = resolve_welcome_context(state, morning)
    if not first or slot.slot_id != "morning":
        _fail(f"expected first morning, got first={first} slot={slot.slot_id}")
    state.mark_period_greeted(slot.date_key, slot.slot_id)

    slot2, first2 = resolve_welcome_context(state, datetime(2026, 8, 13, 8, 0, 0))
    if first2 or slot2.slot_id != "morning":
        _fail(f"expected second morning first=False, got first={first2}")

    # Different slot same day → first again
    slot3, first3 = resolve_welcome_context(state, datetime(2026, 8, 13, 15, 0, 0))
    if not first3 or slot3.slot_id != "afternoon":
        _fail(f"expected first afternoon, got first={first3} slot={slot3.slot_id}")

    # Next day same clock hour → first again
    slot4, first4 = resolve_welcome_context(state, datetime(2026, 8, 14, 7, 0, 0))
    if not first4 or slot4.slot_id != "morning":
        _fail(f"expected next-day morning first=True, got first={first4}")
    print("  ok")


def test_welcome_state_persists_across_reload() -> None:
    print("== WelcomeState persist / reload / prune ==")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "welcome.json"
        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        state = WelcomeState(path)
        slot, first = resolve_welcome_context(state, now)
        if not first:
            _fail("expected first greeting before mark")
        state.mark_period_greeted(slot.date_key, slot.slot_id)

        reloaded = WelcomeState(path)
        slot2, first2 = resolve_welcome_context(reloaded, now)
        if first2 or slot2.slot_id != slot.slot_id:
            _fail(
                f"reload should keep same-slot greeted, got first={first2} slot={slot2.slot_id}"
            )

        tomorrow = now + timedelta(days=1)
        slot3, first3 = resolve_welcome_context(reloaded, tomorrow)
        if not first3:
            _fail("next-day same clock should be first again")

        stale = datetime(2020, 1, 1, 15, 0, 0)
        stale_slot = resolve_slot(stale)
        reloaded.mark_period_greeted(stale_slot.date_key, stale_slot.slot_id)
        raw = json.loads(path.read_text(encoding="utf-8"))
        for item in raw.get("period_greeted") or []:
            if item and item[0] == "2020-01-01":
                _fail(f"stale date should be pruned on save: {raw}")
    print("  ok")


def test_build_welcome_instruction() -> None:
    print("== build_welcome_instruction intents ==")
    late = resolve_slot(datetime(2026, 8, 13, 2, 0, 0))
    night = resolve_slot(datetime(2026, 8, 13, 23, 30, 0))
    morning = resolve_slot(datetime(2026, 8, 13, 7, 0, 0))

    for slot in (late, night):
        if slot.slot_id not in REST_SLOTS:
            _fail(f"{slot.slot_id} should be REST_SLOTS")
        text = build_welcome_instruction(slot, first_in_slot=True)
        if "休息" not in text:
            _fail(f"rest slot instruction missing 休息: {text}")
        if "早上好" in text and "不要说「早上好」" not in text:
            # Allowed only as negation
            pass
        if "注意休息" not in text and "休息" not in text:
            _fail(f"expected rest intent: {text}")

    morning_first = build_welcome_instruction(morning, first_in_slot=True)
    if "早上好" not in morning_first:
        _fail(f"morning first should ask 早上好: {morning_first}")

    morning_again = build_welcome_instruction(morning, first_in_slot=False)
    if "欢迎回来" not in morning_again and "老师好" not in morning_again:
        _fail(f"repeat should mention 老师好/欢迎回来: {morning_again}")
    if "请主动向老师说早上好" in morning_again:
        _fail(f"repeat must not require 早上好: {morning_again}")
    if "不要再说「早上好" not in morning_again:
        _fail(f"repeat should forbid period greetings: {morning_again}")

    if "【系统事件】" not in morning_first:
        _fail("instruction must include 【系统事件】")
    print("  ok")


def main() -> None:
    test_resolve_slot_hours()
    test_welcome_state_same_slot_and_cross_day()
    test_welcome_state_persists_across_reload()
    test_build_welcome_instruction()
    print("ALL PASS")


if __name__ == "__main__":
    main()
