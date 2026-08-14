#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DeepSeek chat helper for renderer data-process scripts.

Credentials: env DEEPSEEK_* or backend/config.yaml planner / memory.extractor.
thinking disabled. Token cost is not optimized.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
BACKEND_CONFIG = REPO_ROOT / "backend" / "config.yaml"


def load_deepseek() -> tuple[str, str, str]:
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    base = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat").strip()
    if BACKEND_CONFIG.is_file():
        try:
            import yaml

            cfg = yaml.safe_load(BACKEND_CONFIG.read_text(encoding="utf-8")) or {}
            planner = cfg.get("planner") or {}
            mem = ((cfg.get("memory") or {}).get("extractor") or {})
            key = key or (planner.get("api_key") or mem.get("api_key") or "").strip()
            base = (planner.get("base_url") or mem.get("base_url") or base).strip()
            model = (planner.get("model") or mem.get("model") or model).strip()
        except Exception:
            pass
    return key, base, model


def extract_json(text: str) -> Any:
    content = (text or "").strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}|\[[\s\S]*\]", content)
        if not match:
            raise
        return json.loads(match.group(0))


def chat_json(
    *,
    system: str,
    user: str,
    temperature: float = 0.3,
    max_tokens: int = 1024,
    timeout_sec: int = 60,
) -> Any:
    key, base, model = load_deepseek()
    if not key or key == "YOUR_DEEPSEEK_API_KEY":
        raise RuntimeError("DeepSeek API key missing (backend/config.yaml planner)")
    body = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "thinking": {"type": "disabled"},
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    url = base.rstrip("/") + "/chat/completions"
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"DeepSeek HTTP {exc.code}: {detail}") from exc
    content = (data["choices"][0]["message"].get("content") or "").strip()
    return extract_json(content)
