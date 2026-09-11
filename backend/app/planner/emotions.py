# Copyright 2026 xia_hy456. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
