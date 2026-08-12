#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Merge renderer training JSONL (+ optional persona mix).

Outputs:
  - data/finetune_training/renderer_finetune.jsonl   (renderer only)
  - data/finetune_training/mixed_renderer_finetune.jsonl  (renderer + persona cap)
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

FINETUNE_ROOT = Path(__file__).resolve().parent.parent
CHOSEN_DIR = FINETUNE_ROOT / "data" / "raw" / "normal" / "chosen"
OUT_DIR = FINETUNE_ROOT / "data" / "finetune_training"

RENDERER_FILES = (
    "renderer_curated.json",
    "renderer_synth_v2.json",
    # legacy boutique file if still present (prefer merged into curated)
    "renderer_intent.json",
)

# Weak / superseded — never merge
BLOCKLIST = frozenset(
    {
        "renderer_synth.json",
    }
)

PERSONA_FILES = (
    "assistant.json",
    "care.json",
    "emotion.json",
    "interest.json",
    "mixture.json",
    "multiple.json",
    "routine.json",
    "self.json",
)

_SENT_SPLIT = re.compile(r"(?<=[。！？!?~～])\s*")


def _compress_gpt_reply(text: str, max_sents: int = 2) -> str:
    t = (text or "").strip()
    if not t:
        return t
    parts = [p.strip() for p in _SENT_SPLIT.split(t) if p.strip()]
    if len(parts) <= max_sents:
        return t
    return "".join(parts[:max_sents])


def _shorten_persona_item(item: dict) -> dict:
    """Keep persona voice but clip assistant turns to <=2 sentences."""
    conv = item.get("conversations")
    if not isinstance(conv, list):
        return item
    new_conv = []
    changed = False
    for turn in conv:
        if not isinstance(turn, dict):
            new_conv.append(turn)
            continue
        if turn.get("from") == "gpt":
            old = str(turn.get("value") or "")
            new = _compress_gpt_reply(old)
            if new != old:
                changed = True
            new_conv.append({**turn, "value": new})
        else:
            new_conv.append(turn)
    if not changed:
        return item
    return {**item, "conversations": new_conv}


def _load_list(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path.name}: root must be array")
    return [x for x in data if isinstance(x, dict) and "conversations" in x]


def _write_jsonl(path: Path, items: list[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    return len(items)


def merge(
    *,
    persona_max: int = 150,
    seed: int = 3407,
    include_intent: bool = True,
) -> tuple[int, int]:
    renderer_items: list[dict] = []
    for name in RENDERER_FILES:
        if name == "renderer_intent.json" and not include_intent:
            continue
        if name in BLOCKLIST:
            continue
        path = CHOSEN_DIR / name
        items = _load_list(path)
        if items:
            print(f"  renderer {name}: {len(items)}")
            renderer_items.extend(items)

    # Dedup by serialized conversations
    seen: set[str] = set()
    deduped: list[dict] = []
    for item in renderer_items:
        key = json.dumps(item.get("conversations"), ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    renderer_items = deduped

    renderer_path = OUT_DIR / "renderer_finetune.jsonl"
    n_r = _write_jsonl(renderer_path, renderer_items)
    print(f"Wrote {n_r} -> {renderer_path}")

    persona_pool: list[dict] = []
    for name in PERSONA_FILES:
        path = CHOSEN_DIR / name
        items = _load_list(path)
        if items:
            print(f"  persona {name}: {len(items)}")
            persona_pool.extend(items)

    rng = random.Random(seed)
    rng.shuffle(persona_pool)
    persona_pick = persona_pool[: max(0, persona_max)]

    # Target persona ~30-40% of mixed: if renderer is R, persona ~= 0.35/(0.65)*R
    # but plan also says cap e.g. 150 — use min(cap, ratio-based)
    if renderer_items:
        ratio_cap = int(len(renderer_items) * 0.4 / 0.6)
        persona_pick = persona_pool[: min(len(persona_pool), min(persona_max, max(ratio_cap, 1)))]
    else:
        persona_pick = persona_pool[: max(0, persona_max)]

    persona_pick = [_shorten_persona_item(x) for x in persona_pick]

    mixed = list(renderer_items) + list(persona_pick)
    rng.shuffle(mixed)
    mixed_path = OUT_DIR / "mixed_renderer_finetune.jsonl"
    n_m = _write_jsonl(mixed_path, mixed)
    print(
        f"Wrote {n_m} -> {mixed_path} "
        f"(renderer={len(renderer_items)}, persona={len(persona_pick)})"
    )
    return n_r, n_m


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--persona-max", type=int, default=150)
    parser.add_argument("--seed", type=int, default=3407)
    parser.add_argument(
        "--no-intent",
        action="store_true",
        help="Skip renderer_intent.json (already folded into curated)",
    )
    args = parser.parse_args()
    print(f"Merging from {CHOSEN_DIR}")
    merge(
        persona_max=args.persona_max,
        seed=args.seed,
        include_intent=not args.no_intent,
    )


if __name__ == "__main__":
    main()
