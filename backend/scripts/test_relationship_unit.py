"""Unit tests for relationship climate (no GGUF).

Run from backend/:
  python scripts/test_relationship_unit.py
"""

from __future__ import annotations

import sys
import tempfile
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import load_config  # noqa: E402
from app.planner.prompts import build_planner_user_message  # noqa: E402
from app.proactive.welcome import build_welcome_instruction  # noqa: E402
from app.proactive.slots import resolve_slot  # noqa: E402
from app.relationship import (  # noqa: E402
    RelationshipEngine,
    RelationshipSettings,
    RelationshipState,
    RelationshipStore,
    classify_user_act,
    planner_climate_block,
    resolve_climate,
)
from app.planner.schema import parse_and_gate_intent  # noqa: E402
from app.proactive import WELCOME_MEMORY_QUERY  # noqa: E402
from app.relationship.events import ARONA_DELTAS, USER_DELTAS  # noqa: E402
from app.relationship.policy import decide, map_arona_act, stick_climate  # noqa: E402


def _fail(msg: str) -> None:
    raise AssertionError(msg)


def test_apply_delta_formula() -> None:
    print("== apply_delta formula ==")
    state = RelationshipState(trust=0.50, dependence=0.30, tension=0.20, day="2026-08-13")
    # new = old + α*Δ - β*(old-baseline); beta=0 so pure increment
    applied = state.apply_delta(
        (0.10, 0.0, 0.0),
        alpha=0.3,
        beta=0.0,
        baseline=(0.55, 0.30, 0.25),
        daily_abs_cap=1.0,
        now=datetime(2026, 8, 13, 12, 0, 0),
    )
    expected = 0.50 + 0.3 * 0.10
    if abs(state.trust - expected) > 1e-9:
        _fail(f"trust {state.trust} != {expected}")
    if abs(applied[0] - 0.03) > 1e-9:
        _fail(f"applied trust {applied[0]}")
    print("  ok")


def test_makeup_amplifies_positive_trust() -> None:
    print("== makeup when tension high ==")
    high = RelationshipState(trust=0.40, dependence=0.30, tension=0.80, day="2026-08-13")
    low = RelationshipState(trust=0.40, dependence=0.30, tension=0.20, day="2026-08-13")
    kwargs = dict(
        alpha=0.3,
        beta=0.0,
        baseline=(0.55, 0.30, 0.25),
        daily_abs_cap=1.0,
        makeup_tension=0.7,
        makeup_trust_scale=1.5,
        now=datetime(2026, 8, 13, 12, 0, 0),
    )
    high.apply_delta((0.10, 0.0, 0.0), **kwargs)
    low.apply_delta((0.10, 0.0, 0.0), **kwargs)
    if high.trust <= low.trust:
        _fail(f"makeup should raise trust more: high={high.trust} low={low.trust}")
    print("  ok")


def test_daily_cap_and_cross_day() -> None:
    print("== daily cap / cross-day ==")
    state = RelationshipState(trust=0.0, dependence=0.0, tension=0.0, day="2026-08-13")
    state.apply_delta(
        (1.0, 0.0, 0.0),
        alpha=1.0,
        beta=0.0,
        baseline=(0.0, 0.0, 0.0),
        daily_abs_cap=0.2,
        now=datetime(2026, 8, 13, 10, 0, 0),
    )
    if abs(state.trust - 0.2) > 1e-9:
        _fail(f"capped trust {state.trust}")
    state.apply_delta(
        (1.0, 0.0, 0.0),
        alpha=1.0,
        beta=0.0,
        baseline=(0.0, 0.0, 0.0),
        daily_abs_cap=0.2,
        now=datetime(2026, 8, 13, 11, 0, 0),
    )
    if abs(state.trust - 0.2) > 1e-9:
        _fail(f"second same-day should stay capped {state.trust}")
    state.apply_delta(
        (1.0, 0.0, 0.0),
        alpha=1.0,
        beta=0.0,
        baseline=(0.0, 0.0, 0.0),
        daily_abs_cap=0.2,
        now=datetime(2026, 8, 14, 10, 0, 0),
    )
    if abs(state.trust - 0.4) > 1e-9:
        _fail(f"next day should apply again {state.trust}")
    print("  ok")


def test_climate_zones() -> None:
    print("== climate zones ==")
    cases = [
        ((0.6, 0.3, 0.3), "secure_play"),
        ((0.5, 0.7, 0.2), "cling_risk"),
        ((0.5, 0.3, 0.7), "rupture"),
        ((0.1, 0.1, 0.1), "cold_tool"),
        ((0.1, 0.3, 0.7), "fragile"),
    ]
    for (a, b, c), expected in cases:
        got = resolve_climate(a, b, c)
        if got != expected:
            _fail(f"{(a, b, c)} expected {expected} got {got}")
    print("  ok")


def test_climate_stickiness() -> None:
    print("== climate stickiness ==")
    state = RelationshipState(trust=0.6, dependence=0.3, tension=0.3)
    first = stick_climate(state, "secure_play", stick_turns=3)
    if first != "secure_play" or state.climate_streak != 1:
        _fail(f"first stick {first} streak={state.climate_streak}")
    kept = stick_climate(state, "steady", stick_turns=3)
    if kept != "secure_play":
        _fail(f"should keep secure_play, got {kept}")
    # urgent overrides
    urgent = stick_climate(state, "cling_risk", stick_turns=3)
    if urgent != "cling_risk":
        _fail(f"urgent should override, got {urgent}")
    print("  ok")


def test_high_b_forbids_cling_stance() -> None:
    print("== high dependence forbids cling ==")
    state = RelationshipState(trust=0.5, dependence=0.85, tension=0.2)
    decision = decide(state, "other", high_dependence=0.7)
    joined = " ".join(decision.must_not)
    if "增加依赖" not in joined and "你还需要我吗" not in joined:
        _fail(f"expected anti-cling must_not: {decision.must_not}")
    if "给空间" not in decision.stance:
        _fail(f"stance should give space: {decision.stance}")
    print("  ok")


def test_classify_and_events() -> None:
    print("== classify / event table ==")
    assert classify_user_act("嗯") == "short_ack"
    assert classify_user_act("好累") == "fatigue"
    assert classify_user_act("你觉得我做得对吗？") == "seek_validation"
    assert classify_user_act("谢谢你还记得") == "gratitude"
    assert classify_user_act("别烦我") == "reject"
    assert classify_user_act("帮我写一段代码") == "instrumental"
    assert classify_user_act("今天天气不错呢") == "other"
    assert classify_user_act(
        "下午好啊，阿洛娜。我有时会想，阿洛娜每天都这么迎接我，会不会感到厌烦呢？"
    ) == "worry_bond"
    assert classify_user_act("那真是太好了，能每天看到阿洛娜，也是我的幸福哦") == "affection"
    assert classify_user_act("和阿洛娜聊天的时候我也很开心") == "affection"
    assert classify_user_act("诶，阿洛娜，抱歉我得离开一会，有事情要干了") == "depart"
    assert classify_user_act("我今天心情很好哦，阿洛娜呢？") == "affection"
    assert classify_user_act("今天我过得很好哦") == "affection"
    assert classify_user_act("抱歉，我得失陪一下，有个任务需要完成") == "depart"
    if USER_DELTAS["seek_validation"][1] <= 0:
        _fail("seek_validation should raise dependence")
    if USER_DELTAS["depart"][1] >= 0:
        _fail("depart should lower dependence")
    print("  ok")


def test_cling_risk_silence() -> None:
    print("== cling_risk + short_ack => silence ==")
    state = RelationshipState(trust=0.5, dependence=0.70, tension=0.15)
    decision = decide(state, "short_ack")
    if decision.climate != "cling_risk":
        _fail(f"expected cling_risk got {decision.climate}")
    if decision.action != "silence":
        _fail(f"expected silence got {decision.action}")
    print("  ok")


def test_seek_validation_raises_b() -> None:
    print("== seek_validation raises B ==")
    settings = RelationshipSettings(beta=0.0)
    state = RelationshipState(trust=0.5, dependence=0.20, tension=0.20, day="2026-08-13")
    before = state.dependence
    state.apply_delta(
        USER_DELTAS["seek_validation"],
        alpha=0.3,
        beta=0.0,
        baseline=settings.baseline,
        daily_abs_cap=1.0,
        now=datetime(2026, 8, 13, 12, 0, 0),
    )
    if state.dependence <= before:
        _fail(f"dependence should rise {before} -> {state.dependence}")
    print("  ok")


def test_planner_block_has_no_numbers() -> None:
    print("== planner block has no A/B/C numbers ==")
    state = RelationshipState(trust=0.61, dependence=0.33, tension=0.28)
    decision = decide(state, "other")
    block = planner_climate_block(decision)
    for token in ("0.61", "0.33", "0.28", "提升 A", "降低 B"):
        if token in block:
            _fail(f"block leaked {token!r}: {block}")
    msg = build_planner_user_message(
        user_text="你好",
        history=[],
        memories=[],
        knowledge=[],
        climate_block=block,
    )
    if "【关系气候】" not in msg:
        _fail("planner user message missing climate")
    if "0.61" in msg:
        _fail("planner user message leaked trust float")
    print("  ok")


def test_store_roundtrip(tmp: Path) -> None:
    print("== JSON persist ==")
    path = tmp / "relationship.json"
    store = RelationshipStore(path)
    state = RelationshipState(trust=0.42, dependence=0.31, tension=0.22)
    store.save(state)
    loaded = store.load()
    if abs(loaded.trust - 0.42) > 1e-9:
        _fail(f"loaded trust {loaded.trust}")
    engine = RelationshipEngine.from_path(path, RelationshipSettings())
    if abs(engine.state.trust - 0.42) > 1e-9:
        _fail("engine did not load persisted state")
    print("  ok")


def test_welcome_climate_notes() -> None:
    print("== welcome climate notes ==")
    slot = resolve_slot(datetime(2026, 8, 13, 7, 0, 0))
    plain = build_welcome_instruction(slot, first_in_slot=True)
    cling = build_welcome_instruction(slot, first_in_slot=True, climate="cling_risk")
    tight = build_welcome_instruction(slot, first_in_slot=True, climate="fragile")
    if "更短" not in cling:
        _fail(f"cling welcome should be shorter: {cling}")
    if "活泼" not in tight:
        _fail(f"fragile welcome should avoid 活泼: {tight}")
    if "更短" in plain:
        _fail("default welcome should not add cling note")
    print("  ok")


def test_welcome_not_teased_and_speak_not_ratchet() -> None:
    print("== welcome greeted / speak not teased ==")
    if map_arona_act("initiate", "secure_play") != "greeted":
        _fail("welcome initiate should be greeted")
    if map_arona_act("initiate", "secure_play", motive_kind="idle") != "checked_in":
        _fail("idle initiate should be checked_in")
    if map_arona_act("initiate", "secure_play", motive_kind="sleep") != "cared":
        _fail("care initiate should be cared")
    if map_arona_act("initiate", "secure_play", motive_kind="goal") != "checked_in":
        _fail("goal initiate should be checked_in")
    if map_arona_act("continue", "secure_play") != "followed_up":
        _fail("continue should be followed_up")
    if ARONA_DELTAS["checked_in"][1] != 0.0 or ARONA_DELTAS["cared"][1] != 0.0:
        _fail("checked_in/cared must not raise dependence")
    if map_arona_act("speak", "secure_play", "other") != "followed_up":
        _fail("normal speak should be followed_up")
    if map_arona_act("speak", "secure_play", "play_tease") != "teased":
        _fail("play_tease speak should be teased")
    if map_arona_act("speak", "secure_play", "depart") != "gave_space":
        _fail("depart speak should be gave_space")
    if ARONA_DELTAS["greeted"][2] != 0.0:
        _fail("greeted should not raise tension")
    if ARONA_DELTAS["followed_up"][2] >= ARONA_DELTAS["teased"][2]:
        _fail("followed_up tension should be smaller than teased")
    print("  ok")


def test_intent_drop_throwback_must_say() -> None:
    print("== must_say vs throwback must_not ==")
    raw = (
        '{"user_emotion":"好奇","topic":"光环","stance":"轻松",'
        '"must_say":["解释光环","用俏皮语气反问老师是否喜欢"],'
        '"must_not":["把问题抛回老师"],"facts_to_use":[],'
        '"tone":"轻松","length":"1-2句","arona_emotion":"smile"}'
    )
    card = parse_and_gate_intent(raw)
    if card is None:
        _fail("card should parse")
    joined = " ".join(card.must_say)
    if "反问" in joined:
        _fail(f"conflicting 反问 should be dropped: {card.must_say}")
    print("  ok")


def test_welcome_forbids_ask() -> None:
    print("== welcome forbids 想聊什么, allows light ask ==")
    slot = resolve_slot(datetime(2026, 8, 13, 15, 0, 0))
    text = build_welcome_instruction(slot, first_in_slot=True)
    if "想聊什么" not in text:
        _fail("welcome instruction should forbid 想聊什么")
    if "轻问" not in text:
        _fail("welcome should allow a light opening question")
    if "【系统事件】" in WELCOME_MEMORY_QUERY:
        _fail("welcome memory query must not be the system event")
    print("  ok")


def test_depart_then_short_ack_silence() -> None:
    print("== depart then 嗯 => silence ==")
    state = RelationshipState(
        trust=0.6, dependence=0.30, tension=0.30, last_user_act="depart"
    )
    decision = decide(state, "short_ack")
    if decision.action != "silence":
        _fail(f"expected silence after depart, got {decision.action}")
    everyday = RelationshipState(
        trust=0.6, dependence=0.30, tension=0.30, last_user_act="other"
    )
    spoken = decide(everyday, "short_ack")
    if spoken.action != "speak":
        _fail(f"everyday 嗯 should still speak, got {spoken.action}")
    print("  ok")


def test_engine_depart_then_ack(tmp: Path) -> None:
    print("== engine persist last_user_act ==")
    path = tmp / "rel.json"
    engine = RelationshipEngine.from_path(path, RelationshipSettings(beta=0.0))
    _act, first = engine.on_user_text("抱歉，我得失陪一下，有个任务需要完成")
    if _act != "depart" or first.user_act != "depart":
        _fail(f"expected depart, got {_act}")
    _ack, second = engine.on_user_text("嗯")
    if _ack != "short_ack" or second.action != "silence":
        _fail(f"expected silence, act={_ack} action={second.action}")
    print("  ok")


def test_config_loads() -> None:
    print("== config ==")
    cfg = load_config()
    rel = cfg.proactive.relationship
    if not rel.enabled:
        _fail("relationship should default enabled")
    if "relationship.json" not in rel.persist_path:
        _fail(f"unexpected persist_path {rel.persist_path}")
    if not cfg.proactive.idle.enabled or not cfg.proactive.care.enabled:
        _fail("idle/care should default enabled")
    print("  ok")


def main() -> None:
    test_apply_delta_formula()
    test_makeup_amplifies_positive_trust()
    test_daily_cap_and_cross_day()
    test_climate_zones()
    test_climate_stickiness()
    test_high_b_forbids_cling_stance()
    test_classify_and_events()
    test_cling_risk_silence()
    test_seek_validation_raises_b()
    test_planner_block_has_no_numbers()
    with tempfile.TemporaryDirectory() as tmp:
        test_store_roundtrip(Path(tmp))
    test_welcome_climate_notes()
    test_welcome_not_teased_and_speak_not_ratchet()
    test_intent_drop_throwback_must_say()
    test_welcome_forbids_ask()
    test_depart_then_short_ack_silence()
    with tempfile.TemporaryDirectory() as tmp:
        test_engine_depart_then_ack(Path(tmp))
    test_config_loads()
    print("ALL PASS")


if __name__ == "__main__":
    main()
