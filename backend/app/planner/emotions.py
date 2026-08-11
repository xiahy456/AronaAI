"""Arona Spine expression whitelist (English values only)."""

from __future__ import annotations

DEFAULT_EMOTION = "normal"

# Keep in sync with frontend AronaSpineAssets/README.md (英文值 column).
EMOTION_WHITELIST: frozenset[str] = frozenset(
    {
        "normal",
        "curious",
        "smile",
        "worried",
        "angry",
        "angry_shame",
        "disgusted",
        "disgusted_surprised",
        "disgusted_worried",
        "frustration",
        "like",
        "very_happy",
        "enjoy",
        "complaint",
        "unwilling",
        "shy",
        "shout",
        "want",
        "confident_serious",
        "sleep_very_content",
        "sleep_question",
        "confident",
        "disappointed",
        "disappointed_disgusted",
        "very_surprised",
        "dizzy",
        "surprise",
        "surprise_very_happy",
        "sleep",
    }
)

EMOTION_WHITELIST_CSV = ", ".join(sorted(EMOTION_WHITELIST))


def normalize_emotion(value: object | None) -> str:
    """Return a whitelist emotion; unknown/missing -> normal."""
    if not isinstance(value, str):
        return DEFAULT_EMOTION
    key = value.strip().lower()
    if key in EMOTION_WHITELIST:
        return key
    return DEFAULT_EMOTION
