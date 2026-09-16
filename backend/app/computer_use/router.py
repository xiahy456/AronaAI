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

"""Conservative text router: default do not operate the teacher's PC."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ..config import ComputerUseConfig, PlannerConfig
from .schema import extract_json_object

logger = logging.getLogger(__name__)

DENY_SUBSTRINGS = (
    "晚安",
    "早安",
    "早上好",
    "摸头",
    "摸摸",
    "吃饭",
    "午饭",
    "想你",
    "想阿洛娜",
    "抱抱",
    "亲亲",
    "喜欢你",
    "去睡觉",
)

ROUTER_SYSTEM = """你是桌面陪伴助手「阿洛娜」的电脑操作路由器。你不写台词，也不执行操作。
判断老师这句话是不是在请阿洛娜立刻操作这台 Windows 电脑（短操作：开开始菜单、按快捷键、在当前输入框打几个字、点屏幕上已经能看清的大按钮）。
只输出一个 JSON 对象，不要 Markdown。
computer_use 为 true 仅当：老师明确要求动手操作电脑，且任务短、不涉及聊天陪伴、不问感受。
以下必须 false：问好、摸头、吃饭、想你、闲聊、提问、让阿洛娜说话、复杂多步/多应用、填表、密码、不确定。
拿不准必须 false。
JSON：{"computer_use": false}"""


def is_denied_computer_use(text: str | None) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return True
    return any(token in stripped for token in DENY_SUBSTRINGS)


def parse_route_decision(raw: str | dict[str, Any] | None) -> bool:
    if isinstance(raw, dict):
        data = raw
    else:
        data = extract_json_object(raw or "")
    if not isinstance(data, dict):
        return False
    value = data.get("computer_use")
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    return False


class ComputerUseRouter:
    def __init__(self, planner: PlannerConfig, computer_use: ComputerUseConfig) -> None:
        self.planner = planner
        self.computer_use = computer_use

    @property
    def llm_enabled(self) -> bool:
        key = (self.planner.api_key or "").strip()
        return bool(
            self.planner.enabled
            and key
            and key != "YOUR_DEEPSEEK_API_KEY"
        )

    async def should_operate(self, user_text: str | None) -> bool:
        text = (user_text or "").strip()
        if not text or is_denied_computer_use(text):
            logger.info("computer_use route deny text=%r", text)
            return False
        if not self.llm_enabled:
            logger.info("computer_use route default_false reason=no_llm")
            return False
        timeout = float(self.computer_use.route_timeout_sec or 3.0)
        url = self.planner.base_url.rstrip("/") + "/chat/completions"
        payload: dict[str, Any] = {
            "model": self.planner.model,
            "messages": [
                {"role": "system", "content": ROUTER_SYSTEM},
                {
                    "role": "user",
                    "content": f"【老师本段】{text}\n请输出唯一 JSON 对象。",
                },
            ],
            "temperature": 0.0,
            "max_tokens": 64,
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
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
            content = data["choices"][0]["message"]["content"] or ""
            decision = parse_route_decision(content)
            logger.info("computer_use route llm computer_use=%s raw=%s", decision, content)
            return decision
        except Exception as exc:
            logger.warning("computer_use route llm failed: %s", exc)
            return False
