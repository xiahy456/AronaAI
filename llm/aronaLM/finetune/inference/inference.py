#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阿洛娜风格交互式推理脚本

加载基座模型 + LoRA 适配器，进行多轮对话测试。
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

FINETUNE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = FINETUNE_ROOT / "config" / "config.yaml"


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("arona_inference")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", "%H:%M:%S")
    )
    logger.addHandler(handler)
    return logger


def resolve_path(path_str: str, base: Path = FINETUNE_ROOT) -> Path:
    p = Path(path_str)
    if not p.is_absolute():
        p = (base / p).resolve()
    return p


def load_config(config_path: Path) -> Dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_messages(
    history: List[Dict[str, str]],
    user_text: str,
    system_prompt: Optional[str],
) -> List[Dict[str, str]]:
    messages: List[Dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.extend(history)
    messages.append({"role": "user", "content": user_text})
    return messages


def _sync_cuda_if_needed(model) -> None:
    """GPU 推理时同步，使计时更准确。"""
    try:
        import torch

        device = getattr(model, "device", None)
        if device is not None and getattr(device, "type", None) == "cuda":
            torch.cuda.synchronize(device)
        elif torch.cuda.is_available():
            torch.cuda.synchronize()
    except Exception:
        pass


def generate_reply(
    model,
    tokenizer,
    messages: List[Dict[str, str]],
    *,
    max_new_tokens: int,
    temperature: float,
    top_p: float,
    do_sample: bool,
    enable_thinking: bool,
) -> Tuple[str, float]:
    """根据对话历史生成回复。

    Returns:
        (回复文本, 耗时秒数)：从开始处理询问到解码完成。
    """
    t0 = time.perf_counter()

    try:
        prompt = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=enable_thinking,
        )
    except TypeError:
        prompt = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    input_len = inputs["input_ids"].shape[1]

    _sync_cuda_if_needed(model)
    outputs = model.generate(
        **inputs,
        max_new_tokens=max_new_tokens,
        temperature=temperature,
        top_p=top_p,
        do_sample=do_sample,
        pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
        eos_token_id=tokenizer.eos_token_id,
    )
    _sync_cuda_if_needed(model)

    new_tokens = outputs[0][input_len:]
    text = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

    # 若仍混入思考块，截取 </think> 之后内容
    if "</think>" in text:
        text = text.split("</think>")[-1].strip()

    elapsed = time.perf_counter() - t0
    return text, elapsed


def interactive_chat(
    model,
    tokenizer,
    infer_cfg: Dict[str, Any],
    enable_thinking: bool,
    logger: logging.Logger,
) -> None:
    system_prompt = (infer_cfg.get("system_prompt") or "").strip() or None
    max_new_tokens = int(infer_cfg.get("max_new_tokens", 256))
    temperature = float(infer_cfg.get("temperature", 0.7))
    top_p = float(infer_cfg.get("top_p", 0.9))
    do_sample = bool(infer_cfg.get("do_sample", True))

    history: List[Dict[str, str]] = []

    print()
    print("=" * 56)
    print("  阿洛娜对话测试（输入 quit / exit / q 退出，clear 清空历史）")
    print("=" * 56)
    if system_prompt:
        print(f"[系统提示已启用] {system_prompt[:80]}...")
    print()

    while True:
        try:
            user_text = input("老师: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见，老师！")
            break

        if not user_text:
            continue
        if user_text.lower() in {"quit", "exit", "q"}:
            print("阿洛娜: 老师再见～记得想我哦！")
            break
        if user_text.lower() in {"clear", "reset"}:
            history.clear()
            print("[已清空对话历史]")
            continue

        messages = build_messages(history, user_text, system_prompt)
        try:
            reply, elapsed = generate_reply(
                model,
                tokenizer,
                messages,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                do_sample=do_sample,
                enable_thinking=enable_thinking,
            )
        except Exception as e:
            logger.error("生成失败: %s", e)
            print(f"[错误] {e}")
            continue

        print(f"阿洛娜: {reply}")
        print(f"[响应时间] {elapsed:.3f}s\n")
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": reply})


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="阿洛娜 LoRA 交互式推理")
    parser.add_argument("--config", type=str, default=str(DEFAULT_CONFIG))
    parser.add_argument("--adapter", type=str, default=None, help="LoRA 适配器目录")
    parser.add_argument("--model", type=str, default=None, help="基座模型路径")
    parser.add_argument("--max-new-tokens", type=int, default=None)
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--top-p", type=float, default=None)
    parser.add_argument(
        "--prompt",
        type=str,
        default=None,
        help="非交互：单条用户输入后退出",
    )
    args = parser.parse_args()

    logger = setup_logger()
    cfg = load_config(Path(args.config).resolve())
    model_cfg = cfg["model"]
    infer_cfg = dict(cfg.get("inference", {}))

    if args.adapter:
        infer_cfg["adapter_path"] = args.adapter
    if args.max_new_tokens is not None:
        infer_cfg["max_new_tokens"] = args.max_new_tokens
    if args.temperature is not None:
        infer_cfg["temperature"] = args.temperature
    if args.top_p is not None:
        infer_cfg["top_p"] = args.top_p

    model_path = resolve_path(args.model or model_cfg["name_or_path"])
    model_name = str(model_path) if model_path.exists() else (args.model or model_cfg["name_or_path"])
    adapter_path = resolve_path(infer_cfg["adapter_path"])
    enable_thinking = bool(model_cfg.get("enable_thinking", False))
    max_seq_length = int(model_cfg.get("max_seq_length", 2048))

    from unsloth import FastLanguageModel

    load_in_4bit = bool(model_cfg.get("load_in_4bit", True))
    adapter_config = adapter_path / "adapter_config.json"

    if adapter_path.exists() and adapter_config.is_file():
        # Unsloth 可直接从适配器目录加载（会读取其中的基座路径）
        logger.info("正在加载微调模型（适配器）: %s", adapter_path)
        try:
            model, tokenizer = FastLanguageModel.from_pretrained(
                model_name=str(adapter_path),
                max_seq_length=max_seq_length,
                dtype=None,
                load_in_4bit=load_in_4bit,
            )
            logger.info("LoRA 适配器加载成功！")
        except Exception as e:
            logger.warning("直接加载适配器失败 (%s)，改为基座+PeftModel", e)
            logger.info("正在加载基座模型: %s", model_name)
            model, tokenizer = FastLanguageModel.from_pretrained(
                model_name=model_name,
                max_seq_length=max_seq_length,
                dtype=None,
                load_in_4bit=load_in_4bit,
            )
            from peft import PeftModel

            model = PeftModel.from_pretrained(model, str(adapter_path))
            logger.info("LoRA 加载成功！")
    else:
        logger.info("正在加载基座模型: %s", model_name)
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=model_name,
            max_seq_length=max_seq_length,
            dtype=None,
            load_in_4bit=load_in_4bit,
        )
        if not adapter_path.exists():
            logger.warning(
                "未找到适配器目录 %s，将使用未微调的基座模型",
                adapter_path,
            )

    # 推理模式
    FastLanguageModel.for_inference(model)
    logger.info("模型就绪，开始对话测试")

    if args.prompt:
        messages = build_messages(
            [],
            args.prompt,
            (infer_cfg.get("system_prompt") or "").strip() or None,
        )
        reply, elapsed = generate_reply(
            model,
            tokenizer,
            messages,
            max_new_tokens=int(infer_cfg.get("max_new_tokens", 256)),
            temperature=float(infer_cfg.get("temperature", 0.7)),
            top_p=float(infer_cfg.get("top_p", 0.9)),
            do_sample=bool(infer_cfg.get("do_sample", True)),
            enable_thinking=enable_thinking,
        )
        print(f"老师: {args.prompt}")
        print(f"阿洛娜: {reply}")
        print(f"[响应时间] {elapsed:.3f}s")
        return

    interactive_chat(model, tokenizer, infer_cfg, enable_thinking, logger)


if __name__ == "__main__":
    main()
