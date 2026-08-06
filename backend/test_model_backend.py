"""
测试模型后端能否正常接收用户输入并返回输出。

用法（在项目根目录）:
  python -m backend.test_model_backend
  python -m backend.test_model_backend --prompt "你好，你是谁？"
  python -m backend.test_model_backend --interactive
  python -m backend.test_model_backend --ws   # 需先启动: python -m backend.ai_service

可选参数:
  --no-rag / --no-memory / --no-cache  关闭对应管线（默认关闭，便于纯测模型）
  --ws-url ws://127.0.0.1:20456/ws
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# 保证可从任意 cwd 导入 backend
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


DEFAULT_PROMPTS = [
    "你好，你是谁？",
    "老师今天有点累了。",
]


def _print_header(title: str) -> None:
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def _print_result(label: str, payload: Dict[str, Any]) -> None:
    print(f"\n[{label}]")
    for key in ("backend", "latency", "from_cache", "context_used", "session_id"):
        if key in payload and payload[key] is not None:
            print(f"  {key}: {payload[key]}")
    content = payload.get("response") or payload.get("content") or ""
    print("  --- 回复 ---")
    print(f"  {content}")
    print("  ------------")
    if "<think>" in content or "</think>" in content:
        print("  [警告] 回复中含有 <think> 标签")


def test_model_loader(prompt: str) -> Dict[str, Any]:
    """直接测 ModelLoader（最短路径，不走 RAG/缓存）。"""
    from backend.config import MODEL_CONFIG
    from backend.model_loader import ModelLoader
    from backend.arona_engine import AronaEngine

    backend = str(MODEL_CONFIG.get("backend", "hf"))
    print(f"MODEL_CONFIG.backend = {backend}")
    if backend == "gguf":
        print(f"gguf_path = {MODEL_CONFIG.get('gguf_path')}")

    loader = ModelLoader()
    t0 = time.time()
    loader.load()
    load_sec = time.time() - t0
    print(f"模型加载耗时: {load_sec:.2f}s")

    engine = AronaEngine()
    system_prompt = engine.system_prompt

    t1 = time.time()
    response = loader.generate(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
    )
    gen_sec = time.time() - t1

    result = {
        "backend": backend,
        "latency": round(gen_sec, 3),
        "response": response,
        "from_cache": False,
        "context_used": False,
        "session_id": None,
        "ok": bool(response and str(response).strip()),
    }
    _print_result("ModelLoader.generate", result)
    return result


def test_engine_chat(
    prompt: str,
    *,
    use_cache: bool = False,
    use_rag: bool = False,
    use_memory: bool = False,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """通过 AronaEngine.chat 测完整对话入口。"""
    from backend.config import MODEL_CONFIG
    from backend.arona_engine import AronaEngine

    engine = AronaEngine()
    result = engine.chat(
        user_input=prompt,
        session_id=session_id,
        use_cache=use_cache,
        use_rag=use_rag,
        use_memory=use_memory,
    )
    out = {
        "backend": MODEL_CONFIG.get("backend"),
        "latency": round(float(result.get("latency", 0)), 3),
        "response": result.get("response", ""),
        "from_cache": result.get("from_cache"),
        "context_used": result.get("context_used"),
        "session_id": result.get("session_id"),
        "ok": bool((result.get("response") or "").strip()),
    }
    _print_result("AronaEngine.chat", out)
    return out


async def test_websocket(
    prompt: str,
    *,
    ws_url: str,
    use_cache: bool = False,
    use_rag: bool = False,
    use_memory: bool = False,
) -> Dict[str, Any]:
    """对已启动的 ai_service 发一条 chat，校验 chat_response。"""
    try:
        import websockets
    except ImportError as e:
        raise ImportError(
            "WebSocket 测试需要 websockets 包: pip install websockets"
        ) from e

    t0 = time.time()
    async with websockets.connect(ws_url, open_timeout=30) as ws:
        connected = json.loads(await ws.recv())
        if connected.get("type") != "connected":
            raise RuntimeError(f"未收到 connected 消息: {connected}")

        await ws.send(
            json.dumps(
                {
                    "type": "chat",
                    "content": prompt,
                    "stream": False,
                    "options": {
                        "use_cache": use_cache,
                        "use_rag": use_rag,
                        "use_memory": use_memory,
                    },
                },
                ensure_ascii=False,
            )
        )

        while True:
            msg = json.loads(await ws.recv())
            msg_type = msg.get("type")
            if msg_type == "chat_response":
                out = {
                    "backend": "websocket",
                    "latency": msg.get("latency"),
                    "response": msg.get("content", ""),
                    "from_cache": msg.get("from_cache"),
                    "context_used": msg.get("context_used"),
                    "session_id": connected.get("session_id"),
                    "ok": bool((msg.get("content") or "").strip()),
                    "wall_sec": round(time.time() - t0, 3),
                }
                _print_result("WebSocket /ws chat", out)
                return out
            if msg_type == "error":
                raise RuntimeError(f"服务端错误: {msg}")


def run_interactive(
    *,
    use_cache: bool,
    use_rag: bool,
    use_memory: bool,
) -> None:
    from backend.arona_engine import AronaEngine

    engine = AronaEngine()
    session_id = None
    print("交互模式已启动。输入空行或 /q 退出，/clear 清空会话。")
    while True:
        try:
            text = input("\n老师> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n退出。")
            break
        if not text or text in {"/q", "/quit", "/exit"}:
            print("退出。")
            break
        if text == "/clear":
            session_id = None
            print("会话已清空。")
            continue
        result = engine.chat(
            user_input=text,
            session_id=session_id,
            use_cache=use_cache,
            use_rag=use_rag,
            use_memory=use_memory,
        )
        session_id = result.get("session_id")
        print(f"阿洛娜 ({result.get('latency', 0):.2f}s)> {result.get('response', '')}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="测试 Arona 模型后端输入/输出")
    p.add_argument(
        "--prompt",
        "-p",
        action="append",
        dest="prompts",
        help="测试用语（可多次指定）；默认使用内置样例",
    )
    p.add_argument(
        "--mode",
        choices=("loader", "engine", "both"),
        default="both",
        help="本地测试路径（默认 both）",
    )
    p.add_argument(
        "--ws",
        action="store_true",
        help="额外通过 WebSocket 测已启动的 ai_service",
    )
    p.add_argument(
        "--ws-url",
        default="ws://127.0.0.1:20456/ws",
        help="WebSocket 地址",
    )
    p.add_argument("--interactive", "-i", action="store_true", help="交互对话")
    p.add_argument("--use-cache", action="store_true", help="启用语义缓存")
    p.add_argument("--use-rag", action="store_true", help="启用 RAG")
    p.add_argument("--use-memory", action="store_true", help="启用记忆")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    prompts: List[str] = args.prompts or list(DEFAULT_PROMPTS)
    use_cache = args.use_cache
    use_rag = args.use_rag
    use_memory = args.use_memory

    if args.interactive:
        _print_header("交互测试 AronaEngine")
        run_interactive(
            use_cache=use_cache, use_rag=use_rag, use_memory=use_memory
        )
        return 0

    failures = 0
    session_id: Optional[str] = None

    for i, prompt in enumerate(prompts, 1):
        _print_header(f"用例 {i}/{len(prompts)}: {prompt}")

        if args.mode in ("loader", "both"):
            try:
                r = test_model_loader(prompt)
                if not r.get("ok"):
                    failures += 1
                    print("  [FAIL] 空回复")
            except Exception as e:
                failures += 1
                print(f"  [FAIL] ModelLoader: {e}")

        if args.mode in ("engine", "both"):
            try:
                r = test_engine_chat(
                    prompt,
                    use_cache=use_cache,
                    use_rag=use_rag,
                    use_memory=use_memory,
                    session_id=session_id,
                )
                session_id = r.get("session_id") or session_id
                if not r.get("ok"):
                    failures += 1
                    print("  [FAIL] 空回复")
            except Exception as e:
                failures += 1
                print(f"  [FAIL] AronaEngine: {e}")

        if args.ws:
            import asyncio

            try:
                r = asyncio.run(
                    test_websocket(
                        prompt,
                        ws_url=args.ws_url,
                        use_cache=use_cache,
                        use_rag=use_rag,
                        use_memory=use_memory,
                    )
                )
                if not r.get("ok"):
                    failures += 1
                    print("  [FAIL] 空回复")
            except Exception as e:
                failures += 1
                print(f"  [FAIL] WebSocket: {e}")

    _print_header("汇总")
    total = len(prompts) * (
        (1 if args.mode in ("loader", "both") else 0)
        + (1 if args.mode in ("engine", "both") else 0)
        + (1 if args.ws else 0)
    )
    print(f"失败: {failures} / 检查点约 {total}")
    if failures:
        print("结果: FAIL")
        return 1
    print("结果: OK — 后端可正常接收输入并返回输出")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
