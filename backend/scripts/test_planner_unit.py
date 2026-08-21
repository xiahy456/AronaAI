"""Quick unit smoke for dual-model pieces (V2.4 draft schema)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import load_config
from app.planner import EMOTION_WHITELIST, normalize_emotion, parse_and_gate_intent, route_mode
from app.planner.prompts import PLANNER_SYSTEM, build_planner_user_message
from app.prompt import build_renderer_messages, clip_inject_chunks
from app.protocol import msg_chat_response
from app.relationship.events import USER_ACT_WHITELIST, USER_ACT_WHITELIST_CSV, USER_DELTAS


def main() -> None:
    assert route_mode("你好") == "local"
    assert route_mode("今天好难受，什么都不想做") == "dual"
    assert normalize_emotion("SMILE") == "smile"
    assert normalize_emotion("nope") == "normal"

    legacy = parse_and_gate_intent(
        '{"user_emotion":"沮丧","topic":"考试","stance":"共情",'
        '"must_say":["安慰"],"must_not":[],"facts_to_use":[],'
        '"tone":"温柔","length":"1-2句","arona_emotion":"smile"}'
    )
    assert legacy is None

    raw = (
        '{"draft":"考试让老师很沮丧，我陪在老师身边。",'
        '"arona_emotion":"smile","followup_ok":false}'
    )
    card = parse_and_gate_intent(raw)
    assert card is not None
    assert card.draft.startswith("考试")
    assert card.arona_emotion == "smile"
    assert card.followup_ok is False
    assert card.reply_ok is True
    assert card.user_act == "other"
    assert card.to_renderer_dict() == {"draft": card.draft}
    assert "arona_emotion" not in card.to_renderer_dict()
    assert "followup_ok" not in card.to_renderer_dict()
    assert "reply_ok" not in card.to_renderer_dict()
    assert "user_act" not in card.to_renderer_dict()

    cfg = load_config()
    hist = [
        {"role": "user", "content": "上一轮老师"},
        {"role": "assistant", "content": "上一轮阿洛娜"},
    ]
    msgs = build_renderer_messages(
        cfg,
        draft=card.to_renderer_draft(),
        history=hist,
        max_history_turns=2,
    )
    assert len(msgs) == 2
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    assert "上一轮老师" not in msgs[1]["content"]
    assert "【意图草稿】" in msgs[-1]["content"]
    assert "【老师原话】" not in msgs[-1]["content"]
    assert "【系统事件】" not in msgs[-1]["content"]
    assert "【回复意图卡】" not in msgs[-1]["content"]
    assert card.draft in msgs[-1]["content"]
    assert "意图草稿" in msgs[0]["content"] or "【意图草稿】" in msgs[-1]["content"]

    follow = parse_and_gate_intent(
        '{"draft":"光环是阿洛娜身份的一部分，我可以慢慢讲给老师听。",'
        '"arona_emotion":"smile","followup_ok":true}'
    )
    assert follow is not None and follow.followup_ok is True
    assert follow.reply_ok is True

    silent = parse_and_gate_intent(
        '{"draft":"","arona_emotion":"smile","followup_ok":true,'
        '"reply_ok":false,"user_act":"depart"}'
    )
    assert silent is not None
    assert silent.reply_ok is False
    assert silent.draft == ""
    assert silent.user_act == "depart"
    assert silent.followup_ok is False
    assert silent.arona_emotion == "normal"

    assert parse_and_gate_intent(
        '{"draft":"","arona_emotion":"normal","followup_ok":false,"reply_ok":true}'
    ) is None

    bad_act = parse_and_gate_intent(
        '{"draft":"好的老师。","arona_emotion":"smile","followup_ok":false,'
        '"reply_ok":true,"user_act":"not_a_real_act"}'
    )
    assert bad_act is not None
    assert bad_act.user_act == "other"

    m = msg_chat_response("ok", emotion="shy")
    assert m["emotion"] == "shy"

    assert "【阿洛娜主要人设】" in PLANNER_SYSTEM
    assert "什亭之匣" in PLANNER_SYSTEM
    assert "温柔活泼" in PLANNER_SYSTEM
    assert "规划参谋" in PLANNER_SYSTEM
    assert '"draft"' in PLANNER_SYSTEM or "draft：" in PLANNER_SYSTEM
    assert "想聊什么" in PLANNER_SYSTEM
    assert "reply_ok" in PLANNER_SYSTEM
    assert "user_act" in PLANNER_SYSTEM
    assert set(USER_ACT_WHITELIST) == set(USER_DELTAS)
    for act in USER_ACT_WHITELIST:
        assert act in PLANNER_SYSTEM
    assert USER_ACT_WHITELIST_CSV
    user_msg = build_planner_user_message(
        user_text="谢谢你，阿洛娜。",
        history=[],
        memories=[],
        knowledge=[],
    )
    assert "【老师本轮消息】" in user_msg
    assert "【阿洛娜主要人设】" not in user_msg
    assert "must_say" not in user_msg
    assert "先判断 reply_ok" in user_msg

    long_a = "设定甲" * 10
    long_b = "设定乙" * 10
    first_line = f"- {long_a}"
    clipped = clip_inject_chunks([long_a, long_b], len(first_line) + 5)
    assert clipped == [long_a]
    clipped_msg = build_planner_user_message(
        user_text="光环是什么颜色？",
        history=[],
        memories=[],
        knowledge=clipped,
    )
    assert "设定甲" in clipped_msg
    assert "设定乙" not in clipped_msg

    _ = EMOTION_WHITELIST
    print("ok")


if __name__ == "__main__":
    main()
