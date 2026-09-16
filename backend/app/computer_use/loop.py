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

"""Send hardcoded probe actions and wait for matching observations."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from ..protocol import msg_chat_response, msg_computer_use_done
from .probe import (
    PROBE_CANCELLED_REPLY,
    PROBE_DONE_REPLY,
    PROBE_FAILED_REPLY,
    probe_actions,
)
from .schema import ComputerUseAction, ComputerUseObservation

logger = logging.getLogger(__name__)

SendFn = Callable[[dict[str, Any]], Awaitable[None]]
WaitObservation = Callable[[str, int], Awaitable[ComputerUseObservation | None]]
AbortCheck = Callable[[], bool]


@dataclass
class ProbeResult:
    ok: bool
    summary: str
    run_id: str
    steps_completed: int
    reason: str


async def run_probe(
    *,
    send: SendFn,
    wait_observation: WaitObservation,
    abort_check: AbortCheck | None = None,
    actions: list[ComputerUseAction] | None = None,
    max_steps: int = 8,
    run_id: str | None = None,
) -> ProbeResult:
    """Drive one probe run. Caller sends computer_use_done + chat_response."""
    rid = (run_id or "").strip() or str(uuid.uuid4())
    steps = list(actions if actions is not None else probe_actions())
    if max_steps < 1:
        return ProbeResult(
            ok=False,
            summary="max_steps",
            run_id=rid,
            steps_completed=0,
            reason="max_steps",
        )
    completed = 0
    for index, action in enumerate(steps, start=1):
        if abort_check is not None and abort_check():
            return ProbeResult(
                ok=False,
                summary="cancelled",
                run_id=rid,
                steps_completed=completed,
                reason="cancelled",
            )
        if index > max_steps:
            return ProbeResult(
                ok=False,
                summary="max_steps",
                run_id=rid,
                steps_completed=completed,
                reason="max_steps",
            )
        action.run_id = rid
        action.step = index
        logger.info(
            "computer_use action run_id=%s step=%s action=%s",
            rid,
            index,
            action.action,
        )
        await send(action.to_message())
        observation = await wait_observation(rid, index)
        if observation is None:
            logger.info("computer_use timeout run_id=%s step=%s", rid, index)
            return ProbeResult(
                ok=False,
                summary="timeout",
                run_id=rid,
                steps_completed=completed,
                reason="timeout",
            )
        if observation.run_id != rid or observation.step != index:
            logger.info(
                "computer_use observation mismatch run_id=%s step=%s got=%s/%s",
                rid,
                index,
                observation.run_id,
                observation.step,
            )
            return ProbeResult(
                ok=False,
                summary="observation_mismatch",
                run_id=rid,
                steps_completed=completed,
                reason="observation_failed",
            )
        if not observation.ok:
            logger.info(
                "computer_use observation failed run_id=%s step=%s error=%s",
                rid,
                index,
                observation.error,
            )
            return ProbeResult(
                ok=False,
                summary=observation.error or "observation_failed",
                run_id=rid,
                steps_completed=completed,
                reason="observation_failed",
            )
        completed = index
        if observation.screen is not None:
            logger.info(
                "computer_use observation ok run_id=%s step=%s "
                "origin=%s,%s phys=%sx%s img=%sx%s dpi=%s cursor=%s,%s",
                rid,
                index,
                observation.screen.origin_x,
                observation.screen.origin_y,
                observation.screen.phys_w,
                observation.screen.phys_h,
                observation.screen.img_w,
                observation.screen.img_h,
                observation.screen.dpi_scale,
                observation.screen.cursor_x,
                observation.screen.cursor_y,
            )
    return ProbeResult(
        ok=True,
        summary="probe complete",
        run_id=rid,
        steps_completed=completed,
        reason="complete",
    )


def probe_reply_text(result: ProbeResult) -> str:
    if result.ok:
        return PROBE_DONE_REPLY
    if result.reason == "cancelled":
        return PROBE_CANCELLED_REPLY
    return PROBE_FAILED_REPLY


def terminal_messages(result: ProbeResult) -> list[dict[str, Any]]:
    return [
        msg_computer_use_done(result.run_id, ok=result.ok, summary=result.summary),
        msg_chat_response(
            probe_reply_text(result),
            context_used="computer_use",
        ),
    ]
