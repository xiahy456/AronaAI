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

"""Vision model client: one whitelist action per screenshot."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ..config import ComputerUseConfig, PlannerConfig
from ..image_input import redact_image_fields
from ..logging_utils import format_llm_exchange
from .prompts import (
    VISION_SYSTEM,
    build_vision_user_message,
    cursor_to_image_xy,
    is_repeat_pointer,
)
from .schema import ComputerUseAction, ComputerUseObservation, SchemaError, parse_vision_action

logger = logging.getLogger(__name__)


class VisionClient:
    def __init__(self, planner: PlannerConfig, computer_use: ComputerUseConfig) -> None:
        self.planner = planner
        self.computer_use = computer_use

    @property
    def enabled(self) -> bool:
        key = (self.planner.api_key or "").strip()
        return bool(
            self.planner.enabled
            and key
            and key != "YOUR_DEEPSEEK_API_KEY"
        )

    async def plan(
        self,
        *,
        user_text: str,
        executed: list[ComputerUseAction],
        observation: ComputerUseObservation,
    ) -> ComputerUseAction | None:
        if not self.enabled:
            logger.info("computer_use vision skipped reason=disabled_or_no_key")
            return None
        if observation.image is None:
            logger.info("computer_use vision skipped reason=no_image")
            return None

        timeout = float(
            self.computer_use.vision_timeout_sec or self.planner.timeout_sec or 20
        )
        screen = observation.screen
        img_w = screen.img_w if screen is not None else None
        img_h = screen.img_h if screen is not None else None
        cursor_image = None
        if screen is not None:
            cursor_image = cursor_to_image_xy(
                cursor_x=screen.cursor_x,
                cursor_y=screen.cursor_y,
                phys_w=screen.phys_w,
                phys_h=screen.phys_h,
                img_w=screen.img_w,
                img_h=screen.img_h,
            )
        repeat_pointer = is_repeat_pointer(
            executed,
            cursor_image,
            img_w=img_w,
            img_h=img_h,
        )
        user_payload = build_vision_user_message(
            user_text=user_text,
            executed=executed,
            img_w=img_w,
            img_h=img_h,
            cursor_img_x=cursor_image[0] if cursor_image is not None else None,
            cursor_img_y=cursor_image[1] if cursor_image is not None else None,
            repeat_pointer=repeat_pointer,
        )
        model = (self.planner.vision_model or "").strip() or self.planner.model
        url = self.planner.base_url.rstrip("/") + "/chat/completions"
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": VISION_SYSTEM},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_payload},
                        {
                            "type": "image_url",
                            "image_url": {"url": observation.image.data_url()},
                        },
                    ],
                },
            ],
            "temperature": 0.0,
            "max_tokens": max(1, int(self.computer_use.vision_max_tokens or 2048)),
            "response_format": {"type": "json_object"},
            "thinking": {
                "type": "enabled" if self.computer_use.vision_thinking else "disabled"
            },
        }
        headers = {
            "Authorization": f"Bearer {self.planner.api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
            message = data["choices"][0]["message"] or {}
            content = message.get("content") or ""
            reasoning = message.get("reasoning_content") or ""
            logger.info(
                "%s",
                format_llm_exchange(
                    title="computer_use vision",
                    prompt=redact_image_fields(payload["messages"]),
                    response=content,
                    reasoning=reasoning if str(reasoning).strip() else None,
                ),
            )
            if not str(content).strip():
                logger.warning("computer_use vision empty final content")
                return None
            return parse_vision_action(content)
        except SchemaError as exc:
            logger.warning("computer_use vision parse failed: %s", exc)
            return None
        except Exception as exc:
            logger.warning("computer_use vision call failed: %s", exc)
            return None
