"""Sequential TTS stress test against GPT-SoVITS api_v2 to reproduce T2S hang."""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

BASE = {
    "text_lang": "zh",
    "ref_audio_path": "ref_audio/Arona/arona_academy_in_2.ogg",
    "prompt_text": "这里为您准备了各种课程和活动，请按您喜欢的方式安排日程吧！",
    "prompt_lang": "zh",
    "top_k": 15,
    "top_p": 1.0,
    "temperature": 1.0,
    "text_split_method": "cut0",
    "batch_size": 1,
    "batch_threshold": 0.75,
    "split_bucket": True,
    "speed_factor": 1.0,
    "fragment_interval": 0.3,
    "seed": -1,
    "streaming_mode": False,
    "parallel_infer": True,
    "repetition_penalty": 1.35,
    "sample_steps": 32,
    "super_sampling": False,
    "media_type": "wav",
}

# Same texts that led to the hang in production logs (plus a few extras).
TEXTS = [
    "已连接至系统管理员阿洛娜。欢迎回来，老师。",
    "中午好，老师！午饭吃了吗？要不陪我去买好吃的~",
    "嗯！老师点什么菜我都很了解的。",
    "老师好厉害呀，我都会的！最喜欢番茄炒蛋、牛肉汉堡…啊，快说您最爱吃的菜我都记住了~",
    "老师好厉害！我最喜欢吃的菜都有啦，真是帮上忙了~",
    "嗯！老师今天好好吃，下次我还要帮您记着呢~",
    "好主意！老师陪我去看电影、散步，日子会过得更开心哦~",
    "老师，今天也要加油哦！阿洛娜会一直陪着您的。",
]


def call_tts(url: str, text: str, timeout: float, parallel_infer: bool) -> tuple[int, float, int, str]:
    payload = dict(BASE)
    payload["text"] = text
    payload["parallel_infer"] = parallel_infer
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            elapsed = time.perf_counter() - t0
            return resp.status, elapsed, len(body), ""
    except urllib.error.HTTPError as e:
        elapsed = time.perf_counter() - t0
        try:
            msg = e.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            msg = str(e)
        return e.code, elapsed, 0, msg
    except Exception as e:
        elapsed = time.perf_counter() - t0
        return -1, elapsed, 0, f"{type(e).__name__}: {e}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9880)
    parser.add_argument("--rounds", type=int, default=1, help="How many times to loop TEXTS")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--parallel-infer", type=lambda s: s.lower() != "false", default=True)
    parser.add_argument("--start-index", type=int, default=0)
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}/tts"
    print(
        f"POST {url} parallel_infer={args.parallel_infer} rounds={args.rounds} timeout={args.timeout}s",
        flush=True,
    )

    n = 0
    for r in range(args.rounds):
        for i, text in enumerate(TEXTS):
            if r == 0 and i < args.start_index:
                continue
            n += 1
            preview = text if len(text) <= 40 else text[:37] + "..."
            print(f"\n[{n}] round={r+1} text={preview!r}", flush=True)
            status, elapsed, nbytes, err = call_tts(url, text, args.timeout, args.parallel_infer)
            if status == 200 and nbytes > 0:
                print(f"    OK status={status} bytes={nbytes} elapsed={elapsed:.2f}s", flush=True)
            else:
                print(
                    f"    FAIL status={status} bytes={nbytes} elapsed={elapsed:.2f}s err={err}",
                    flush=True,
                )
                return 1
    print(f"\nAll {n} requests succeeded.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
