#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DEPRECATED path for weak renderer pairs.

Use build_renderer_synth_v2.py instead. This script refuses to emit虚卡
(must_say=["回应老师本轮意图"]) and redirects output away from chosen/.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

DISABLED_DIR = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "raw"
    / "normal"
    / "disabled"
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force-legacy",
        action="store_true",
        help="Allow writing template pairs to disabled/ (still not chosen/).",
    )
    args = parser.parse_args()
    print(
        "build_renderer_pairs.py is disabled for training.\n"
        "Use: python data-process/build_renderer_synth_v2.py --mode template|llm\n"
        "Weak虚卡 output must not land in raw/normal/chosen/.",
        file=sys.stderr,
    )
    if not args.force_legacy:
        raise SystemExit(2)

    # Late import only for forced legacy dump into disabled/
    from build_renderer_synth_v2 import build_template

    items = build_template(50)
    DISABLED_DIR.mkdir(parents=True, exist_ok=True)
    out = DISABLED_DIR / "renderer_pairs_legacy_dump.json"
    import json

    out.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(items)} -> {out} (not used for training)")


if __name__ == "__main__":
    main()
