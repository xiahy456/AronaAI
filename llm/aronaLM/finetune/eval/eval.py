#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阿洛娜微调模型完整评测：基座 vs LoRA 并排对比。

用法（在 finetune/ 目录下）:
  python eval\\eval.py --config config\\config.yaml
  python eval\\eval.py --no-judge
  python eval\\eval.py --no-multi
  python eval\\eval.py --no-summary
  python eval\\eval.py --adapter outputs\\AronaLM-Generator-V2.0-lora-adapter
  python eval\\eval.py --cases eval\\cases.json --multi-sessions eval\\multi_sessions.json

默认开启 --compare、Judge、8 轮多轮会话、全局 LLM 总结。
推理参数（max_new_tokens / temperature / top_p / do_sample / system_prompt）默认取自 config.yaml 的 inference 段；可用 CLI 覆盖。
默认开启训练集抽样探针（对比金标，辅助判断欠拟合/过拟合），结果并入 LLM 总结。
DeepSeek 配置来自 backend/config.yaml 的 memory.extractor。
显存策略：先跑基座（单轮+训练集探针+多轮）→ 释放 → 再跑 LoRA。
"""

from __future__ import annotations

import argparse
import gc
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

EVAL_DIR = Path(__file__).resolve().parent
FINETUNE_ROOT = EVAL_DIR.parent
REPO_ROOT = FINETUNE_ROOT.parent.parent.parent
DEFAULT_CONFIG = FINETUNE_ROOT / "config" / "config.yaml"
DEFAULT_CASES = EVAL_DIR / "cases.json"
DEFAULT_MULTI = EVAL_DIR / "multi_sessions.json"
DEFAULT_OUTPUT = EVAL_DIR / "reports"
DEFAULT_BACKEND_CONFIG = REPO_ROOT / "backend" / "config.yaml"

# 脚本直接运行时：EVAL_DIR 用于同目录模块，FINETUNE_ROOT 用于 inference
if str(FINETUNE_ROOT) not in sys.path:
    sys.path.insert(0, str(FINETUNE_ROOT))
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

from judge import load_extractor_config  # noqa: E402
from judge import judge_reply  # noqa: E402
from multi_runner import (  # noqa: E402
    build_multi_summary,
    load_multi_sessions,
    merge_multi_sessions,
    run_multi_session,
)
from report import build_summary, print_console_summary, write_reports  # noqa: E402
from rules import check_reply  # noqa: E402
from summarize import summarize_evaluation  # noqa: E402
from train_probe import (  # noqa: E402
    build_train_probe_summary,
    load_train_probe_cases,
    merge_train_probe_results,
)
from inference.inference import (  # noqa: E402
    build_messages,
    generate_reply,
    load_config,
    resolve_path,
)


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("arona_eval")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", "%H:%M:%S")
    )
    logger.addHandler(handler)
    return logger


def load_cases(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"cases 文件应为 JSON 数组: {path}")
    return data


def unload_model(model, tokenizer, logger: logging.Logger) -> None:
    try:
        del model
    except Exception:
        pass
    try:
        del tokenizer
    except Exception:
        pass
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
    except Exception as e:
        logger.warning("释放 CUDA 缓存时出现问题: %s", e)


def load_model_for_eval(
    *,
    model_cfg: Dict[str, Any],
    model_name: str,
    adapter_path: Optional[Path],
    use_adapter: bool,
    logger: logging.Logger,
):
    from unsloth import FastLanguageModel

    max_seq_length = int(model_cfg.get("max_seq_length", 2048))
    load_in_4bit = bool(model_cfg.get("load_in_4bit", True))

    if use_adapter and adapter_path is not None:
        adapter_config = adapter_path / "adapter_config.json"
        if adapter_path.exists() and adapter_config.is_file():
            logger.info("加载微调模型（适配器）: %s", adapter_path)
            try:
                model, tokenizer = FastLanguageModel.from_pretrained(
                    model_name=str(adapter_path),
                    max_seq_length=max_seq_length,
                    dtype=None,
                    load_in_4bit=load_in_4bit,
                )
            except Exception as e:
                logger.warning("直接加载适配器失败 (%s)，改为基座+PeftModel", e)
                model, tokenizer = FastLanguageModel.from_pretrained(
                    model_name=model_name,
                    max_seq_length=max_seq_length,
                    dtype=None,
                    load_in_4bit=load_in_4bit,
                )
                from peft import PeftModel

                model = PeftModel.from_pretrained(model, str(adapter_path))
        else:
            raise FileNotFoundError(f"未找到 LoRA 适配器: {adapter_path}")
    else:
        logger.info("加载基座模型: %s", model_name)
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=model_name,
            max_seq_length=max_seq_length,
            dtype=None,
            load_in_4bit=load_in_4bit,
        )

    FastLanguageModel.for_inference(model)
    return model, tokenizer


def run_cases_on_model(
    model,
    tokenizer,
    cases: List[Dict[str, Any]],
    *,
    system_prompt: Optional[str],
    max_new_tokens: int,
    temperature: float,
    top_p: float,
    do_sample: bool,
    enable_thinking: bool,
    seed: Optional[int],
    logger: logging.Logger,
    label: str,
) -> Dict[str, Dict[str, Any]]:
    if seed is not None:
        try:
            import torch

            torch.manual_seed(seed)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(seed)
        except Exception as e:
            logger.warning("设置 seed 失败: %s", e)

    outputs: Dict[str, Dict[str, Any]] = {}
    total = len(cases)
    for i, case in enumerate(cases, 1):
        case_id = str(case.get("id") or f"case_{i}")
        prompt = str(case.get("prompt") or "")
        history = list(case.get("history") or [])
        messages = build_messages(history, prompt, system_prompt)
        logger.info("[%s] (%d/%d) %s", label, i, total, case_id)
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
            logger.error("[%s] 生成失败 %s: %s", label, case_id, e)
            reply, elapsed = f"[ERROR] {e}", 0.0
        outputs[case_id] = {"reply": reply, "elapsed": elapsed}
    return outputs


def run_multi_on_model(
    model,
    tokenizer,
    sessions: List[Dict[str, Any]],
    *,
    api,
    system_prompt: Optional[str],
    max_new_tokens: int,
    temperature: float,
    top_p: float,
    do_sample: bool,
    enable_thinking: bool,
    logger: logging.Logger,
    label: str,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for i, session in enumerate(sessions, 1):
        logger.info("[%s] 多轮 (%d/%d) %s", label, i, len(sessions), session.get("id"))
        result = run_multi_session(
            model,
            tokenizer,
            session,
            api=api,
            system_prompt=system_prompt,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=top_p,
            do_sample=do_sample,
            enable_thinking=enable_thinking,
            build_messages=build_messages,
            generate_reply=generate_reply,
            label=label,
        )
        out.append(result)
    return out


def merge_results(
    cases: List[Dict[str, Any]],
    base_out: Dict[str, Dict[str, Any]],
    lora_out: Dict[str, Dict[str, Any]],
    *,
    run_judge: bool,
    judge_api,
    logger: logging.Logger,
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for case in cases:
        case_id = str(case.get("id"))
        expect = case.get("expect") or {}
        prompt = str(case.get("prompt") or "")
        history = list(case.get("history") or [])
        category = str(case.get("category") or "")

        base_reply = (base_out.get(case_id) or {}).get("reply", "")
        lora_reply = (lora_out.get(case_id) or {}).get("reply", "")
        base_elapsed = (base_out.get(case_id) or {}).get("elapsed")
        lora_elapsed = (lora_out.get(case_id) or {}).get("elapsed")

        base_rule = check_reply(base_reply, expect)
        lora_rule = check_reply(lora_reply, expect)

        base_judge = None
        lora_judge = None
        if run_judge and judge_api is not None:
            logger.info("Judge: %s (base)", case_id)
            base_judge = judge_reply(
                judge_api,
                prompt=prompt,
                reply=base_reply,
                history=history,
                category=category,
            )
            logger.info("Judge: %s (lora)", case_id)
            lora_judge = judge_reply(
                judge_api,
                prompt=prompt,
                reply=lora_reply,
                history=history,
                category=category,
            )

        delta_rule = round(lora_rule.score - base_rule.score, 2)
        delta_judge = None
        if (
            base_judge
            and lora_judge
            and not base_judge.error
            and not lora_judge.error
            and base_judge.overall
            and lora_judge.overall
        ):
            delta_judge = round(lora_judge.overall - base_judge.overall, 2)

        results.append(
            {
                "id": case_id,
                "category": category,
                "prompt": prompt,
                "history": history,
                "base_reply": base_reply,
                "lora_reply": lora_reply,
                "base_elapsed": base_elapsed,
                "lora_elapsed": lora_elapsed,
                "base_rule": base_rule.to_dict(),
                "lora_rule": lora_rule.to_dict(),
                "delta_rule": delta_rule,
                "base_judge": base_judge.to_dict() if base_judge else None,
                "lora_judge": lora_judge.to_dict() if lora_judge else None,
                "delta_judge": delta_judge,
            }
        )
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="阿洛娜微调模型完整评测（Base vs LoRA）")
    parser.add_argument("--config", type=str, default=str(DEFAULT_CONFIG))
    parser.add_argument("--cases", type=str, default=str(DEFAULT_CASES))
    parser.add_argument("--multi-sessions", type=str, default=str(DEFAULT_MULTI))
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT))
    parser.add_argument("--adapter", type=str, default=None, help="LoRA 适配器目录")
    parser.add_argument("--model", type=str, default=None, help="基座模型路径")
    parser.add_argument(
        "--backend-config",
        type=str,
        default=str(DEFAULT_BACKEND_CONFIG),
        help="backend/config.yaml（读取 memory.extractor）",
    )
    parser.add_argument("--compare", action="store_true", default=True, help="基座 vs LoRA（默认开）")
    parser.add_argument("--no-compare", action="store_true", help="只测 LoRA")
    parser.add_argument("--judge", action="store_true", default=True, help="启用 DeepSeek Judge（默认开）")
    parser.add_argument("--no-judge", action="store_true", help="跳过单轮 LLM Judge")
    parser.add_argument("--multi", action="store_true", default=True, help="启用 8 轮多轮评测（默认开）")
    parser.add_argument("--no-multi", action="store_true", help="跳过多轮会话")
    parser.add_argument(
        "--train-probe",
        action="store_true",
        default=True,
        help="启用训练集抽样探针（默认开）",
    )
    parser.add_argument("--no-train-probe", action="store_true", help="跳过训练集探针")
    parser.add_argument(
        "--train-file",
        type=str,
        default=None,
        help="训练集 JSONL；默认用 config.yaml data.train_file",
    )
    parser.add_argument(
        "--train-probe-n",
        type=int,
        default=24,
        help="训练集抽样条数（默认 24）",
    )
    parser.add_argument("--summary", action="store_true", default=True, help="启用全局 LLM 总结（默认开）")
    parser.add_argument("--no-summary", action="store_true", help="跳过全局总结")
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=None,
        help="覆盖 config.yaml inference.max_new_tokens；默认用配置文件",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="覆盖 config.yaml inference.temperature；默认用配置文件",
    )
    parser.add_argument(
        "--top-p",
        type=float,
        default=None,
        help="覆盖 config.yaml inference.top_p；默认用配置文件",
    )
    parser.add_argument("--seed", type=int, default=3407)
    parser.add_argument("--limit", type=int, default=None, help="只跑前 N 条单轮用例（调试）")
    parser.add_argument("--multi-limit", type=int, default=None, help="只跑前 N 个多轮会话（调试）")
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    args = parse_args()
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

    compare = bool(args.compare) and not bool(args.no_compare)
    run_judge = bool(args.judge) and not bool(args.no_judge)
    run_multi = bool(args.multi) and not bool(args.no_multi)
    run_train_probe = bool(args.train_probe) and not bool(args.no_train_probe)
    run_summary = bool(args.summary) and not bool(args.no_summary)

    model_path = resolve_path(args.model or model_cfg["name_or_path"])
    model_name = str(model_path) if model_path.exists() else (args.model or model_cfg["name_or_path"])
    adapter_path = resolve_path(infer_cfg["adapter_path"])
    enable_thinking = bool(model_cfg.get("enable_thinking", False))
    system_prompt = (infer_cfg.get("system_prompt") or "").strip() or None

    cases = load_cases(Path(args.cases).resolve())
    if args.limit is not None:
        cases = cases[: max(0, int(args.limit))]
    logger.info("加载单轮用例 %d 条: %s", len(cases), args.cases)

    multi_sessions: List[Dict[str, Any]] = []
    if run_multi:
        multi_path = Path(args.multi_sessions).resolve()
        if not multi_path.is_file():
            logger.warning("未找到多轮配置 %s，跳过多轮", multi_path)
            run_multi = False
        else:
            multi_sessions = load_multi_sessions(multi_path)
            if args.multi_limit is not None:
                multi_sessions = multi_sessions[: max(0, int(args.multi_limit))]
            logger.info("加载多轮会话 %d 个: %s", len(multi_sessions), multi_path)

    train_probe_cases: List[Dict[str, Any]] = []
    if run_train_probe:
        train_rel = args.train_file or (cfg.get("data") or {}).get("train_file")
        if not train_rel:
            logger.warning("未配置 data.train_file，跳过训练集探针")
            run_train_probe = False
        else:
            train_path = resolve_path(str(train_rel))
            if not train_path.is_file():
                logger.warning("未找到训练集 %s，跳过训练集探针", train_path)
                run_train_probe = False
            else:
                try:
                    train_probe_cases = load_train_probe_cases(
                        train_path,
                        n=int(args.train_probe_n),
                        seed=int(args.seed),
                    )
                except Exception as e:
                    logger.warning("加载训练集探针失败: %s", e)
                    run_train_probe = False

    # API：Judge / 追问生成 / 总结共用
    api = None
    need_api = run_judge or run_multi or run_summary
    if need_api:
        backend_cfg_path = Path(args.backend_config).resolve()
        if not backend_cfg_path.is_file():
            logger.warning("未找到 backend 配置 %s，依赖 API 的功能将降级", backend_cfg_path)
        else:
            api = load_extractor_config(backend_cfg_path)
            if not api.enabled:
                logger.warning("memory.extractor.api_key 无效，依赖 API 的功能将降级")
                api = None
            else:
                logger.info("DeepSeek API: %s model=%s", api.base_url, api.model)

    if run_judge and api is None:
        logger.warning("跳过单轮 Judge（无可用 API）")
        run_judge = False
    if run_summary and api is None:
        logger.warning("跳过全局总结（无可用 API）")
        run_summary = False

    gen_common = dict(
        system_prompt=system_prompt,
        max_new_tokens=int(infer_cfg.get("max_new_tokens", 128)),
        temperature=float(infer_cfg.get("temperature", 0.7)),
        top_p=float(infer_cfg.get("top_p", 0.85)),
        do_sample=bool(infer_cfg.get("do_sample", True)),
        enable_thinking=enable_thinking,
    )
    logger.info(
        "推理参数: max_new_tokens=%s temperature=%s top_p=%s do_sample=%s",
        gen_common["max_new_tokens"],
        gen_common["temperature"],
        gen_common["top_p"],
        gen_common["do_sample"],
    )

    t0 = time.perf_counter()
    base_out: Dict[str, Dict[str, Any]] = {}
    lora_out: Dict[str, Dict[str, Any]] = {}
    base_train_out: Dict[str, Dict[str, Any]] = {}
    lora_train_out: Dict[str, Dict[str, Any]] = {}
    base_multi: List[Dict[str, Any]] = []
    lora_multi: List[Dict[str, Any]] = []

    if compare:
        model, tokenizer = load_model_for_eval(
            model_cfg=model_cfg,
            model_name=model_name,
            adapter_path=adapter_path,
            use_adapter=False,
            logger=logger,
        )
        base_out = run_cases_on_model(
            model,
            tokenizer,
            cases,
            seed=args.seed,
            logger=logger,
            label="base",
            **gen_common,
        )
        if run_train_probe and train_probe_cases:
            base_train_out = run_cases_on_model(
                model,
                tokenizer,
                train_probe_cases,
                seed=args.seed,
                logger=logger,
                label="base-train",
                **gen_common,
            )
        if run_multi and multi_sessions:
            base_multi = run_multi_on_model(
                model,
                tokenizer,
                multi_sessions,
                api=api,
                logger=logger,
                label="base",
                **gen_common,
            )
        unload_model(model, tokenizer, logger)
        model = tokenizer = None

    model, tokenizer = load_model_for_eval(
        model_cfg=model_cfg,
        model_name=model_name,
        adapter_path=adapter_path,
        use_adapter=True,
        logger=logger,
    )
    lora_out = run_cases_on_model(
        model,
        tokenizer,
        cases,
        seed=args.seed,
        logger=logger,
        label="lora",
        **gen_common,
    )
    if run_train_probe and train_probe_cases:
        lora_train_out = run_cases_on_model(
            model,
            tokenizer,
            train_probe_cases,
            seed=args.seed,
            logger=logger,
            label="lora-train",
            **gen_common,
        )
    if run_multi and multi_sessions:
        lora_multi = run_multi_on_model(
            model,
            tokenizer,
            multi_sessions,
            api=api,
            logger=logger,
            label="lora",
            **gen_common,
        )
    unload_model(model, tokenizer, logger)

    if not compare:
        base_out = {
            cid: {"reply": "", "elapsed": 0.0}
            for cid in (c.get("id") for c in cases)
        }
        if run_train_probe and train_probe_cases:
            base_train_out = {
                cid: {"reply": "", "elapsed": 0.0}
                for cid in (c.get("id") for c in train_probe_cases)
            }
        # 无基座多轮时用空结构占位，merge 仍能出 LoRA 侧
        if run_multi and lora_multi and not base_multi:
            base_multi = []
            for s in lora_multi:
                base_multi.append(
                    {
                        "id": s.get("id"),
                        "category": s.get("category"),
                        "goal": s.get("goal"),
                        "opening": s.get("opening"),
                        "agenda": s.get("agenda"),
                        "turns": [],
                        "rule_avg": None,
                        "warnings": [],
                        "n_off_topic": 0,
                        "label": "base",
                    }
                )

    results = merge_results(
        cases,
        base_out,
        lora_out,
        run_judge=run_judge,
        judge_api=api,
        logger=logger,
    )
    summary = build_summary(results)

    train_probe_results: List[Dict[str, Any]] = []
    train_probe_summary = None
    if run_train_probe and train_probe_cases:
        train_probe_results = merge_train_probe_results(
            train_probe_cases,
            base_train_out,
            lora_train_out,
        )
        train_probe_summary = build_train_probe_summary(train_probe_results)

    multi_merged: List[Dict[str, Any]] = []
    multi_summary = None
    if run_multi and (base_multi or lora_multi):
        # 若只有一侧，补齐
        if base_multi and not lora_multi:
            lora_multi = [
                {
                    "id": s.get("id"),
                    "category": s.get("category"),
                    "goal": s.get("goal"),
                    "opening": s.get("opening"),
                    "agenda": s.get("agenda"),
                    "turns": [],
                    "rule_avg": None,
                    "warnings": [],
                    "n_off_topic": 0,
                    "label": "lora",
                }
                for s in base_multi
            ]
        multi_merged = merge_multi_sessions(base_multi, lora_multi)
        multi_summary = build_multi_summary(multi_merged)

    llm_summary = None
    if run_summary and api is not None:
        logger.info("调用 DeepSeek 生成全局总结评估…")
        llm_summary = summarize_evaluation(
            api,
            finetune_cfg=cfg,
            single_summary=summary,
            single_results=results,
            multi_summary=multi_summary,
            multi_merged=multi_merged,
            train_probe_summary=train_probe_summary,
            train_probe_results=train_probe_results,
        )

    elapsed_total = time.perf_counter() - t0
    summary["elapsed_sec"] = round(elapsed_total, 2)

    print_console_summary(
        results,
        summary,
        multi_merged=multi_merged,
        multi_summary=multi_summary,
        train_probe_results=train_probe_results,
        train_probe_summary=train_probe_summary,
        llm_summary=llm_summary,
    )

    meta = {
        "config": str(Path(args.config).resolve()),
        "adapter": str(adapter_path),
        "model": model_name,
        "compare": compare,
        "judge": run_judge,
        "multi": run_multi,
        "train_probe": run_train_probe,
        "train_probe_n": len(train_probe_cases) if run_train_probe else 0,
        "summary": run_summary,
        "temperature": gen_common["temperature"],
        "seed": args.seed,
        "cases_file": str(Path(args.cases).resolve()),
        "multi_sessions_file": str(Path(args.multi_sessions).resolve()) if run_multi else None,
        "elapsed_sec": summary["elapsed_sec"],
    }
    paths = write_reports(
        results,
        summary,
        Path(args.output_dir).resolve(),
        meta=meta,
        multi_merged=multi_merged,
        multi_summary=multi_summary,
        train_probe_results=train_probe_results,
        train_probe_summary=train_probe_summary,
        llm_summary=llm_summary,
    )
    logger.info("报告已写入: %s", paths["json"])
    logger.info("报告已写入: %s", paths["md"])


if __name__ == "__main__":
    main()
