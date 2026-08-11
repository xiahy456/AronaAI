"""Merge all JSON files under raw/normal/expand into a single JSONL file."""

from __future__ import annotations

import json
from pathlib import Path

EXPAND_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "normal" / "chosen"
OUTPUT_FILE = Path(__file__).resolve().parent.parent / "data" / "finetune_training" / "normal_finetune.jsonl"


def merge_expand_to_jsonl(
    input_dir: Path = EXPAND_DIR,
    output_file: Path = OUTPUT_FILE,
) -> int:
    if not input_dir.is_dir():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    # Renderer training has its own merge (merge_renderer_finetune.py).
    # Skip weak/disabled synth and renderer-only corpora here.
    skip_names = {
        "renderer_synth.json",
        "renderer_synth_v2.json",
        "renderer_curated.json",
        "renderer_intent.json",
    }

    json_files = sorted(
        p for p in input_dir.glob("*.json") if p.name not in skip_names
    )
    if not json_files:
        raise FileNotFoundError(f"No JSON files found in: {input_dir}")

    total = 0
    with output_file.open("w", encoding="utf-8") as out_f:
        for json_file in json_files:
            with json_file.open("r", encoding="utf-8") as in_f:
                data = json.load(in_f)

            if not isinstance(data, list):
                raise ValueError(f"Root of {json_file.name} must be a JSON array")

            for item in data:
                out_f.write(json.dumps(item, ensure_ascii=False) + "\n")
                total += 1

            print(f"  {json_file.name}: {len(data)} items")

    print(f"Wrote {total} lines -> {output_file}")
    return total


def main() -> None:
    print(f"Merging JSON files from: {EXPAND_DIR}")
    merge_expand_to_jsonl()


if __name__ == "__main__":
    main()
