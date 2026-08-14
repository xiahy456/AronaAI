"""Quick unit smoke for dual-model pieces."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.cache import ResponseCache
from app.config import load_config
from app.planner import EMOTION_WHITELIST, normalize_emotion, parse_and_gate_intent, route_mode
from app.prompt import build_renderer_messages
from app.protocol import msg_chat_response


def main() -> None:
    assert route_mode("你好") == "local"
    assert route_mode("今天好难受，什么都不想做") == "dual"
    assert normalize_emotion("SMILE") == "smile"
    assert normalize_emotion("nope") == "normal"

    raw = (
        '{"user_emotion":"沮丧","topic":"考试","stance":"共情",'
        '"must_say":["安慰"],"must_not":[],"facts_to_use":[],'
        '"tone":"温柔","length":"1-2句","arona_emotion":"smile"}'
    )
    card = parse_and_gate_intent(raw)
    assert card is not None
    assert card.arona_emotion == "smile"
    assert card.followup_ok is False
    assert "arona_emotion" not in card.to_renderer_dict()
    assert "followup_ok" not in card.to_renderer_dict()

    cfg = load_config()
    hist = [
        {"role": "user", "content": "上一轮老师"},
        {"role": "assistant", "content": "上一轮阿洛娜"},
    ]
    msgs = build_renderer_messages(
        cfg,
        user_text="嗨",
        intent_card=card.to_renderer_dict(),
        history=hist,
        max_history_turns=2,
    )
    assert len(msgs) == 2
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    assert "上一轮老师" not in msgs[1]["content"]
    assert "【回复意图卡】" in msgs[-1]["content"]
    assert '"arona_emotion"' not in msgs[-1]["content"]
    assert "落实 must_say" in msgs[-1]["content"]

    conflict = parse_and_gate_intent(
        '{"user_emotion":"感激","topic":"道谢","stance":"轻松",'
        '"must_say":["回应老师的感谢，表示随时愿意陪伴","可自然询问老师接下来想做什么或想聊什么"],'
        '"must_not":["用提问收尾","把问题抛回老师","反问老师想聊什么"],'
        '"facts_to_use":[],"tone":"轻松","length":"1-2句","arona_emotion":"smile"}'
    )
    assert conflict is not None
    assert any("询问" in x for x in conflict.must_say)
    assert any("想聊什么" in x for x in conflict.must_say)
    assert not any("用提问收尾" in x for x in conflict.must_not)

    m = msg_chat_response("ok", emotion="shy")
    assert m["emotion"] == "shy"

    c = ResponseCache(8)
    c.put("a", "b", "curious")
    assert c.get("a") == ("b", "curious")

    print("unit ok", len(EMOTION_WHITELIST), "emotions")


if __name__ == "__main__":
    main()
