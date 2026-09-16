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

"""Run CU routing in parallel with chat; wait for the router first."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)

SendFn = Callable[[dict[str, Any]], Awaitable[None]]
ChatFn = Callable[[SendFn], Awaitable[None]]
RouteFn = Callable[[], Awaitable[bool]]
CuFn = Callable[[], Awaitable[None]]


class RouteGate:
    """Hold the router decision until chat is allowed to send."""

    def __init__(self) -> None:
        self.operate: bool | None = None
        self.event = asyncio.Event()

    def set(self, operate: bool) -> None:
        self.operate = bool(operate)
        self.event.set()


async def gated_send(
    gate: RouteGate,
    send: SendFn,
    payload: dict[str, Any],
) -> None:
    """Block chat payloads until the router says false; drop them if true."""
    if gate.operate is None:
        await gate.event.wait()
    if gate.operate:
        raise asyncio.CancelledError()
    await send(payload)


async def _cancel_task(task: asyncio.Task[Any]) -> None:
    if task.done():
        try:
            task.result()
        except (asyncio.CancelledError, Exception):
            return
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        return
    except Exception:
        logger.exception("computer_use parallel child failed after cancel")


async def race_route_and_chat(
    *,
    route: RouteFn,
    run_chat: ChatFn,
    run_cu: CuFn,
    send: SendFn,
) -> bool:
    """Run router and chat together. Returns True if computer-use ran.

    Waits for the router first. True cancels chat (no draft). False unblocks
    send and waits for chat. Router errors are treated as false.
    """
    gate = RouteGate()

    async def wrapped_send(payload: dict[str, Any]) -> None:
        await gated_send(gate, send, payload)

    route_task = asyncio.create_task(route(), name="cu-route")
    chat_task = asyncio.create_task(run_chat(wrapped_send), name="cu-chat")
    operate = False
    try:
        try:
            operate = bool(await route_task)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("computer_use parallel route failed")
            operate = False
        gate.set(operate)
        if operate:
            logger.info("computer_use parallel route=true discard planner")
            await _cancel_task(chat_task)
            await run_cu()
            return True
        await chat_task
        return False
    except asyncio.CancelledError:
        await _cancel_task(route_task)
        await _cancel_task(chat_task)
        raise
