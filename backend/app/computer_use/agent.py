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

"""Vision-driven computer-use agent: one whitelist action per step."""

from __future__ import annotations

from .client import VisionClient
from .loop import (
    AbortCheck,
    ProbeResult,
    SendFn,
    WaitObservation,
    run_action_loop,
)
from .schema import ComputerUseAction, ComputerUseObservation

_NO_FRAME_SUMMARY = "没有收到屏幕画面，先不操作了。"


async def run_vision_agent(
    *,
    send: SendFn,
    wait_observation: WaitObservation,
    client: VisionClient,
    user_text: str,
    abort_check: AbortCheck | None = None,
    max_steps: int = 5,
    run_id: str | None = None,
) -> ProbeResult:
    async def next_action(
        step: int,
        last_obs: ComputerUseObservation | None,
        executed: list[ComputerUseAction],
    ) -> ComputerUseAction | None:
        del step
        if last_obs is None or last_obs.image is None:
            if not executed:
                return ComputerUseAction(action="wait", ms=0)
            return ComputerUseAction(action="done", summary=_NO_FRAME_SUMMARY)
        return await client.plan(
            user_text=user_text,
            executed=executed,
            observation=last_obs,
        )

    return await run_action_loop(
        send=send,
        wait_observation=wait_observation,
        next_action=next_action,
        abort_check=abort_check,
        max_steps=max_steps,
        run_id=run_id,
    )
