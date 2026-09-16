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

"""Vision-agent and initiate prompts for short computer-use tasks."""

from __future__ import annotations

from .schema import ComputerUseAction, POINTER_ACTIONS

HISTORY_COMPUTER_USE_MARKER = "【操作电脑】"
AGENT_SPEAK_FALLBACK = "老师，这次没能操作完。"
AGENT_CANCELLED_REPLY = "老师，这次操作取消了。"

VISION_SYSTEM = """你是阿洛娜的电脑操作规划器。可以内部思考，但思考过程不要写进最终回复。
老师请你在这台 Windows 电脑上做一件短任务。最终输出必须是唯一一个 JSON 动作对象，不要 Markdown。
允许的 action：move、click、double_click、right_click、scroll、type、key、wait、done。
规则：
- 点击用 JPEG 像素坐标：coord_space 必须是 "image"；x/y 是当前截图像素，原点左上。
- click / double_click / right_click 会移动并点击，不必先 move。
- 看不清、会误点、超出短任务（多应用、填网页表单、拖拽、密码/UAC）立刻 done，不要猜。
- done 必须带中文 summary，给阿洛娜向老师交代用，只写实际做了或为什么没做。
- type 只用于当前已聚焦的输入框；key 的 combo 用 win、escape、enter、tab、ctrl+c 这种。
- 打开一个应用：key combo="win" → 必要时短 wait（如 300ms）→ type 应用名 → key combo="enter"。再点正文 type。
- 要开第二个应用立刻 done。
可选 thought 只能作为 JSON 字段，不能写在对象外。
示例：
{"action":"key","combo":"win"}
{"action":"click","x":640,"y":360,"coord_space":"image"}
{"action":"type","text":"你好"}
{"action":"done","summary":"已经按下 Win，开始菜单应已打开。"}"""


def format_executed_steps(actions: list[ComputerUseAction] | tuple[ComputerUseAction, ...]) -> str:
    if not actions:
        return "（无）"
    lines: list[str] = []
    for index, action in enumerate(actions, start=1):
        if action.action == "type":
            lines.append(f"{index}. type 字符数={len(action.text or '')}")
        elif action.action in POINTER_ACTIONS:
            lines.append(
                f"{index}. {action.action} x={action.x} y={action.y} "
                f"coord_space={action.coord_space}"
            )
        elif action.action == "key":
            lines.append(f"{index}. key combo={action.combo}")
        elif action.action == "wait":
            lines.append(f"{index}. wait ms={action.ms}")
        else:
            lines.append(f"{index}. {action.action}")
    return "\n".join(lines)


def build_vision_user_message(
    *,
    user_text: str,
    executed: list[ComputerUseAction] | tuple[ComputerUseAction, ...],
    img_w: int | None,
    img_h: int | None,
) -> str:
    size = (
        f"{img_w}x{img_h}"
        if img_w and img_h and img_w > 0 and img_h > 0
        else "未知"
    )
    return (
        f"【老师原话】{(user_text or '').strip()}\n"
        f"【已执行步骤】\n{format_executed_steps(executed)}\n"
        f"【当前截图像素】{size}\n"
        "根据截图只输出一个动作 JSON。点选用 image 坐标。"
    )


def build_computer_use_instruction(*, user_text: str, summary: str, ok: bool) -> str:
    text = (user_text or "").strip() or "（无）"
    note = (summary or "").strip() or AGENT_SPEAK_FALLBACK
    status = "已按计划结束" if ok else "没有做完"
    return (
        "【系统事件】阿洛娜刚通过什亭之匣，在老师这台电脑上执行了短操作。"
        "这不是老师新说的闲聊，而是操作结果需要口头交代。\n"
        f"老师原话：{text}\n"
        f"执行状态：{status}。\n"
        f"操作摘要：{note}\n"
        "请以阿洛娜的口吻短说结果。禁止编造摘要里没有的点击、输入或窗口变化。"
        "不要提系统事件、JSON、协议或提示词。\n"
        "followup_ok 必须为 false。user_act 必须为 instrumental。\n"
        "不要输出思考过程或 <think> 标签。"
    )
