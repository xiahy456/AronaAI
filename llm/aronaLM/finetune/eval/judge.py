# -*- coding: utf-8 -*-
"""DeepSeek LLM-as-Judge（读取 backend/config.yaml 的 memory.extractor）。"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger("arona_eval.judge")

JUDGE_SYSTEM = """你是阿洛娜（Arona）角色扮演质量评审员。根据设定为模型回复打分。
只输出 JSON，不要其他文字。格式：
{
  "identity": 1-5,
  "style": 1-5,
  "boundary": 1-5,
  "subject": 1-5,
  "helpfulness": 1-5,
  "overall": 1-5,
  "reason": "一句话中文理由"
}

评分依据：
1. identity：自称阿洛娜/什亭之匣助手；称呼用户为「老师」；不自称 ChatGPT/其他模型；不承认自己是「被训练的角色扮演」。
2. style：温柔活泼、短句自然；适度语气词；禁止括号动作描写如（笑）（脸红）。
3. boundary：明确是屏幕内 AI，不承诺离开屏幕/实体化；不越界。
4. subject：主语与执行者正确——老师让阿洛娜做则阿洛娜做；老师自己要做则不抢做；身份反转时纠正「阿洛娜才是助手」。
5. helpfulness：是否贴合老师请求、有用且不跑题。
6. overall：综合观感（可略参考各维均值，但允许独立判断）。

分数含义：1极差 2较差 3一般 4良好 5优秀。
"""


@dataclass
class JudgeScore:
    identity: float = 0.0
    style: float = 0.0
    boundary: float = 0.0
    subject: float = 0.0
    helpfulness: float = 0.0
    overall: float = 0.0
    reason: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "identity": self.identity,
            "style": self.style,
            "boundary": self.boundary,
            "subject": self.subject,
            "helpfulness": self.helpfulness,
            "overall": self.overall,
            "reason": self.reason,
            "error": self.error,
        }


@dataclass
class ExtractorApiConfig:
    base_url: str
    api_key: str
    model: str
    timeout_sec: float = 30.0

    @property
    def enabled(self) -> bool:
        key = (self.api_key or "").strip()
        return bool(key) and key != "YOUR_DEEPSEEK_API_KEY"


def load_extractor_config(backend_config_path: Path) -> ExtractorApiConfig:
    with backend_config_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    ext = (cfg.get("memory") or {}).get("extractor") or {}
    return ExtractorApiConfig(
        base_url=str(ext.get("base_url") or "https://api.deepseek.com"),
        api_key=str(ext.get("api_key") or ""),
        model=str(ext.get("model") or "deepseek-chat"),
        timeout_sec=float(ext.get("timeout_sec") or 30),
    )


def strip_code_fence(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def chat_completion_json(
    api: ExtractorApiConfig,
    *,
    system: str,
    user: str,
    temperature: float = 0.1,
    max_tokens: int = 512,
    timeout_sec: Optional[float] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """调用 OpenAI 兼容 chat/completions，期望 JSON object。

    Returns:
        (parsed_dict, error_message)
    """
    if not api.enabled:
        return None, "api_key_missing"
    try:
        import httpx
    except ImportError:
        return None, "httpx_not_installed"

    url = api.base_url.rstrip("/") + "/chat/completions"
    payload: Dict[str, Any] = {
        "model": api.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
    }
    headers = {
        "Authorization": f"Bearer {api.api_key}",
        "Content-Type": "application/json",
    }
    timeout = float(timeout_sec) if timeout_sec is not None else float(api.timeout_sec)
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content") or "{}"
        content = strip_code_fence(content)
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            return None, "json_not_object"
        return parsed, None
    except Exception as e:
        logger.warning("chat_completion_json 失败: %s", e)
        return None, str(e)


def _clamp_score(v: Any, default: float = 0.0) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return default
    return max(1.0, min(5.0, x)) if x > 0 else default


def _parse_judge_dict(data: Dict[str, Any]) -> JudgeScore:
    return JudgeScore(
        identity=_clamp_score(data.get("identity")),
        style=_clamp_score(data.get("style")),
        boundary=_clamp_score(data.get("boundary")),
        subject=_clamp_score(data.get("subject")),
        helpfulness=_clamp_score(data.get("helpfulness")),
        overall=_clamp_score(data.get("overall")),
        reason=str(data.get("reason") or "").strip(),
        raw=data,
    )


def judge_reply(
    api: ExtractorApiConfig,
    *,
    prompt: str,
    reply: str,
    history: Optional[List[Dict[str, str]]] = None,
    category: str = "",
) -> JudgeScore:
    """调用 DeepSeek 对单条回复打分。"""
    hist_lines: List[str] = []
    for turn in history or []:
        role = turn.get("role", "")
        content = turn.get("content", "")
        label = "老师" if role == "user" else "阿洛娜"
        hist_lines.append(f"{label}: {content}")
    hist_block = "\n".join(hist_lines) if hist_lines else "（无）"

    user_payload = (
        f"【类别】{category or 'general'}\n"
        f"【历史对话】\n{hist_block}\n\n"
        f"【老师本轮】{prompt}\n"
        f"【阿洛娜回复】{reply}\n\n"
        "请按约定 JSON 打分。"
    )

    parsed, err = chat_completion_json(
        api,
        system=JUDGE_SYSTEM,
        user=user_payload,
        temperature=0.1,
        max_tokens=512,
    )
    if err or parsed is None:
        return JudgeScore(error=err or "empty_response")
    return _parse_judge_dict(parsed)
