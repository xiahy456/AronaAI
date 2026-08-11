#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Copy exported GGUF into models/aronalm-v2.1-renderer and print backend switch notes.

Does NOT modify backend/config.yaml (keep rollback manual).
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
FINETUNE = Path(__file__).resolve().parents[1]
DEFAULT_SRC = FINETUNE / "outputs" / "aronalm-v2.1-renderer-gguf"
DEFAULT_DST = REPO / "models" / "aronalm-v2.1-renderer"
V20 = REPO / "models" / "aronalm-v2.0-normal"


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

    # Prefer q4_k_m-ish names
    pick = ggufs[0]
    for g in ggufs:
        name = g.name.lower()
        if "q4_k_m" in name or "q4_k" in name:
            pick = g
            break

    args.dst.mkdir(parents=True, exist_ok=True)
    dest_file = args.dst / "aronalm-v2.1-renderer.Q4_K_M.gguf"
    shutil.copy2(pick, dest_file)
    print(f"Copied {pick} -> {dest_file}")

    rel = "../models/aronalm-v2.1-renderer/aronalm-v2.1-renderer.Q4_K_M.gguf"
    rollback = "../models/aronalm-v2.0-normal/aronalm-v2.0-normal.Q4_K_M.gguf"
    print()
    print("Deploy: set backend/config.yaml")
    print(f'  model.gguf_path: "{rel}"')
    print()
    print("Rollback:")
    print(f'  model.gguf_path: "{rollback}"')
    if V20.is_dir():
        print(f"  (v2.0 dir present: {V20})")
    else:
        print(f"  WARNING: v2.0 dir missing: {V20}")


if __name__ == "__main__":
    main()
