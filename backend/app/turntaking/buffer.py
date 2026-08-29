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

"""Rolling transcript buffer for a listen session."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .speaker import is_teacher_speaker, normalize_speaker


@dataclass
class TranscriptSegment:
    segment_id: str
    text: str
    speaker: str
    silence_ms: int
    received_at: float = field(default_factory=time.time)


class TurnBuffer:
    def __init__(self) -> None:
        self.listening: bool = False
        self.last_arona_at: float = 0.0
        self._segments: list[TranscriptSegment] = []

    def set_listening(self, on: bool) -> None:
        self.listening = bool(on)
        if on:
            self._segments.clear()

    def note_arona_spoke(self, when: float | None = None) -> None:
        self.last_arona_at = float(when if when is not None else time.time())

    def seconds_since_arona(self, now: float | None = None) -> float | None:
        if self.last_arona_at <= 0:
            return None
        stamp = float(now if now is not None else time.time())
        return max(0.0, stamp - self.last_arona_at)

    def push(
        self,
        *,
        text: str,
        speaker: object = "teacher",
        segment_id: str = "",
        silence_ms: int = 0,
    ) -> TranscriptSegment | None:
        cleaned = (text or "").strip()
        if not cleaned:
            return None
        tag = normalize_speaker(speaker)
        if not is_teacher_speaker(tag):
            return None
        segment = TranscriptSegment(
            segment_id=str(segment_id or ""),
            text=cleaned,
            speaker=tag,
            silence_ms=max(0, int(silence_ms or 0)),
        )
        self._segments.append(segment)
        return segment

    def prepend(self, text: str) -> None:
        cleaned = (text or "").strip()
        if not cleaned:
            return
        self._segments.insert(
            0,
            TranscriptSegment(segment_id="", text=cleaned, speaker="teacher", silence_ms=0),
        )

    def joined(self) -> str:
        return "".join(item.text for item in self._segments).strip()

    def last_text(self) -> str:
        if not self._segments:
            return ""
        return self._segments[-1].text

    def drain(self) -> str:
        text = self.joined()
        self._segments.clear()
        return text

    def clear(self) -> None:
        self._segments.clear()

    def __len__(self) -> int:
        return len(self._segments)
