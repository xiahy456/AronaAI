"""Synthesize renderer (intent-card -> reply) pairs from existing chosen dialogues.

Writes ShareGPT JSON under raw/normal/chosen/renderer_synth.json so merge_expand_to_jsonl
picks it up. Emotion is never included in the card text.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

CHOSEN_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "normal" / "chosen"
OUTPUT_FILE = CHOSEN_DIR / "renderer_synth.json"
SKIP_NAMES = frozenset({"renderer_intent.json", "renderer_synth.json"})


def _infer_card(user_text: str, reply: str) -> dict:
    topic = user_text.strip()[:24] or "日常闲聊"
    return {
        "user_emotion": "平常",
        "topic": topic,
        "stance": "按阿洛娜口吻自然回应",
        "must_say": ["回应老师本轮意图"],
        "must_not": ["说教", "自称其他AI", "长篇列表", "复述意图卡"],
        "facts_to_use": [],
        "tone": "温柔活泼短句",
        "length": "1-3句",
    }


def _format_human(user_text: str, card: dict) -> str:
    card_text = json.dumps(card, ensure_ascii=False)
    return (
        f"【回复意图卡】\n{card_text}\n\n"
        f"【老师原话】\n{user_text.strip()}\n\n"
        "请用阿洛娜的口吻回复老师。"
    )


def convert_item(item: dict) -> dict | None:
    conv = item.get("conversations")
    if not isinstance(conv, list) or len(conv) < 2:
        return None
    # Use last human/gpt pair for multi-turn samples.
    human = None
    gpt = None
    for turn in conv:
        if not isinstance(turn, dict):
            continue
        if turn.get("from") == "human":
            human = str(turn.get("value") or "")
        elif turn.get("from") == "gpt":
            gpt = str(turn.get("value") or "")
    if not human or not gpt:
        return None
    # Skip already-rendered intent samples.
    if "【回复意图卡】" in human:
        return None
    card = _infer_card(human, gpt)
    return {
        "conversations": [
            {"from": "human", "value": _format_human(human, card)},
            {"from": "gpt", "value": gpt.strip()},
        ]
    }


def build(chosen_dir: Path = CHOSEN_DIR, output: Path = OUTPUT_FILE) -> int:
    items: list[dict] = []
    for path in sorted(chosen_dir.glob("*.json")):
        if path.name in SKIP_NAMES:
            continue
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            continue
        for item in data:
            if isinstance(item, dict):
                converted = convert_item(item)
                if converted:
                    items.append(converted)
        print(f"  scanned {path.name}")

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(items)} renderer pairs -> {output}")
    return len(items)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chosen-dir", type=Path, default=CHOSEN_DIR)
    parser.add_argument("--output", type=Path, default=OUTPUT_FILE)
    args = parser.parse_args()
    build(args.chosen_dir, args.output)


if __name__ == "__main__":
    main()
