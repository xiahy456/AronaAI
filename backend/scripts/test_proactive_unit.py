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
from app.memory.store import MemoryStore  # noqa: E402
from app.planner.schema import parse_and_gate_intent  # noqa: E402
from app.proactive.care import (  # noqa: E402
    HISTORY_CARE_MARKER,
    build_care_instruction,
    in_window,
    should_fire_care,
)
from app.proactive.festival import (  # noqa: E402
    HISTORY_FESTIVAL_MARKER,
    match_festival,
    needs_rest_followup,
    parse_birthday_md,
)
from app.proactive.goal import (  # noqa: E402
    HISTORY_GOAL_MARKER,
    can_attempt_goal,
    select_goal,
    wants_goal_mute,
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
    goal_ok = decide_proactive(play, "goal")
    if goal_ok.action != "initiate":
        _fail(f"secure_play goal should initiate, got {goal_ok.action}")
    goal_cling = decide_proactive(cling, "goal")
    if goal_cling.action != "silence":
        _fail(f"cling goal should silence, got {goal_cling.action}")
    if map_arona_act("initiate", "secure_play", motive_kind="goal") != "checked_in":
        _fail("goal initiate should be checked_in")
    fest = decide_proactive(cling, "festival")
    if fest.action != "initiate":
        _fail(f"cling festival should still initiate, got {fest.action}")
    if map_arona_act("initiate", "secure_play", motive_kind="festival") != "greeted":
        _fail("festival initiate should be greeted")
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
    picked = sched.pick_motive(
        noon,
        last_user_act="other",
        climate="secure_play",
        goals=_sample_goals(),
    )
    if picked is None or picked.kind != "lunch":
        _fail(f"expected lunch over goal/idle, got {picked}")
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
    print("== config idle / care / goal / continue ==")
    cfg = load_config()
    if not cfg.proactive.idle.enabled:
        _fail("idle should default enabled")
    if cfg.proactive.idle.after_sec <= 0:
        _fail(f"after_sec {cfg.proactive.idle.after_sec}")
    if "proactive.json" not in cfg.proactive.care.persist_path:
        _fail(f"persist_path {cfg.proactive.care.persist_path}")
    if cfg.proactive.care.lunch_start != "12:00":
        _fail("lunch_start")
    if not cfg.proactive.goal.enabled:
        _fail("goal should default enabled")
    if cfg.proactive.goal.min_after_user_sec != 300:
        _fail(f"min_after_user_sec {cfg.proactive.goal.min_after_user_sec}")
    if cfg.proactive.goal.cooldown_sec != 21600:
        _fail(f"goal cooldown {cfg.proactive.goal.cooldown_sec}")
    if cfg.proactive.goal.mute_sec != 604800:
        _fail(f"mute_sec {cfg.proactive.goal.mute_sec}")
    if cfg.proactive.goal.max_per_day != 1:
        _fail(f"goal max_per_day {cfg.proactive.goal.max_per_day}")
    if not cfg.proactive.continue_line.enabled:
        _fail("continue should default enabled")
    if cfg.proactive.continue_line.delay_sec != 2:
        _fail(f"delay_sec {cfg.proactive.continue_line.delay_sec}")
    if not cfg.proactive.festival.enabled:
        _fail("festival should default enabled")
    print("  ok")


def _goal_cfg(**overrides: object) -> SimpleNamespace:
    base: dict[str, object] = {
        "enabled": True,
        "min_after_user_sec": 300,
        "cooldown_sec": 21600,
        "mute_sec": 604800,
        "max_per_day": 1,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _sample_goals() -> list[dict[str, object]]:
    return [
        {"key": "old_trip", "content": "老师想去海边", "updated_at": 100.0},
        {"key": "new_exam", "content": "老师要准备考试", "updated_at": 200.0},
    ]


def test_list_by_category() -> None:
    print("== list_by_category ==")
    cfg = load_config()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        store = MemoryStore(cfg, db_path=Path(tmp) / "memory.db")
        with store._connect() as conn:
            conn.execute(
                "INSERT INTO memories(key, content, category, updated_at, source) "
                "VALUES (?, ?, ?, ?, ?)",
                ("old_trip", "老师想去海边", "goal", 100.0, "test"),
            )
            conn.execute(
                "INSERT INTO memories(key, content, category, updated_at, source) "
                "VALUES (?, ?, ?, ?, ?)",
                ("drink", "老师喜欢草莓牛奶", "preference", 200.0, "test"),
            )
            conn.commit()
        goals = store.list_by_category("goal")
        if len(goals) != 1 or goals[0]["key"] != "old_trip":
            _fail(f"expected one goal, got {goals}")
        prefs = store.list_by_category("preference")
        if len(prefs) != 1 or prefs[0]["key"] != "drink":
            _fail(f"expected preference, got {prefs}")
        if store.list_by_category("missing"):
            _fail("missing category should be empty")
    print("  ok")


def test_goal_fire_rules() -> None:
    print("== goal cooldown / daily / mute / select ==")
    now = datetime(2026, 8, 13, 15, 0, 0)
    if not can_attempt_goal(
        now,
        last_user_at=now - timedelta(seconds=400),
        last_user_act="other",
        goal_count=0,
        min_after_user_sec=300,
        max_per_day=1,
    ):
        _fail("goal should be attemptable after quiet afternoon")
    if can_attempt_goal(
        now,
        last_user_at=now - timedelta(seconds=60),
        last_user_act="other",
        goal_count=0,
        min_after_user_sec=300,
        max_per_day=1,
    ):
        _fail("too soon after user should not goal")
    if can_attempt_goal(
        now,
        last_user_at=now - timedelta(seconds=400),
        last_user_act="other",
        goal_count=1,
        min_after_user_sec=300,
        max_per_day=1,
    ):
        _fail("daily cap should block goal")
    if can_attempt_goal(
        now,
        last_user_at=now - timedelta(seconds=400),
        last_user_act="depart",
        goal_count=0,
        min_after_user_sec=300,
        max_per_day=1,
    ):
        _fail("depart should block goal")
    night = datetime(2026, 8, 13, 23, 10, 0)
    if can_attempt_goal(
        night,
        last_user_at=night - timedelta(seconds=400),
        last_user_act="other",
        goal_count=0,
        min_after_user_sec=300,
        max_per_day=1,
    ):
        _fail("rest slot should not goal")

    picked = select_goal(
        _sample_goals(), now, goal_last={}, goal_mute={}, cooldown_sec=21600
    )
    if picked is None or picked["key"] != "old_trip":
        _fail(f"never-visited should pick oldest updated_at, got {picked}")

    recent = (now - timedelta(hours=1)).isoformat(timespec="seconds")
    picked = select_goal(
        _sample_goals(),
        now,
        goal_last={"old_trip": recent},
        goal_mute={},
        cooldown_sec=21600,
    )
    if picked is None or picked["key"] != "new_exam":
        _fail(f"cooling old_trip should pick new_exam, got {picked}")

    mute_until = (now + timedelta(days=7)).isoformat(timespec="seconds")
    picked = select_goal(
        _sample_goals(),
        now,
        goal_last={},
        goal_mute={"old_trip": mute_until},
        cooldown_sec=21600,
    )
    if picked is None or picked["key"] != "new_exam":
        _fail(f"muted old_trip should pick new_exam, got {picked}")

    cooling = now.isoformat(timespec="seconds")
    if (
        select_goal(
            _sample_goals(),
            now,
            goal_last={"old_trip": cooling, "new_exam": cooling},
            goal_mute={},
            cooldown_sec=21600,
        )
        is not None
    ):
        _fail("both cooling should pick none")
    if HISTORY_GOAL_MARKER != "【回访】":
        _fail("goal history marker")
    print("  ok")


def test_mute_last_goal_phrase(tmp: Path) -> None:
    print("== 先别提 mutes last goal key ==")
    if not wants_goal_mute("先别提这个了"):
        _fail("先别提 should mute")
    if not wants_goal_mute("别再问了"):
        _fail("别再问 should mute")
    if not wants_goal_mute("不用提了"):
        _fail("不用提了 should mute")
    if wants_goal_mute("今天天气不错"):
        _fail("plain chat should not mute")

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
    sched = ProactiveScheduler(
        tmp / "proactive_mute.json",
        idle_cfg=idle_cfg,
        care_cfg=care_cfg,
        goal_cfg=_goal_cfg(max_per_day=2),
    )
    now = datetime(2026, 8, 13, 15, 0, 0)
    sched.mark_fired("goal", now, goal_key="old_trip")
    if sched.state.last_goal_key != "old_trip":
        _fail(f"last_goal_key {sched.state.last_goal_key}")
    muted = sched.mute_last_goal(now)
    if muted != "old_trip" or "old_trip" not in sched.state.goal_mute:
        _fail(f"mute should record old_trip, got {muted} {sched.state.goal_mute}")
    picked = select_goal(
        _sample_goals(),
        now,
        goal_last=sched.state.goal_last,
        goal_mute=sched.state.goal_mute,
        cooldown_sec=21600,
    )
    if picked is None or picked["key"] != "new_exam":
        _fail(f"muted last key should skip old_trip, got {picked}")
    print("  ok")


def test_goal_after_welcome_not_blocked_by_idle(tmp: Path) -> None:
    print("== welcome after_sec ok; goal ignores idle cooldown ==")
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
    sched = ProactiveScheduler(
        tmp / "proactive_goal_welcome.json",
        idle_cfg=idle_cfg,
        care_cfg=care_cfg,
        goal_cfg=_goal_cfg(),
    )
    now = datetime(2026, 8, 13, 15, 10, 0)
    sched.note_user_activity(now - timedelta(seconds=400))
    sched.note_proactive(now - timedelta(seconds=60))
    picked = sched.pick_motive(
        now,
        last_user_act="other",
        climate="secure_play",
        goals=_sample_goals(),
    )
    if picked is None or picked.kind != "goal":
        _fail(f"welcome 1min ago should still allow goal, got {picked}")

    sched.mark_fired("idle", now - timedelta(seconds=60))
    later = now
    blocked_idle = sched.pick_motive(
        later,
        last_user_act="other",
        climate="secure_play",
        goals=[],
    )
    if blocked_idle is not None and blocked_idle.kind == "idle":
        _fail("idle cooldown should still hold without goals")
    still_goal = sched.pick_motive(
        later,
        last_user_act="other",
        climate="secure_play",
        goals=_sample_goals(),
    )
    if still_goal is None or still_goal.kind != "goal":
        _fail(f"idle cooldown must not block goal, got {still_goal}")
    print("  ok")


def test_festival_calendar_and_once(tmp: Path) -> None:
    print("== festival calendar / welcome swap / rest followup ==")
    if parse_birthday_md("老师的生日是3月15日") != (3, 15):
        _fail("cn birthday parse")
    if parse_birthday_md("1990-03-15") != (3, 15):
        _fail("iso birthday parse")
    if parse_birthday_md("03-15") != (3, 15):
        _fail("md birthday parse")
    if parse_birthday_md("今天天气不错") is not None:
        _fail("plain text should not parse as birthday")

    national = match_festival(datetime(2026, 10, 1, 10, 0, 0))
    if national is None or national.id != "national" or national.name != "国庆节":
        _fail(f"expected national day, got {national}")
    lantern = match_festival(datetime(2026, 3, 3, 8, 0, 0))
    if lantern is None or lantern.id != "lantern":
        _fail(f"expected lantern, got {lantern}")
    bday = match_festival(
        datetime(2026, 10, 1, 10, 0, 0),
        birthday_content="老师的生日是10月1日",
    )
    if bday is None or bday.id != "birthday":
        _fail(f"birthday should win over national, got {bday}")
    if match_festival(datetime(2026, 8, 13, 15, 0, 0)) is not None:
        _fail("Aug 13 2026 is not a festival")
    if HISTORY_FESTIVAL_MARKER != "【节日】":
        _fail("festival history marker")

    if not needs_rest_followup(datetime(2026, 10, 1, 23, 10, 0)):
        _fail("night should allow rest followup")
    if not needs_rest_followup(datetime(2026, 10, 1, 2, 0, 0)):
        _fail("late_night should allow rest followup")
    if needs_rest_followup(datetime(2026, 10, 1, 15, 0, 0)):
        _fail("afternoon festival should be a single line")

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
    sched = ProactiveScheduler(
        tmp / "proactive_festival.json",
        idle_cfg=idle_cfg,
        care_cfg=care_cfg,
        festival_cfg=SimpleNamespace(enabled=True),
    )
    noon = datetime(2026, 10, 1, 12, 10, 0)
    sched.note_user_activity(noon - timedelta(seconds=2000))
    first = sched.pending_festival(noon)
    if first is None or first.id != "national":
        _fail(f"first login should pending national, got {first}")
    picked = sched.pick_motive(noon, last_user_act="other", climate="secure_play")
    if picked is None or picked.kind != "festival":
        _fail(f"festival should beat lunch, got {picked}")
    sched.mark_fired("festival", noon, festival_id="national")
    if sched.pending_festival(noon) is not None:
        _fail("second welcome same day should not swap to festival")
    again = sched.pick_motive(noon, last_user_act="other", climate="secure_play")
    if again is None or again.kind != "lunch":
        _fail(f"after festival, lunch should fire, got {again}")

    night = datetime(2026, 10, 1, 23, 10, 0)
    night_sched = ProactiveScheduler(
        tmp / "proactive_festival_night.json",
        idle_cfg=idle_cfg,
        care_cfg=care_cfg,
        festival_cfg=SimpleNamespace(enabled=True),
    )
    night_picked = night_sched.pick_motive(night, last_user_act="other")
    if night_picked is None or night_picked.kind != "festival":
        _fail(f"REST_SLOTS should still festival, got {night_picked}")
    night_sched.mark_fired("festival", night, festival_id="national")
    night_sched.mark_fired("sleep", night)
    blocked_sleep = night_sched.pick_motive(night, last_user_act="other")
    if blocked_sleep is not None and blocked_sleep.kind in {"festival", "sleep"}:
        _fail(f"after rest followup, sleep/festival should be done, got {blocked_sleep}")

    depart_sched = ProactiveScheduler(
        tmp / "proactive_festival_depart.json",
        idle_cfg=idle_cfg,
        care_cfg=care_cfg,
        festival_cfg=SimpleNamespace(enabled=True),
    )
    departed = depart_sched.pick_motive(
        datetime(2026, 10, 1, 16, 0, 0),
        last_user_act="depart",
    )
    if departed is not None and departed.kind == "festival":
        _fail("tick should skip festival after depart")
    if depart_sched.pending_festival(datetime(2026, 10, 1, 16, 0, 0)) is None:
        _fail("welcome swap should still see pending festival after depart")
    print("  ok")


def test_followup_ok_default_and_gate() -> None:
    print("== followup_ok default false; draft gate ==")
    legacy = parse_and_gate_intent(
        '{"user_emotion":"平静","topic":"问候","stance":"回应",'
        '"must_say":["问好"],"must_not":[],"facts_to_use":[],'
        '"tone":"温柔","length":"1-2句","arona_emotion":"smile"}'
    )
    if legacy is not None:
        _fail("legacy card without draft must fail gate")

    raw = '{"draft":"老师好，今天也请多指教。","arona_emotion":"smile"}'
    card = parse_and_gate_intent(raw)
    if card is None:
        _fail("card should parse")
    if card.followup_ok:
        _fail("followup_ok should default false")
    if "followup_ok" in card.to_renderer_dict():
        _fail("followup_ok must not go to renderer")
    if card.to_renderer_draft() != "老师好，今天也请多指教。":
        _fail(f"unexpected draft: {card.to_renderer_draft()!r}")

    raw_ok = (
        '{"draft":"光环是阿洛娜身份的一部分，我可以慢慢讲给老师听。",'
        '"arona_emotion":"smile","followup_ok":true}'
    )
    gated = parse_and_gate_intent(raw_ok)
    if gated is None or not gated.followup_ok:
        _fail("followup_ok true should survive parse")
    print("  ok")


def test_continue_renderer_split_and_skip() -> None:
    print("== continue: planner system event; renderer draft only; too_similar ==")
    from app.planner.schema import IntentCard
    from app.prompt import build_renderer_messages
    from app.proactive.followup import (
        build_continue_instruction,
        last_teacher_utterance,
        should_skip_continue,
        too_similar,
    )

    previous = "老师今天过得真好！"
    history = [
        {"role": "user", "content": "我今天过得很好"},
        {"role": "assistant", "content": previous},
    ]
    if last_teacher_utterance(history) != "我今天过得很好":
        _fail("last teacher should skip Arona's previous line")

    instruction = build_continue_instruction(previous)
    if "【系统事件】" not in instruction or "上一句是：" not in instruction:
        _fail("Planner continue instruction still needs system event + previous line")
    if "与上一句不同的新信息" not in instruction:
        _fail("continue instruction must require new information")
    if "已经回答过的问题" not in instruction:
        _fail("continue instruction must forbid re-asking answered questions")

    draft = "那明天要不要一起去买草莓牛奶？"
    card = IntentCard(draft=draft, arona_emotion="smile", followup_ok=False)
    cfg = load_config()
    msgs = build_renderer_messages(
        cfg,
        draft=card.to_renderer_draft(),
        history=history,
        max_history_turns=2,
    )
    payload = msgs[-1]["content"]
    if "【意图草稿】" not in payload:
        _fail("Renderer payload needs 【意图草稿】")
    if draft not in payload:
        _fail("Renderer payload should contain draft")
    if "【系统事件】" in payload:
        _fail("Renderer payload must not contain 【系统事件】")
    if "上一句是：" in payload:
        _fail("Renderer payload must not contain 上一句是：")
    if "【老师原话】" in payload:
        _fail("Renderer payload must not contain 【老师原话】")
    if "【回复意图卡】" in payload:
        _fail("Renderer payload must not contain JSON intent card header")
    if "我今天过得很好" in payload or previous in payload:
        _fail("Renderer must not see teacher utterance or previous Arona line")

    if not should_skip_continue("老师今天过得真好！还去了哪里呢？"):
        _fail("two-sentence first reply should skip continue")
    if should_skip_continue("老师今天过得真好！"):
        _fail("one-sentence first reply should still allow continue")
    if should_skip_continue(""):
        _fail("empty previous is not a two-sentence skip")

    if not too_similar("老师今天过得真好！", "老师今天过得真好"):
        _fail("punctuation-only difference is similar")
    if not too_similar("老师今天过得真好！", "老师今天过得真好呀~"):
        _fail("near restatement should be similar")
    if too_similar("老师今天过得真好！", "那明天要不要一起去买草莓牛奶？"):
        _fail("new information should not be similar")
    if too_similar("", "补一句"):
        _fail("empty previous is not similar")
    print("  ok")


def main() -> None:
    test_idle_fire_rules()
    test_care_window_once_per_day()
    test_decide_proactive_policy()
    test_list_by_category()
    test_goal_fire_rules()
    test_followup_ok_default_and_gate()
    test_continue_renderer_split_and_skip()
    with tempfile.TemporaryDirectory() as tmp:
        test_scheduler_persist_and_priority(Path(tmp))
        test_welcome_does_not_eat_idle_cooldown(Path(tmp))
        test_mute_last_goal_phrase(Path(tmp))
        test_goal_after_welcome_not_blocked_by_idle(Path(tmp))
        test_festival_calendar_and_once(Path(tmp))
    test_hub_busy()
    test_config_loads()
    print("ALL PASS")


if __name__ == "__main__":
    main()
