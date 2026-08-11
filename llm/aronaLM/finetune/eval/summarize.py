# -*- coding: utf-8 -*-
"""全局 LLM 总结评估：注入 finetune config + 全部测试结果。"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any, Dict, List, Optional

from judge import ExtractorApiConfig, chat_completion_json

logger = logging.getLogger("arona_eval.summarize")

SUMMARY_SYSTEM = """你是阿洛娜（Arona）微调模型的评测总结专家。
根据提供的模型配置与评测数据，输出一份结构化评估。
只输出 JSON，不要其他文字。格式：
{
  "overall_verdict": "一句话结论",
  "lora_vs_base": "Base 与 LoRA 对比结论",
  "fit_diagnosis": "underfit|overfit|good_fit|unclear",
  "fit_analysis": "结合训练集探针与 held-out 表现，说明欠拟合/过拟合判断依据",
  "strengths": ["优点1", "优点2"],
  "weaknesses": ["不足1", "不足2"],
  "multi_turn_coherence": "多轮对话连贯性与防跑题表现评估",
  "risks": ["风险1"],
  "recommendations": ["针对微调/数据/提示的建议"],
  "scores": {
    "character": 1-5,
    "multi_turn": 1-5,
    "stability": 1-5,
    "train_fit": 1-5,
    "overall": 1-5
  }
}

拟合诊断指引（必须填写 fit_diagnosis / fit_analysis）：
- underfit：训练集探针与金标相似度仍低，且 held-out（单轮/多轮）角色/能力也弱 → 学习不足。
- overfit：训练集探针与金标很接近（甚至复述），但 held-out 泛化明显变差、僵硬背诵或答非所问 → 过拟合。
- good_fit：训练集有合理提升，held-out 也同步变好，风格自然不过度背诵。
- unclear：证据不足或矛盾。
分数：1极差 2较差 3一般 4良好 5优秀。评价要具体，引用明显现象，避免空话。
"""


def _clip_prompt(text: str, limit: int = 600) -> str:
    t = (text or "").strip()
    if len(t) <= limit:
        return t
    return t[: limit - 3] + "..."


def extract_model_config_slice(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """从 finetune config.yaml 抽取与模型相关的片段。"""
    model = dict(cfg.get("model") or {})
    lora = dict(cfg.get("lora") or {})
    training = dict(cfg.get("training") or {})
    inference = dict(cfg.get("inference") or {})
    export = dict(cfg.get("export") or {})

    # 截断 system_prompt，避免总结请求过大
    if "system_prompt" in inference:
        inference = dict(inference)
        inference["system_prompt"] = _clip_prompt(str(inference.get("system_prompt") or ""), 800)

    # 训练只保留关键超参
    train_keys = [
        "output_dir",
        "per_device_train_batch_size",
        "gradient_accumulation_steps",
        "num_train_epochs",
        "learning_rate",
        "warmup_steps",
        "optim",
        "weight_decay",
        "lr_scheduler_type",
        "seed",
        "train_on_responses_only",
        "max_seq_length",
    ]
    training_slim = {k: training[k] for k in train_keys if k in training}

    return {
        "model": model,
        "lora": lora,
        "training": training_slim,
        "inference": {
            k: inference[k]
            for k in (
                "adapter_path",
                "max_new_tokens",
                "temperature",
                "top_p",
                "do_sample",
                "system_prompt",
            )
            if k in inference
        },
        "export": {
            k: export[k]
            for k in ("save_gguf", "quantization_method", "lora_dir", "gguf_dir")
            if k in export
        },
    }


def _collect_fail_freq(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    base_c: Counter = Counter()
    lora_c: Counter = Counter()
    for r in results:
        for f in (r.get("base_rule") or {}).get("fails") or []:
            base_c[str(f)] += 1
        for f in (r.get("lora_rule") or {}).get("fails") or []:
            lora_c[str(f)] += 1
    return {
        "base_top_fails": base_c.most_common(10),
        "lora_top_fails": lora_c.most_common(10),
    }


def _format_multi_for_prompt(multi_merged: List[Dict[str, Any]], max_chars: int = 12000) -> str:
    chunks: List[str] = []
    for m in multi_merged:
        lines = [
            f"### session {m.get('id')} | goal={m.get('goal')}",
            f"rule_avg Base={m.get('base_rule_avg')} LoRA={m.get('lora_rule_avg')} Δ={m.get('delta_rule')}",
            f"off_topic Base={m.get('base_n_off_topic')} LoRA={m.get('lora_n_off_topic')}",
        ]
        for t in m.get("turns") or []:
            lines.append(
                f"T{t.get('turn')} agenda={t.get('agenda')}\n"
                f"  Base老师: {t.get('base_user')}\n"
                f"  Base阿洛娜: {t.get('base_assistant')}\n"
                f"  LoRA老师: {t.get('lora_user')}\n"
                f"  LoRA阿洛娜: {t.get('lora_assistant')}"
            )
        chunks.append("\n".join(lines))
    text = "\n\n".join(chunks)
    if len(text) > max_chars:
        return text[: max_chars - 20] + "\n...[truncated]..."
    return text


def build_summary_user_payload(
    *,
    config_slice: Dict[str, Any],
    single_summary: Dict[str, Any],
    multi_summary: Optional[Dict[str, Any]],
    multi_merged: List[Dict[str, Any]],
    single_results: List[Dict[str, Any]],
    train_probe_summary: Optional[Dict[str, Any]] = None,
    train_probe_results: Optional[List[Dict[str, Any]]] = None,
) -> str:
    import json

    fails = _collect_fail_freq(single_results)
    # 单轮只给精简表，避免超大
    slim_cases = []
    for r in single_results:
        slim_cases.append(
            {
                "id": r.get("id"),
                "category": r.get("category"),
                "prompt": r.get("prompt"),
                "base_reply": r.get("base_reply"),
                "lora_reply": r.get("lora_reply"),
                "base_rule": (r.get("base_rule") or {}).get("score"),
                "lora_rule": (r.get("lora_rule") or {}).get("score"),
                "base_judge": (r.get("base_judge") or {}).get("overall") if r.get("base_judge") else None,
                "lora_judge": (r.get("lora_judge") or {}).get("overall") if r.get("lora_judge") else None,
                "delta_rule": r.get("delta_rule"),
                "delta_judge": r.get("delta_judge"),
            }
        )

    slim_train = []
    for r in train_probe_results or []:
        slim_train.append(
            {
                "id": r.get("id"),
                "prompt": r.get("prompt"),
                "gold": r.get("gold"),
                "base_reply": r.get("base_reply"),
                "lora_reply": r.get("lora_reply"),
                "base_gold_sim": r.get("base_gold_sim"),
                "lora_gold_sim": r.get("lora_gold_sim"),
                "delta_gold_sim": r.get("delta_gold_sim"),
                "base_exact": r.get("base_exact"),
                "lora_exact": r.get("lora_exact"),
                "base_rule": (r.get("base_rule") or {}).get("score"),
                "lora_rule": (r.get("lora_rule") or {}).get("score"),
            }
        )

    payload = {
        "finetune_config": config_slice,
        "single_turn_summary": single_summary,
        "single_turn_fail_freq": fails,
        "single_turn_cases": slim_cases,
        "multi_turn_summary": multi_summary,
        "train_probe_summary": train_probe_summary,
        "train_probe_cases": slim_train,
        "fit_hint": (
            "请重点对比 train_probe（训练集抽样 vs 金标）与 single_turn/multi_turn（held-out）表现，"
            "判断 underfit / overfit / good_fit。"
        ),
    }
    header = json.dumps(payload, ensure_ascii=False, indent=2)
    multi_text = _format_multi_for_prompt(multi_merged)
    return (
        "以下是阿洛娜微调评测的完整材料，请按约定 JSON 输出总结评估。\n\n"
        f"【配置与单轮/训练集探针摘要 JSON】\n{header}\n\n"
        f"【多轮对话明细】\n{multi_text if multi_text.strip() else '（无多轮数据）'}\n"
    )


def summarize_evaluation(
    api: ExtractorApiConfig,
    *,
    finetune_cfg: Dict[str, Any],
    single_summary: Dict[str, Any],
    single_results: List[Dict[str, Any]],
    multi_summary: Optional[Dict[str, Any]] = None,
    multi_merged: Optional[List[Dict[str, Any]]] = None,
    train_probe_summary: Optional[Dict[str, Any]] = None,
    train_probe_results: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """一次 LLM 调用，返回总结 dict（含 error 字段若失败）。"""
    config_slice = extract_model_config_slice(finetune_cfg)
    user = build_summary_user_payload(
        config_slice=config_slice,
        single_summary=single_summary,
        multi_summary=multi_summary,
        multi_merged=multi_merged or [],
        single_results=single_results,
        train_probe_summary=train_probe_summary,
        train_probe_results=train_probe_results,
    )
    # 总结需要更大输出
    parsed, err = chat_completion_json(
        api,
        system=SUMMARY_SYSTEM,
        user=user,
        temperature=0.2,
        max_tokens=2048,
        timeout_sec=max(float(api.timeout_sec), 120.0),
    )
    if err or parsed is None:
        logger.warning("总结评估失败: %s", err)
        return {"error": err or "empty_response"}
    return parsed
