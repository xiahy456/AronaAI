"""Climate zones and action/stance policy. No numeric A/B/C in outputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .events import AronaAct, UserAct
from .state import RelationshipState

Climate = Literal[
    "secure_play",
    "cling_risk",
    "rupture",
    "cold_tool",
    "fragile",
    "steady",
]

Action = Literal["speak", "continue", "initiate", "refuse", "silence"]
ProactiveKind = Literal["idle", "lunch", "sleep"]

_IDLE_OK_CLIMATES: frozenset[str] = frozenset({"secure_play", "steady"})

URGENT_CLIMATES: frozenset[str] = frozenset({"fragile", "rupture", "cling_risk"})

CLIMATE_LABELS: dict[str, str] = {
    "secure_play": "安心可玩",
    "cling_risk": "依赖偏高，需要空间",
    "rupture": "张力偏高，需要先稳住",
    "cold_tool": "偏工具化，先可靠办事",
    "fragile": "信任不足且紧绷，只稳住",
    "steady": "平稳相处",
}


@dataclass(frozen=True)
class Decision:
    action: Action
    climate: Climate
    stance: str
    must_not: list[str] = field(default_factory=list)
    tone_hint: str = ""
    user_act: UserAct = "other"


def resolve_climate(
    trust: float,
    dependence: float,
    tension: float,
    *,
    cling_dependence: float = 0.55,
) -> Climate:
    if trust < 0.2 and tension > 0.5:
        return "fragile"
    if tension > 0.55 and trust >= 0.2:
        return "rupture"
    if dependence > cling_dependence and tension < 0.35:
        return "cling_risk"
    if trust < 0.25 and dependence < 0.25 and tension < 0.25:
        return "cold_tool"
    if trust >= 0.4 and 0.15 <= dependence <= 0.55 and 0.15 <= tension <= 0.55:
        return "secure_play"
    return "steady"


def stick_climate(
    state: RelationshipState,
    raw: Climate,
    *,
    stick_turns: int = 3,
) -> Climate:
    """Keep the same climate for a few turns unless an urgent zone appears."""
    last = state.last_climate or "steady"
    if raw in URGENT_CLIMATES:
        chosen = raw
    elif (
        last
        and last != raw
        and state.climate_streak < max(1, stick_turns)
        and last not in URGENT_CLIMATES
    ):
        chosen = last  # type: ignore[assignment]
    else:
        chosen = raw

    if chosen == last:
        state.climate_streak = state.climate_streak + 1
    else:
        state.climate_streak = 1
    state.last_climate = chosen
    return chosen  # type: ignore[return-value]


_POLICY: dict[Climate, tuple[str, list[str], str]] = {
    "secure_play": (
        "可以轻松一点，允许轻玩笑或轻轻顶一句，仍要接住老师本轮内容",
        ["说教", "把问题抛回老师", "用提问收尾", "反问老师想聊什么"],
        "轻松自然",
    ),
    "cling_risk": (
        "给空间，少提问，回复更短，不要索取确认",
        [
            "询问老师还需要阿洛娜吗",
            "你还需要我吗",
            "追问老师在做什么",
            "撒娇绑定",
        ],
        "短而轻",
    ),
    "rupture": (
        "先认老师的情绪，不讲理、不抬杠、不纠正对错",
        ["讲理争赢", "开玩笑化解", "说教"],
        "放软、认真",
    ),
    "cold_tool": (
        "先把老师要办的事办可靠，不要硬套亲密或撒娇",
        ["强行亲密", "突然撒娇", "追问心情"],
        "清楚、克制",
    ),
    "fragile": (
        "只稳住，不玩笑、不对立、不翻旧账",
        ["玩笑", "顶嘴", "对立", "翻旧账"],
        "轻、稳",
    ),
    "steady": (
        "平稳陪伴，接住本轮，不要额外加戏",
        ["再次问候", "把问题抛回老师"],
        "温柔短句",
    ),
}


def decide(
    state: RelationshipState,
    user_act: UserAct,
    *,
    cling_dependence: float = 0.55,
    high_dependence: float = 0.7,
    stick_turns: int = 3,
) -> Decision:
    raw = resolve_climate(
        state.trust,
        state.dependence,
        state.tension,
        cling_dependence=cling_dependence,
    )
    climate = stick_climate(state, raw, stick_turns=stick_turns)
    stance, must_not, tone = _POLICY[climate]
    must_not = list(must_not)
    if state.dependence > high_dependence:
        must_not.extend(["增加依赖", "追问还在不在"])
        if "给空间" not in stance:
            stance = "给空间，" + stance

    action: Action = "speak"
    prev_act = state.last_user_act
    if climate == "cling_risk" and user_act in {"short_ack", "fatigue"}:
        action = "silence"
    elif user_act == "short_ack" and prev_act == "depart":
        action = "silence"

    return Decision(
        action=action,
        climate=climate,
        stance=stance,
        must_not=must_not,
        tone_hint=tone,
        user_act=user_act,
    )


def decide_proactive(
    state: RelationshipState,
    kind: ProactiveKind | str,
    *,
    cling_dependence: float = 0.55,
    high_dependence: float = 0.7,
) -> Decision:
    """Gate an idle/care motive. Does not mutate climate stickiness."""
    climate = resolve_climate(
        state.trust,
        state.dependence,
        state.tension,
        cling_dependence=cling_dependence,
    )
    if kind == "idle":
        action: Action = "initiate" if climate in _IDLE_OK_CLIMATES else "silence"
        stance = "轻在场，不追问老师还在不在"
        must_not = ["还在吗", "需不需要我", "编造未发生的事", "把问题抛回老师"]
        tone = "轻、短"
    else:
        action = "initiate"
        if climate == "cling_risk":
            stance = "更短地提醒，不要索取确认"
            must_not = ["还需要我吗", "追问老师在做什么", "撒娇绑定"]
            tone = "短而轻"
        elif climate in {"fragile", "rupture"}:
            stance = "放轻提醒，不要活泼催促"
            must_not = ["开玩笑", "活泼催促", "说教"]
            tone = "轻、稳"
        else:
            stance = "简短提醒吃饭或休息，不要催"
            must_not = ["催促", "说教", "把问题抛回老师"]
            tone = "温柔短句"

    if state.dependence > high_dependence:
        must_not = list(must_not)
        must_not.extend(["增加依赖", "追问还在不在"])

    return Decision(
        action=action,
        climate=climate,
        stance=stance,
        must_not=must_not,
        tone_hint=tone,
    )


def planner_climate_block(decision: Decision) -> str:
    """Text for Planner only — climate label and stance, never A/B/C numbers."""
    label = CLIMATE_LABELS.get(decision.climate, decision.climate)
    bans = "；".join(decision.must_not) if decision.must_not else "（无额外禁区）"
    return (
        f"【关系气候】{label}\n"
        f"【建议姿态】{decision.stance}\n"
        f"【语气】{decision.tone_hint}\n"
        f"【本轮禁区】{bans}\n"
        "不要提及关系数值、信任度、依赖度或张力；不要写「提升/降低某维度」。"
    )


def local_system_hint(decision: Decision) -> str:
    label = CLIMATE_LABELS.get(decision.climate, decision.climate)
    bans = "、".join(decision.must_not[:4])
    return (
        f"【相处姿态】当前气候：{label}。{decision.stance}。"
        f"语气：{decision.tone_hint}。禁止：{bans}。"
    )


def map_arona_act(
    action: Action,
    climate: Climate,
    user_act: UserAct = "other",
    motive_kind: str | None = None,
) -> AronaAct | None:
    if action in {"silence", "refuse"}:
        return "gave_space"
    if action == "initiate":
        if motive_kind == "idle":
            return "checked_in"
        if motive_kind in {"lunch", "sleep", "care"}:
            return "cared"
        return "greeted"
    if action not in {"speak", "continue"}:
        return None
    if climate in {"cling_risk", "fragile"}:
        return "gave_space"
    if user_act == "depart":
        return "gave_space"
    if user_act == "play_tease":
        return "teased"
    return "followed_up"
