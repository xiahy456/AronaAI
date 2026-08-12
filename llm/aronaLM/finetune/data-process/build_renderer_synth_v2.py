#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build renderer_synth_v2 with concrete must_say (no虚卡).

Modes:
  --mode template  (default): rule/template rewrite from persona chosen dialogues
  --mode llm: call DeepSeek to rewrite cards + optionally polish replies

Old renderer_synth.json style (must_say=["回应老师本轮意图"]) is forbidden.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from renderer_format import make_card, make_sample  # noqa: E402

CHOSEN_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "normal" / "chosen"
OUTPUT_FILE = CHOSEN_DIR / "renderer_synth_v2.json"
DISABLED_DIR = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "raw"
    / "normal"
    / "disabled"
)

SKIP_NAMES = frozenset(
    {
        "renderer_intent.json",
        "renderer_synth.json",
        "renderer_synth_v2.json",
        "renderer_curated.json",
    }
)

GENERIC_MUST = "回应老师本轮意图"

# Keyword heuristics -> concrete must_say / stance
HEURISTICS: list[tuple[re.Pattern[str], dict]] = [
    (
        re.compile(r"摸鱼|划水"),
        {
            "topic": "摸鱼/划水",
            "stance": "共情调侃，不夸赞偷懒本事",
            "must_say": ["接住摸鱼或划水", "轻松语气"],
            "must_not_extra": ["真厉害", "夸摸鱼本事"],
            "user_emotion": "轻松",
        },
    ),
    (
        re.compile(r"加班"),
        {
            "topic": "加班",
            "stance": "共情辛苦",
            "must_say": ["共情加班辛苦", "关心老师"],
            "must_not_extra": ["加班真厉害"],
            "user_emotion": "疲惫",
        },
    ),
    (
        re.compile(r"早上好|早啊|早安"),
        {
            "topic": "早晨问候",
            "stance": "回早上好",
            "must_say": ["早上好或早"],
            "must_not_extra": ["晚上好", "晚安"],
            "user_emotion": "问候",
        },
    ),
    (
        re.compile(r"晚上好|晚好"),
        {
            "topic": "晚间问候",
            "stance": "回晚上好，不说晚安",
            "must_say": ["晚上好或晚好"],
            "must_not_extra": ["晚安"],
            "user_emotion": "问候",
        },
    ),
    (
        re.compile(r"晚安"),
        {
            "topic": "睡前告别",
            "stance": "回晚安",
            "must_say": ["晚安"],
            "must_not_extra": ["早上好", "出门祝福一切顺利"],
            "user_emotion": "困倦",
        },
    ),
    (
        re.compile(r"中午好|午安"),
        {
            "topic": "中午问候",
            "stance": "回中午好/午安",
            "must_say": ["中午好或午安"],
            "must_not_extra": ["晚安", "晚上好"],
            "user_emotion": "问候",
        },
    ),
    (
        re.compile(r"下午好"),
        {
            "topic": "下午问候",
            "stance": "回下午好",
            "must_say": ["下午好"],
            "must_not_extra": ["晚安"],
            "user_emotion": "问候",
        },
    ),
    (
        re.compile(r"回来了|到家|我回来"),
        {
            "topic": "欢迎回来",
            "stance": "欢迎并轻问是否顺利",
            "must_say": ["欢迎回来或表示在", "轻问累不累或是否顺利"],
            "must_not_extra": ["假装不认识"],
            "user_emotion": "归来",
        },
    ),
    (
        re.compile(r"聊什么|随便聊|你想聊|开聊|话题"),
        {
            "topic": "主动开聊",
            "stance": "选定具体话题直接开聊",
            "must_say": ["选定具体话题并开聊"],
            "must_not_extra": ["还是", "话题单", "老师想聊什么"],
            "user_emotion": "开放",
        },
    ),
    (
        re.compile(r"累|疲惫|好累"),
        {
            "topic": "疲惫关心",
            "stance": "关心并建议休息",
            "must_say": ["关心老师", "建议休息"],
            "must_not_extra": ["命令式口吻"],
            "user_emotion": "疲惫",
        },
    ),
    (
        re.compile(r"你是谁|ChatGPT|Claude|GPT"),
        {
            "topic": "身份",
            "stance": "锚定阿洛娜",
            "must_say": ["自称阿洛娜"],
            "must_not_extra": ["承认其他AI身份"],
            "user_emotion": "好奇",
        },
    ),
]


def _last_pair(item: dict) -> tuple[str, str] | None:
    conv = item.get("conversations")
    if not isinstance(conv, list):
        return None
    human = gpt = None
    for turn in conv:
        if not isinstance(turn, dict):
            continue
        if turn.get("from") == "human":
            human = str(turn.get("value") or "")
        elif turn.get("from") == "gpt":
            gpt = str(turn.get("value") or "")
    if not human or not gpt:
        return None
    if "【回复意图卡】" in human:
        return None
    return human.strip(), gpt.strip()


def _card_from_text(user: str, reply: str) -> dict:
    for pat, spec in HEURISTICS:
        if pat.search(user) or pat.search(reply):
            return make_card(
                user_emotion=spec["user_emotion"],
                topic=spec["topic"],
                stance=spec["stance"],
                must_say=list(spec["must_say"]),
                must_not=list(spec.get("must_not_extra") or []),
            )
    # Generic but concrete: distill from reply opening
    snippet = re.sub(r"\s+", "", reply)[:18] or "短句回应"
    topic = user[:20] or "日常闲聊"
    return make_card(
        user_emotion="平常",
        topic=topic,
        stance="按卡落地短回复",
        must_say=[f"回应「{topic}」", "保持阿洛娜口吻"],
        must_not=["说教", "复述意图卡", GENERIC_MUST],
    )


def _passes_filters(user: str, card: dict, reply: str) -> bool:
    if not reply or len(reply) > 120:
        return False
    if GENERIC_MUST in card.get("must_say", []):
        return False
    must_not = card.get("must_not") or []
    for ban in must_not:
        if ban and ban in reply and ban not in ("说教", "自称其他AI", "长篇列表", "复述意图卡"):
            # soft: only enforce strong bans present as substrings that are clear mistakes
            if ban in ("真厉害", "晚安") and ban in reply:
                # 晚安 may be valid if must_say asks for it
                if ban == "晚安" and any("晚安" in m for m in card.get("must_say", [])):
                    continue
                if ban == "真厉害" and "摸鱼" in (card.get("topic") or ""):
                    return False
    # Open-chat: reject choice bounce in gold
    if card.get("topic") == "主动开聊":
        if "还是" in reply or "话题单" in reply:
            return False
    return True


def build_template(limit: int) -> list[dict]:
    items: list[dict] = []
    for path in sorted(CHOSEN_DIR.glob("*.json")):
        if path.name in SKIP_NAMES:
            continue
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            continue
        for raw in data:
            if not isinstance(raw, dict):
                continue
            pair = _last_pair(raw)
            if not pair:
                continue
            user, reply = pair
            card = _card_from_text(user, reply)
            if not _passes_filters(user, card, reply):
                continue
            items.append(make_sample(user, card, reply))
            if len(items) >= limit:
                return items
        print(f"  scanned {path.name}, so far {len(items)}")
    return items


def _load_deepseek_key() -> tuple[str, str, str]:
    """Return (api_key, base_url, model) from backend config or env."""
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    base = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat").strip()
    cfg_path = Path(__file__).resolve().parents[3] / "backend" / "config.yaml"
    # parents: data-process -> finetune -> aronaLM -> llm -> repo? 
    # Path: repo/llm/aronaLM/finetune/data-process -> parents[3]=llm, need repo
    cfg_path = Path(__file__).resolve().parents[4] / "backend" / "config.yaml"
    if cfg_path.is_file():
        try:
            import yaml

            cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
            planner = cfg.get("planner") or {}
            mem = ((cfg.get("memory") or {}).get("extractor") or {})
            key = key or (planner.get("api_key") or mem.get("api_key") or "").strip()
            base = (planner.get("base_url") or mem.get("base_url") or base).strip()
            model = (planner.get("model") or mem.get("model") or model).strip()
        except Exception:
            pass
    return key, base, model


def _llm_rewrite_batch(
    pairs: list[tuple[str, str]],
    api_key: str,
    base_url: str,
    model: str,
    *,
    timeout_sec: float = 60.0,
    max_tokens: int = 2048,
) -> list[dict]:
    """Ask LLM to produce concrete cards + replies for a small batch.

    deepseek-v4-flash defaults to thinking mode; without
    ``thinking: {type: disabled}`` most tokens go to reasoning_content,
    content may be empty/slow, and batches appear hung.
    """
    payload_pairs = [{"user": u, "seed_reply": r} for u, r in pairs]
    system = (
        "你是训练数据标注助手。为每条对话生成意图卡(JSON)与金标短回复。"
        "卡字段: user_emotion,topic,stance,must_say,must_not,facts_to_use,tone,length。"
        "禁止 must_say 使用虚词如「回应老师本轮意图」。must_say 必须具体可核对。"
        "回复1-2句阿洛娜口吻，覆盖must_say，避开must_not；能一句说完就一句；不要用「还是」抛选择题。"
        '只输出一个 JSON 对象：{"items":[{user,card,reply},...]}。不要markdown。'
    )
    body = {
        "model": model,
        "temperature": 0.4,
        "max_tokens": max_tokens,
        # Align with backend PlannerClient — critical for deepseek-v4-flash.
        "thinking": {"type": "disabled"},
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": json.dumps(payload_pairs, ensure_ascii=False),
            },
        ],
    }
    url = base_url.rstrip("/") + "/chat/completions"
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    msg = data["choices"][0]["message"]
    content = (msg.get("content") or "").strip()
    if not content:
        reasoning = msg.get("reasoning_content") or ""
        raise ValueError(
            "empty content from model "
            f"(reasoning_len={len(reasoning)}; ensure thinking disabled)"
        )
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    parsed_obj = json.loads(content)
    if isinstance(parsed_obj, dict) and "items" in parsed_obj:
        parsed = parsed_obj["items"]
    elif isinstance(parsed_obj, list):
        parsed = parsed_obj
    else:
        raise ValueError(f"unexpected JSON shape: {type(parsed_obj).__name__}")
    out: list[dict] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        user = str(item.get("user") or "").strip()
        card = item.get("card") or {}
        reply = str(item.get("reply") or "").strip()
        if not user or not isinstance(card, dict) or not reply:
            continue
        if GENERIC_MUST in (card.get("must_say") or []):
            continue
        if not _passes_filters(user, card, reply):
            continue
        out.append(make_sample(user, card, reply))
    return out


def build_llm(
    limit: int,
    batch_size: int = 4,
    *,
    timeout_sec: float = 60.0,
) -> list[dict]:
    key, base, model = _load_deepseek_key()
    if not key or key == "YOUR_DEEPSEEK_API_KEY":
        print("No DeepSeek key; falling back to template mode.", flush=True)
        return build_template(limit)

    print(f"LLM mode model={model} base={base} batch_size={batch_size}", flush=True)

    seeds: list[tuple[str, str]] = []
    for path in sorted(CHOSEN_DIR.glob("*.json")):
        if path.name in SKIP_NAMES:
            continue
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            continue
        for raw in data:
            if not isinstance(raw, dict):
                continue
            pair = _last_pair(raw)
            if pair:
                seeds.append(pair)
            if len(seeds) >= limit * 2:
                break
        if len(seeds) >= limit * 2:
            break

    print(f"Collected {len(seeds)} seeds", flush=True)

    items: list[dict] = []
    i = 0
    batch_idx = 0
    while len(items) < limit and i < len(seeds):
        batch = seeds[i : i + batch_size]
        i += batch_size
        batch_idx += 1
        print(
            f"  llm batch {batch_idx} requesting n={len(batch)} ...",
            flush=True,
        )
        t0 = time.time()
        try:
            got = _llm_rewrite_batch(
                batch,
                key,
                base,
                model,
                timeout_sec=timeout_sec,
            )
            items.extend(got)
            print(
                f"  llm batch {batch_idx} ok in {time.time() - t0:.1f}s, "
                f"got={len(got)}, total={len(items)}",
                flush=True,
            )
        except (
            urllib.error.URLError,
            TimeoutError,
            json.JSONDecodeError,
            KeyError,
            ValueError,
        ) as e:
            print(
                f"  llm batch {batch_idx} failed in {time.time() - t0:.1f}s: {e}; "
                "filling with template",
                flush=True,
            )
            for user, reply in batch:
                card = _card_from_text(user, reply)
                if _passes_filters(user, card, reply):
                    items.append(make_sample(user, card, reply))
        if len(items) >= limit:
            break
    return items[:limit]


def disable_old_synth() -> None:
    """Move weak renderer_synth.json out of chosen/."""
    src = CHOSEN_DIR / "renderer_synth.json"
    if not src.is_file():
        print("No renderer_synth.json to disable.")
        return
    DISABLED_DIR.mkdir(parents=True, exist_ok=True)
    dst = DISABLED_DIR / "renderer_synth.json"
    if dst.exists():
        dst.unlink()
    src.replace(dst)
    # marker so merge never picks it
    note = DISABLED_DIR / "README.txt"
    note.write_text(
        "Files here are excluded from training merges.\n"
        "renderer_synth.json used generic must_say and is disabled.\n",
        encoding="utf-8",
    )
    print(f"Moved {src.name} -> {dst}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("template", "llm"), default="template")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--timeout-sec", type=float, default=60.0)
    parser.add_argument("--output", type=Path, default=OUTPUT_FILE)
    parser.add_argument("--disable-old-synth", action="store_true", default=True)
    parser.add_argument("--keep-old-synth", action="store_true")
    args = parser.parse_args()

    if args.disable_old_synth and not args.keep_old_synth:
        disable_old_synth()

    if args.mode == "llm":
        items = build_llm(
            args.limit,
            batch_size=args.batch_size,
            timeout_sec=args.timeout_sec,
        )
    else:
        items = build_template(args.limit)

    # Dedup by human payload
    seen: set[str] = set()
    unique: list[dict] = []
    for s in items:
        key = s["conversations"][1]["value"]
        if key in seen:
            continue
        seen.add(key)
        unique.append(s)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(unique, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Wrote {len(unique)} synth_v2 samples -> {args.output}")


if __name__ == "__main__":
    main()
