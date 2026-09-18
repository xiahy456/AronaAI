#!/usr/bin/env python3
"""Lock Step 0 taxonomy names and Step 2 extractor schema wiring.

Run from backend/:
  python scripts/test_taxonomy_unit.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.memory.extractor import EXTRACT_SYSTEM  # noqa: E402
from app.relationship.events import USER_DELTAS  # noqa: E402
from app.taxonomy import (  # noqa: E402
    CRISIS_USER_ACT,
    FACT_CATEGORIES,
    FOLLOWUP_BLOCK_USER_ACTS,
    FOLLOWUP_OK_CLIMATES,
    FOLLOWUP_SKIP_REASONS,
    FOLLOWUP_SOURCE_CATEGORIES,
    MEMORY_CATEGORIES,
    MOOD_FOLLOWUP_KIND,
    climate_allows_mood_followup,
    is_followup_source_category,
    normalize_memory_category,
    user_act_blocks_mood_followup,
)


def main() -> None:
    fails: list[str] = []

    if CRISIS_USER_ACT != "crisis":
        fails.append(f"CRISIS_USER_ACT={CRISIS_USER_ACT!r}")
    if MOOD_FOLLOWUP_KIND != "mood_followup":
        fails.append(f"MOOD_FOLLOWUP_KIND={MOOD_FOLLOWUP_KIND!r}")
    if "episodic" not in MEMORY_CATEGORIES:
        fails.append("MEMORY_CATEGORIES missing episodic")
    if "emotional" not in MEMORY_CATEGORIES:
        fails.append("MEMORY_CATEGORIES missing emotional")
    if FOLLOWUP_SOURCE_CATEGORIES != frozenset({"emotional"}):
        fails.append(f"FOLLOWUP_SOURCE_CATEGORIES={FOLLOWUP_SOURCE_CATEGORIES!r}")
    if FACT_CATEGORIES != frozenset({"preference", "profile", "goal", "other"}):
        fails.append(f"FACT_CATEGORIES={FACT_CATEGORIES!r}")
    if FOLLOWUP_OK_CLIMATES != frozenset({"steady", "secure_play"}):
        fails.append(f"FOLLOWUP_OK_CLIMATES={FOLLOWUP_OK_CLIMATES!r}")
    if not {"depart", "reject", "crisis"} <= FOLLOWUP_BLOCK_USER_ACTS:
        fails.append(f"FOLLOWUP_BLOCK_USER_ACTS={FOLLOWUP_BLOCK_USER_ACTS!r}")
    expected_reasons = {
        "crisis",
        "muted",
        "too_new",
        "too_old",
        "climate",
        "blocked_user_act",
    }
    if FOLLOWUP_SKIP_REASONS != expected_reasons:
        fails.append(f"FOLLOWUP_SKIP_REASONS={FOLLOWUP_SKIP_REASONS!r}")

    if normalize_memory_category("emotional") != "emotional":
        fails.append("normalize emotional")
    if normalize_memory_category("EPISODIC") != "episodic":
        fails.append("normalize EPISODIC")
    if normalize_memory_category("unknown") != "other":
        fails.append("normalize unknown")
    if normalize_memory_category(None) != "other":
        fails.append("normalize None")
    if normalize_memory_category(1) != "other":
        fails.append("normalize non-str")

    if not is_followup_source_category("emotional"):
        fails.append("emotional should be followup source")
    if is_followup_source_category("episodic"):
        fails.append("episodic should not be followup source")
    if is_followup_source_category("goal"):
        fails.append("goal should not be followup source")
    if is_followup_source_category("nope"):
        fails.append("unknown category should not be followup source")

    for climate in ("steady", "secure_play"):
        if not climate_allows_mood_followup(climate):
            fails.append(f"climate {climate} should allow followup")
    for climate in ("fragile", "rupture", "cling_risk", "cold_tool", "", None):
        if climate_allows_mood_followup(climate):
            fails.append(f"climate {climate!r} should block followup")

    for act in ("depart", "reject", "crisis", "CRISIS"):
        if not user_act_blocks_mood_followup(act):
            fails.append(f"user_act {act} should block followup")
    if user_act_blocks_mood_followup("self_disclose"):
        fails.append("self_disclose should not block followup")
    if user_act_blocks_mood_followup(None):
        fails.append("None user_act should not block followup")

    if CRISIS_USER_ACT not in USER_DELTAS:
        fails.append("USER_DELTAS must include crisis")
    if USER_DELTAS.get(CRISIS_USER_ACT) != (0.0, 0.0, 0.0):
        fails.append(f"crisis delta={USER_DELTAS.get(CRISIS_USER_ACT)!r}")
    if "episodic" not in EXTRACT_SYSTEM:
        fails.append("EXTRACT_SYSTEM must list episodic")
    if "emotional" not in EXTRACT_SYSTEM:
        fails.append("EXTRACT_SYSTEM must list emotional")

    if fails:
        print("FAIL")
        for item in fails:
            print(f" - {item}")
        raise SystemExit(1)
    print("OK: taxonomy contract cases passed")


if __name__ == "__main__":
    main()
