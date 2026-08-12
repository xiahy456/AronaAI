#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rewrite renderer training samples to hard 1–2 sentence replies.

Pipeline: rule prep -> DeepSeek rewrite (optional) -> QA -> write JSON.
Uses backend/config.yaml planner credentials. thinking disabled.
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
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from renderer_format import make_sample  # noqa: E402

CHOSEN_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "normal" / "chosen"
MANUAL_QUEUE = CHOSEN_DIR.parent / "disabled" / "needs_manual_short.json"

_SENT_SPLIT = re.compile(r"(?<=[。！？!?~～])\s*")
_CARD_RE = re.compile(
    r"【回复意图卡】\s*\n(\{.*?\})\s*\n\s*【老师原话】\s*\n(.*?)\n\s*请严格按意图卡",
    re.S,
)


def sentence_count(text: str) -> int:
    t = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()
    if not t:
        return 0
    parts = [p for p in _SENT_SPLIT.split(t) if p.strip()]
    return len(parts) if parts else (1 if t else 0)


def split_sentences(text: str) -> list[str]:
    t = (text or "").strip()
    parts = [p.strip() for p in _SENT_SPLIT.split(t) if p.strip()]
    return parts if parts else ([t] if t else [])


def load_deepseek() -> tuple[str, str, str]:
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    base = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat").strip()
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


def parse_sample(item: dict[str, Any]) -> tuple[str, dict[str, Any], str] | None:
    conv = item.get("conversations")
    if not isinstance(conv, list):
        return None
    human = gpt = ""
    for turn in conv:
        if not isinstance(turn, dict):
            continue
        if turn.get("from") == "human":
            human = str(turn.get("value") or "")
        elif turn.get("from") == "gpt":
            gpt = str(turn.get("value") or "")
    if not human or not gpt:
        return None
    m = _CARD_RE.search(human)
    if not m:
        # try looser: first JSON object
        jm = re.search(r"\{[\s\S]*\}", human)
        um = re.search(r"【老师原话】\s*\n(.+?)(?:\n\s*请严格|$)", human, re.S)
        if not jm or not um:
            return None
        try:
            card = json.loads(jm.group(0))
        except json.JSONDecodeError:
            return None
        return um.group(1).strip(), card, gpt.strip()
    try:
        card = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None
    if not isinstance(card, dict):
        return None
    return m.group(2).strip(), card, gpt.strip()


def normalize_card_fields(card: dict[str, Any]) -> dict[str, Any]:
    out = dict(card)
    out.pop("arona_emotion", None)
    out["length"] = "1-2句"
    must = out.get("must_say")
    if isinstance(must, list) and len(must) > 2:
        out["must_say"] = must[:2]
        out["_must_say_was_long"] = True
    else:
        out["_must_say_was_long"] = False
    # also fix nested string dumps of length in case
    return out


def needs_llm(card: dict[str, Any], reply: str) -> bool:
    if card.get("_must_say_was_long"):
        return True
    n = sentence_count(reply)
    if n >= 3:
        return True
    if len(reply.strip()) > 70:
        return True
    must = card.get("must_say") or []
    if isinstance(must, list) and len(must) > 2:
        return True
    return False


def qa_ok(card: dict[str, Any], reply: str) -> tuple[bool, str]:
    if not reply or not reply.strip():
        return False, "empty"
    n = sentence_count(reply)
    if n not in (1, 2):
        return False, f"sent={n}"
    if len(reply.strip()) > 80:
        return False, "too_long"
    if card.get("length") not in ("1-2句", "1–2句"):
        return False, "bad_length"
    must = card.get("must_say") or []
    if isinstance(must, list) and len(must) > 2:
        card["must_say"] = must[:2]
        must = card["must_say"]
    if not isinstance(must, list):
        return False, "must_say"
    must_not = card.get("must_not") or []
    for ban in must_not:
        if isinstance(ban, str) and ban and ban in (
            "真厉害",
            "话题单",
            "老师想聊什么",
        ) and ban in reply:
            return False, f"banned:{ban}"
    topic = str(card.get("topic") or "")
    if "开聊" in topic or "闲聊" in topic:
        if "话题单" in reply or "老师想聊什么" in reply:
            return False, "open_chat_bounce"
        if "还是" in reply and ("想聊" in reply or "？" in reply):
            return False, "choice_bounce"
    if "回应老师本轮意图" in (must if isinstance(must, list) else []):
        return False, "generic_must"
    return True, "ok"


def conservative_compress(card: dict[str, Any], reply: str) -> str | None:
    sents = split_sentences(reply)
    if not sents:
        return None
    if len(sents) <= 2 and len(reply) <= 80:
        return "".join(sents) if not reply.endswith(("。", "！", "？", "~", "～")) else reply
    kept = sents[:2]
    out = "".join(kept)
    # light must_say keyword check: at least one non-trivial char from each must_say
    must = card.get("must_say") or []
    for m in must:
        if not isinstance(m, str) or len(m) < 2:
            continue
        # skip meta instructions
        key = re.sub(r"[「」『』用回应]", "", m)[:4]
        if key and key not in out and m not in out:
            # try include first sentence only if shorter path fails QA later
            pass
    return out


def llm_rewrite_batch(
    items: list[dict[str, Any]],
    api_key: str,
    base_url: str,
    model: str,
    timeout_sec: float = 60.0,
) -> list[dict[str, Any]]:
    system = (
        "你是阿洛娜 Renderer 训练数据改写助手。把偏长样本压成 1–2 句金标。"
        "对每条输入输出 JSON 对象：{\"items\":[{\"idx\":0,\"card\":{...},\"reply\":\"...\"},...]}"
        "硬性：card.length 必须为 \"1-2句\"；card.must_say 最多 2 条且具体可核对；"
        "reply 恰好 1 或 2 句（中文句末标点），优先 1 句覆盖 must_say；"
        "避开 must_not；阿洛娜口吻；禁止还是抛回/话题单/复述 JSON；"
        "禁止同义反复第三段；不要引入卡外新事实。"
        "不要 markdown。"
    )
    payload = []
    for it in items:
        payload.append(
            {
                "idx": it["idx"],
                "user": it["user"],
                "old_card": {k: v for k, v in it["card"].items() if not str(k).startswith("_")},
                "old_reply": it["reply"],
            }
        )
    body = {
        "model": model,
        "temperature": 0.3,
        "max_tokens": 2048,
        "thinking": {"type": "disabled"},
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
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
    content = (data["choices"][0]["message"].get("content") or "").strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    parsed = json.loads(content)
    if isinstance(parsed, dict) and "items" in parsed:
        rows = parsed["items"]
    elif isinstance(parsed, list):
        rows = parsed
    else:
        raise ValueError("unexpected shape")
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        out.append(row)
    return out


def process_file(
    path: Path,
    *,
    use_llm: bool,
    batch_size: int,
    rewrite_all_cards: bool,
) -> tuple[list[dict], list[dict], dict[str, int]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path.name}: root must be array")

    stats = {
        "total": 0,
        "skip_llm": 0,
        "llm_ok": 0,
        "fallback": 0,
        "manual": 0,
        "failed_parse": 0,
    }
    key, base, model = load_deepseek() if use_llm else ("", "", "")
    if use_llm and (not key or key == "YOUR_DEEPSEEK_API_KEY"):
        print("No API key; rule-only mode.", flush=True)
        use_llm = False

    pending_llm: list[dict[str, Any]] = []
    results: dict[int, dict[str, Any]] = {}
    manual: list[dict] = []

    for i, item in enumerate(data):
        stats["total"] += 1
        parsed = parse_sample(item) if isinstance(item, dict) else None
        if not parsed:
            # persona-like without intent card: compress gpt only later in merge
            results[i] = item
            stats["failed_parse"] += 1
            continue
        user, card, reply = parsed
        card = normalize_card_fields(card)
        # always normalize length string in card
        card["length"] = "1-2句"
        need = needs_llm(card, reply) or rewrite_all_cards
        # clean internal flag before save
        flag = card.pop("_must_say_was_long", False)
        if not need:
            sample = make_sample(user, card, reply)
            ok, reason = qa_ok(card, reply)
            if ok:
                results[i] = sample
                stats["skip_llm"] += 1
                continue
            need = True
            card["_must_say_was_long"] = flag

        pending_llm.append(
            {"idx": i, "user": user, "card": card, "reply": reply, "raw": item}
        )

    # LLM batches
    if use_llm and pending_llm:
        print(f"  {path.name}: LLM rewrite {len(pending_llm)} samples", flush=True)
        for off in range(0, len(pending_llm), batch_size):
            batch = pending_llm[off : off + batch_size]
            print(f"    batch {off // batch_size + 1} n={len(batch)} ...", flush=True)
            t0 = time.time()
            try:
                rows = llm_rewrite_batch(batch, key, base, model)
                by_idx = {int(r.get("idx")): r for r in rows if "idx" in r}
                for it in batch:
                    i = it["idx"]
                    row = by_idx.get(i)
                    if not row:
                        # fallback
                        card = {k: v for k, v in it["card"].items() if not str(k).startswith("_")}
                        card["length"] = "1-2句"
                        if isinstance(card.get("must_say"), list):
                            card["must_say"] = card["must_say"][:2]
                        compressed = conservative_compress(card, it["reply"])
                        if compressed and qa_ok(card, compressed)[0]:
                            results[i] = make_sample(it["user"], card, compressed)
                            stats["fallback"] += 1
                        else:
                            manual.append(it)
                            stats["manual"] += 1
                        continue
                    card = row.get("card") or {}
                    reply = str(row.get("reply") or "").strip()
                    if not isinstance(card, dict):
                        card = {}
                    card = normalize_card_fields(card)
                    card.pop("_must_say_was_long", None)
                    card["length"] = "1-2句"
                    if isinstance(card.get("must_say"), list):
                        card["must_say"] = card["must_say"][:2]
                    ok, reason = qa_ok(card, reply)
                    if ok:
                        results[i] = make_sample(it["user"], card, reply)
                        stats["llm_ok"] += 1
                    else:
                        compressed = conservative_compress(card, reply or it["reply"])
                        if compressed and qa_ok(card, compressed)[0]:
                            results[i] = make_sample(it["user"], card, compressed)
                            stats["fallback"] += 1
                        else:
                            manual.append({**it, "qa_fail": reason, "llm_reply": reply})
                            stats["manual"] += 1
                print(f"    ok in {time.time() - t0:.1f}s", flush=True)
            except (
                urllib.error.URLError,
                TimeoutError,
                json.JSONDecodeError,
                KeyError,
                ValueError,
            ) as e:
                print(f"    batch failed: {e}; fallback", flush=True)
                for it in batch:
                    i = it["idx"]
                    card = {k: v for k, v in it["card"].items() if not str(k).startswith("_")}
                    card["length"] = "1-2句"
                    if isinstance(card.get("must_say"), list):
                        card["must_say"] = card["must_say"][:2]
                    compressed = conservative_compress(card, it["reply"])
                    if compressed and qa_ok(card, compressed)[0]:
                        results[i] = make_sample(it["user"], card, compressed)
                        stats["fallback"] += 1
                    else:
                        manual.append(it)
                        stats["manual"] += 1
    else:
        for it in pending_llm:
            i = it["idx"]
            card = {k: v for k, v in it["card"].items() if not str(k).startswith("_")}
            card["length"] = "1-2句"
            if isinstance(card.get("must_say"), list):
                card["must_say"] = card["must_say"][:2]
            compressed = conservative_compress(card, it["reply"])
            if compressed and qa_ok(card, compressed)[0]:
                results[i] = make_sample(it["user"], card, compressed)
                stats["fallback"] += 1
            else:
                # keep original but force length in card via remake if possible
                try:
                    results[i] = make_sample(it["user"], card, compressed or it["reply"][:80])
                    # if still bad, manual
                    if not qa_ok(card, results[i]["conversations"][2]["value"])[0]:
                        manual.append(it)
                        stats["manual"] += 1
                        # still write best effort short
                except Exception:
                    manual.append(it)
                    stats["manual"] += 1
                    results[i] = it["raw"]

    out_list = [results[i] for i in range(len(data)) if i in results]
    return out_list, manual, stats


def build_short_seeds() -> list[dict]:
    """Hand-written 1-sentence (or tight 2-sentence) hard cases."""
    from renderer_format import make_card

    seeds: list[tuple[str, dict, str]] = [
        (
            "早上好。",
            make_card(
                user_emotion="平静",
                topic="早晨问候",
                stance="一句回早上好",
                must_say=["早上好"],
                must_not=["晚上好", "晚安"],
            ),
            "早上好，老师~",
        ),
        (
            "晚上好",
            make_card(
                user_emotion="平静",
                topic="晚间问候",
                stance="一句回晚上好",
                must_say=["晚上好"],
                must_not=["晚安"],
            ),
            "晚上好呀，老师~",
        ),
        (
            "晚安",
            make_card(
                user_emotion="困倦",
                topic="睡前告别",
                stance="一句晚安",
                must_say=["晚安"],
                must_not=["早上好"],
            ),
            "晚安，老师，好好休息~",
        ),
        (
            "我在摸鱼。",
            make_card(
                user_emotion="轻松",
                topic="摸鱼",
                stance="一句接梗",
                must_say=["接住摸鱼"],
                must_not=["真厉害"],
            ),
            "嘿嘿，老师偷偷歇一会儿，阿洛娜帮您看着~",
        ),
        (
            "今天又在划水。",
            make_card(
                user_emotion="自嘲",
                topic="划水",
                stance="一句调侃",
                must_say=["接住划水"],
                must_not=["真厉害"],
            ),
            "划水也要划得舒服点嘛，老师~",
        ),
        (
            "你想聊什么？",
            make_card(
                user_emotion="开放",
                topic="主动开聊",
                stance="一句点题开聊",
                must_say=["选定草莓牛奶并开聊"],
                must_not=["还是", "话题单", "老师想聊什么"],
            ),
            "那阿洛娜想先跟老师聊聊草莓牛奶，最近有没有好喝的新口味呀？",
        ),
        (
            "我们来聊聊天吧。",
            make_card(
                user_emotion="轻松",
                topic="主动开聊",
                stance="一句选定话题",
                must_say=["选定具体话题开聊"],
                must_not=["还是", "话题单"],
            ),
            "好呀，阿洛娜想聊今天有没有遇到好玩的小事~",
        ),
        (
            "阿洛娜你真可爱！",
            make_card(
                user_emotion="开心",
                topic="夸奖",
                stance="一句害羞感谢",
                must_say=["害羞感谢"],
                must_not=["自大"],
            ),
            "诶？谢、谢谢老师……阿洛娜好开心。",
        ),
        (
            "我好喜欢你。",
            make_card(
                user_emotion="亲昵",
                topic="表白",
                stance="一句开心回应",
                must_say=["表示开心"],
                must_not=["长篇恋爱承诺"],
            ),
            "老师这样说，阿洛娜心里暖暖的，好开心~",
        ),
        (
            "我回来了。",
            make_card(
                user_emotion="归来",
                topic="欢迎回来",
                stance="欢迎并轻问压成两句内",
                must_say=["欢迎回来", "轻问是否顺利"],
                must_not=["晚安"],
            ),
            "欢迎回来，老师~今天还顺利吗？",
        ),
        (
            "今天过得很不错。",
            make_card(
                user_emotion="愉快",
                topic="今日回顾",
                stance="一句接住开心",
                must_say=["接住愉快"],
                must_not=["再次问候"],
            ),
            "太好啦，老师今天开心阿洛娜也跟着开心~",
        ),
        (
            "谢谢你啊，阿洛娜。",
            make_card(
                user_emotion="感激",
                topic="感谢",
                stance="一句回应",
                must_say=["回应感谢"],
                must_not=["再次问候"],
            ),
            "不用谢，老师，能帮到您阿洛娜就很开心~",
        ),
    ]
    return [make_sample(u, c, r) for u, c, r in seeds]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument(
        "--rewrite-all-cards",
        action="store_true",
        help="Force LLM even when already short (still normalizes length locally otherwise)",
    )
    args = parser.parse_args()

    files = [
        CHOSEN_DIR / "renderer_curated.json",
        CHOSEN_DIR / "renderer_synth_v2.json",
    ]
    all_manual: list[dict] = []
    for path in files:
        if not path.is_file():
            print(f"skip missing {path}", flush=True)
            continue
        print(f"Processing {path.name} ...", flush=True)
        out, manual, stats = process_file(
            path,
            use_llm=not args.no_llm,
            batch_size=args.batch_size,
            rewrite_all_cards=args.rewrite_all_cards,
        )
        # append short seeds only into curated
        if path.name == "renderer_curated.json":
            seeds = build_short_seeds()
            out.extend(seeds)
            print(f"  appended {len(seeds)} short seeds", flush=True)
        path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  wrote {len(out)} -> {path}", flush=True)
        print(f"  stats={stats}", flush=True)
        all_manual.extend(manual)

    if all_manual:
        MANUAL_QUEUE.parent.mkdir(parents=True, exist_ok=True)
        MANUAL_QUEUE.write_text(
            json.dumps(all_manual, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"manual queue {len(all_manual)} -> {MANUAL_QUEUE}", flush=True)


if __name__ == "__main__":
    main()
