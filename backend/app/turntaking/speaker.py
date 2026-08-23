"""Speaker tags on transcript messages. Phase 1 always sends teacher."""

from __future__ import annotations

SPEAKER_TEACHER = "teacher"
SPEAKER_OTHER = "other"
SPEAKER_UNKNOWN = "unknown"

_USER_SPEAKERS = frozenset({SPEAKER_TEACHER})


def normalize_speaker(value: object | None) -> str:
    text = str(value or "").strip().lower()
    if text == SPEAKER_OTHER:
        return SPEAKER_OTHER
    if text == SPEAKER_UNKNOWN:
        return SPEAKER_UNKNOWN
    return SPEAKER_TEACHER


def is_teacher_speaker(value: object | None) -> bool:
    """Only teacher-tagged speech may enter the user history path."""
    return normalize_speaker(value) in _USER_SPEAKERS
