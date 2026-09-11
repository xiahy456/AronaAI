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
