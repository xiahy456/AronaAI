#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Copy exported GGUF into models/AronaLM-Renderer-V2.2 and print backend switch notes."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
FINETUNE = Path(__file__).resolve().parents[1]
DEFAULT_SRC = FINETUNE / "outputs" / "AronaLM-Renderer-V2.2-gguf"
DEFAULT_DST = REPO / "models" / "AronaLM-Renderer-V2.2"
V21 = REPO / "models" / "AronaLM-Renderer-V2.1"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", type=Path, default=DEFAULT_SRC)
    parser.add_argument("--dst", type=Path, default=DEFAULT_DST)
    args = parser.parse_args()

    src = args.src
    if not src.is_dir():
        raise SystemExit(f"GGUF export dir missing: {src}")

    ggufs = sorted(src.rglob("*.gguf"))
    if not ggufs:
        raise SystemExit(f"No .gguf under {src}")

    pick = ggufs[0]
    for g in ggufs:
        name = g.name.lower()
        if "q4_k_m" in name or "q4_k" in name:
            pick = g
            break

    args.dst.mkdir(parents=True, exist_ok=True)
    dest_file = args.dst / "AronaLM-Renderer-V2.2.Q4_K_M.gguf"
    shutil.copy2(pick, dest_file)
    print(f"Copied {pick} -> {dest_file}")

    rel = "../models/AronaLM-Renderer-V2.2/AronaLM-Renderer-V2.2.Q4_K_M.gguf"
    rollback = "../models/AronaLM-Renderer-V2.1/AronaLM-Renderer-V2.1.Q4_K_M.gguf"
    print()
    print("Deploy: set backend/config.yaml")
    print(f'  model.gguf_path: "{rel}"')
    print()
    print("Rollback:")
    print(f'  model.gguf_path: "{rollback}"')
    if V21.is_dir():
        print(f"  (v2.1 dir present: {V21})")
    else:
        print(f"  WARNING: v2.1 dir missing: {V21}")


if __name__ == "__main__":
    main()
