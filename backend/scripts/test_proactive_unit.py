"""Unit tests for idle / care motives and scheduler (no GGUF).

Run from backend/:
  python scripts/test_proactive_unit.py
"""

from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import load_config  # noqa: E402
from app.proactive.care import (  # noqa: E402
    HISTORY_CARE_MARKER,
    build_care_instruction,
    in_window,
    should_fire_care,
)
from app.proactive.hub import ConnectionHub  # noqa: E402
from app.proactive.idle import (  # noqa: E402
    HISTORY_IDLE_MARKER,
    build_idle_instruction,
    should_fire_idle,
)
from app.proactive.scheduler import ProactiveScheduler  # noqa: E402
from app.relationship.events import ARONA_DELTAS  # noqa: E402
from app.relationship.policy import decide_proactive, map_arona_act  # noqa: E402
from app.relationship.state import RelationshipState  # noqa: E402


def _fail(msg: str) -> None:
    raise AssertionError(msg)


def _idle_kwargs(**overrides: object) -> dict[str, object]:
    now = datetime(2026, 8, 13, 15, 0, 0)
    base: dict[str, object] = {
        "last_user_at": now - timedelta(seconds=1000),
        "last_proactive_at": now - timedelta(seconds=2000),
        "last_idle_at": None,
        "idle_count": 0,
        "last_user_act": "other",
        "after_sec": 900,
        "cooldown_sec": 1800,
        "max_per_day": 3,
    }
    base.update(overrides)
    return base


def test_idle_fire_rules() -> None:
    print("== idle fire / cooldown / rest / depart ==")
    now = datetime(2026, 8, 13, 15, 0, 0)
    if not should_fire_idle(now, **_idle_kwargs()):  # type: ignore[arg-type]
        _fail("expected idle to fire after quiet afternoon")
    if should_fire_idle(now, **_idle_kwargs(last_user_at=None)):  # type: ignore[arg-type]
        _fail("no last_user_at should not idle")
    if should_fire_idle(now, **_idle_kwargs(last_user_at=now - timedelta(seconds=100))):  # type: ignore[arg-type]
        _fail("too soon after user should not idle")
    if should_fire_idle(
        now, **_idle_kwargs(last_proactive_at=now - timedelta(seconds=60))
    ):  # type: ignore[arg-type]
        _fail("welcome gap (after_sec) should block idle")
    if should_fire_idle(
        now, **_idle_kwargs(last_idle_at=now - timedelta(seconds=60))
    ):  # type: ignore[arg-type]
        _fail("idle-to-idle cooldown should block")
    if should_fire_idle(now, **_idle_kwargs(idle_count=3)):  # type: ignore[arg-type]
        _fail("daily cap should block idle")
    if should_fire_idle(now, **_idle_kwargs(last_user_act="depart")):  # type: ignore[arg-type]
        _fail("depart should block idle")
    night = datetime(2026, 8, 13, 23, 10, 0)
    if should_fire_idle(night, **_idle_kwargs()):  # type: ignore[arg-type]
        _fail("rest slot should not idle")
    late = datetime(2026, 8, 13, 2, 0, 0)
    if should_fire_idle(
        late,
        **_idle_kwargs(  # type: ignore[arg-type]
            last_user_at=late - timedelta(seconds=1000),
            last_proactive_at=late - timedelta(seconds=2000),
        ),
    ):
        _fail("late_night should not idle")
    text = build_idle_instruction()
    if "还在不在" not in text or HISTORY_IDLE_MARKER != "【搭话】":
        _fail("idle instruction missing presence ban")
    print("  ok")


def test_care_window_once_per_day() -> None:
    print("== care window / daily once ==")
    lunch = datetime(2026, 8, 13, 12, 10, 0)
    if not in_window(lunch, "12:00", "12:30"):
        _fail("12:10 should be in lunch window")
    if in_window(datetime(2026, 8, 13, 12, 30, 0), "12:00", "12:30"):
        _fail("12:30 should be exclusive end")
    if not should_fire_care(
        "lunch", lunch, done_today=[], start="12:00", end="12:30"
    ):
        _fail("lunch should fire in window")
    if should_fire_care(
        "lunch", lunch, done_today=["lunch"], start="12:00", end="12:30"
    ):
        _fail("lunch already done today")
    sleep = datetime(2026, 8, 13, 23, 5, 0)
    if not should_fire_care(
        "sleep", sleep, done_today=[], start="23:00", end="23:20"
    ):
        _fail("sleep should fire in window")
    if should_fire_care(
        "sleep", datetime(2026, 8, 13, 15, 0, 0), done_today=[], start="23:00", end="23:20"
    ):
        _fail("afternoon is not sleep window")
    text = build_care_instruction("lunch", climate="cling_risk")
    if "更短" not in text or HISTORY_CARE_MARKER != "【提醒】":
        _fail("cling care should be shorter")
    print("  ok")


def test_decide_proactive_policy() -> None:
    print("== cling_risk vetoes idle, allows short care ==")
    cling = RelationshipState(trust=0.5, dependence=0.70, tension=0.15)
    idle = decide_proactive(cling, "idle")
    if idle.action != "silence" or idle.climate != "cling_risk":
        _fail(f"cling idle should silence, got {idle.action} {idle.climate}")
    care = decide_proactive(cling, "lunch")
    if care.action != "initiate":
        _fail(f"cling care should still initiate, got {care.action}")
    if "索取确认" not in care.stance:
        _fail(f"cling care stance should be short: {care.stance}")

    play = RelationshipState(trust=0.6, dependence=0.30, tension=0.30)
    ok = decide_proactive(play, "idle")
    if ok.action != "initiate" or ok.climate != "secure_play":
        _fail(f"secure_play idle should initiate, got {ok.action} {ok.climate}")

    tool = RelationshipState(trust=0.10, dependence=0.10, tension=0.10)
    blocked = decide_proactive(tool, "idle")
    if blocked.action != "silence":
        _fail("cold_tool should not idle")

    if map_arona_act("initiate", "secure_play") != "greeted":
        _fail("welcome initiate stays greeted")
    if map_arona_act("initiate", "secure_play", motive_kind="idle") != "checked_in":
        _fail("idle initiate should be checked_in")
    if map_arona_act("initiate", "secure_play", motive_kind="lunch") != "cared":
        _fail("care initiate should be cared")
    if ARONA_DELTAS["checked_in"][1] != 0.0:
        _fail("checked_in must not raise dependence")
    if ARONA_DELTAS["cared"][1] != 0.0:
        _fail("cared must not raise dependence")
    print("  ok")


def test_scheduler_persist_and_priority(tmp: Path) -> None:
    print("== scheduler persist / care over idle ==")
    idle_cfg = SimpleNamespace(
        enabled=True, after_sec=900, cooldown_sec=1800, max_per_day=3
    )
    care_cfg = SimpleNamespace(
        enabled=True,
        lunch_start="12:00",
        lunch_end="12:30",
        sleep_start="23:00",
        sleep_end="23:20",
    )
    path = tmp / "proactive.json"
    sched = ProactiveScheduler(path, idle_cfg=idle_cfg, care_cfg=care_cfg)
    noon = datetime(2026, 8, 13, 12, 10, 0)
    sched.note_user_activity(noon - timedelta(seconds=2000))
    sched.note_proactive(noon - timedelta(seconds=2000))
    picked = sched.pick_motive(noon, last_user_act="other", climate="secure_play")
    if picked is None or picked.kind != "lunch":
        _fail(f"expected lunch over idle, got {picked}")
    sched.mark_fired("lunch", noon)
    again = sched.pick_motive(noon, last_user_act="other")
    if again is not None and again.kind == "lunch":
        _fail("lunch should not fire twice the same day")

    loaded = ProactiveScheduler(path, idle_cfg=idle_cfg, care_cfg=care_cfg)
    if "lunch" not in loaded.state.care_done:
        _fail("care_done should persist")

    afternoon = datetime(2026, 8, 13, 15, 0, 0)
    idle = loaded.pick_motive(afternoon, last_user_act="other")
    if idle is None or idle.kind != "idle":
        _fail(f"expected idle in afternoon, got {idle}")
    loaded.mark_fired("idle", afternoon)
    if loaded.state.idle_count != 1:
        _fail(f"idle_count {loaded.state.idle_count}")
    if not loaded.state.last_idle_at:
        _fail("last_idle_at should be set after idle")
    print("  ok")


def test_welcome_does_not_eat_idle_cooldown(tmp: Path) -> None:
    print("== welcome after_sec ok; idle cooldown still holds ==")
    idle_cfg = SimpleNamespace(
        enabled=True, after_sec=30, cooldown_sec=1800, max_per_day=10
    )
    care_cfg = SimpleNamespace(
        enabled=True,
        lunch_start="12:00",
        lunch_end="12:30",
        sleep_start="23:00",
        sleep_end="23:20",
    )
    path = tmp / "proactive_welcome_idle.json"
    sched = ProactiveScheduler(path, idle_cfg=idle_cfg, care_cfg=care_cfg)
    now = datetime(2026, 8, 13, 15, 10, 0)
    welcome_at = now - timedelta(seconds=240)
    user_at = now - timedelta(seconds=40)
    sched.note_user_activity(user_at)
    sched.note_proactive(welcome_at)
    picked = sched.pick_motive(now, last_user_act="other")
    if picked is None or picked.kind != "idle":
        _fail(f"welcome 4min ago + after_sec=30 should idle, got {picked}")

    sched.mark_fired("idle", now)
    soon = now + timedelta(seconds=60)
    blocked = sched.pick_motive(soon, last_user_act="other")
    if blocked is not None and blocked.kind == "idle":
        _fail("second idle should wait cooldown_sec")
    reason = sched.idle_block_reason(soon, last_user_act="other")
    if reason is None or "idle_cooldown" not in reason:
        _fail(f"expected idle_cooldown reason, got {reason}")
    print("  ok")


def test_hub_busy() -> None:
    print("== hub busy filter ==")
    hub = ConnectionHub()

    async def _send(_payload: dict) -> None:
        return None

    hub.register("a", _send)
    hub.register("b", _send)
    hub.set_busy("a", True)
    idle = hub.idle_sessions()
    if len(idle) != 1 or idle[0][0] != "b":
        _fail(f"expected only b idle, got {idle}")
    hub.unregister("b")
    if hub.idle_sessions():
        _fail("no idle sessions after unregister")
    print("  ok")


def test_config_loads() -> None:
    print("== config idle / care ==")
    cfg = load_config()
    if not cfg.proactive.idle.enabled:
        _fail("idle should default enabled")
    if cfg.proactive.idle.after_sec <= 0:
        _fail(f"after_sec {cfg.proactive.idle.after_sec}")
    if "proactive.json" not in cfg.proactive.care.persist_path:
        _fail(f"persist_path {cfg.proactive.care.persist_path}")
    if cfg.proactive.care.lunch_start != "12:00":
        _fail("lunch_start")
    print("  ok")


def main() -> None:
    test_idle_fire_rules()
    test_care_window_once_per_day()
    test_decide_proactive_policy()
    with tempfile.TemporaryDirectory() as tmp:
        test_scheduler_persist_and_priority(Path(tmp))
        test_welcome_does_not_eat_idle_cooldown(Path(tmp))
    test_hub_busy()
    test_config_loads()
    print("ALL PASS")


if __name__ == "__main__":
    main()
