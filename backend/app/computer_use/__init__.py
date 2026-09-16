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

"""Computer use: conservative router, vision short loop, hardcoded probe."""

from .agent import run_vision_agent
from .client import VisionClient
from .loop import ProbeResult, probe_reply_text, run_action_loop, run_probe, terminal_messages
from .probe import (
    PROBE_ALIAS,
    PROBE_ALIASES,
    PROBE_CANCELLED_REPLY,
    PROBE_DISABLED_REPLY,
    PROBE_DONE_REPLY,
    PROBE_FAILED_REPLY,
    PROBE_TOKEN,
    is_probe_text,
    probe_actions,
)
from .prompts import (
    AGENT_CANCELLED_REPLY,
    AGENT_SPEAK_FALLBACK,
    HISTORY_COMPUTER_USE_MARKER,
    build_computer_use_instruction,
    computer_use_history_content,
)
from .router import (
    ComputerUseRouter,
    build_route_user_message,
    format_route_history,
    is_denied_computer_use,
    parse_route_decision,
)
from .schema import (
    ACTION_WHITELIST,
    ComputerUseAction,
    ComputerUseObservation,
    SchemaError,
    ScreenGeometry,
    parse_action,
    parse_observation,
    parse_screen,
    parse_vision_action,
)

__all__ = [
    "ACTION_WHITELIST",
    "AGENT_CANCELLED_REPLY",
    "AGENT_SPEAK_FALLBACK",
    "HISTORY_COMPUTER_USE_MARKER",
    "PROBE_ALIAS",
    "PROBE_ALIASES",
    "PROBE_CANCELLED_REPLY",
    "PROBE_DISABLED_REPLY",
    "PROBE_DONE_REPLY",
    "PROBE_FAILED_REPLY",
    "PROBE_TOKEN",
    "ComputerUseAction",
    "ComputerUseObservation",
    "ComputerUseRouter",
    "ProbeResult",
    "SchemaError",
    "ScreenGeometry",
    "VisionClient",
    "build_computer_use_instruction",
    "build_route_user_message",
    "computer_use_history_content",
    "format_route_history",
    "is_denied_computer_use",
    "is_probe_text",
    "parse_action",
    "parse_observation",
    "parse_route_decision",
    "parse_screen",
    "parse_vision_action",
    "probe_actions",
    "probe_reply_text",
    "run_action_loop",
    "run_probe",
    "run_vision_agent",
    "terminal_messages",
]
