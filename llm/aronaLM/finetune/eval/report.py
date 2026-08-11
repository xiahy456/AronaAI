# -*- coding: utf-8 -*-
"""评测报告：控制台摘要 + JSON / Markdown。"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def _avg(nums: List[float]) -> Optional[float]:
    if not nums:
        return None
    return sum(nums) / len(nums)


def build_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    base_rules: List[float] = []
    lora_rules: List[float] = []
    base_judges: List[float] = []
    lora_judges: List[float] = []
    by_cat: Dict[str, Dict[str, List[float]]] = defaultdict(
        lambda: {
            "base_rule": [],
            "lora_rule": [],
            "base_judge": [],
            "lora_judge": [],
        }
    )
    base_fail_count = 0
    lora_fail_count = 0

    for r in results:
        cat = r.get("category") or "unknown"
        br = r.get("base_rule") or {}
        lr = r.get("lora_rule") or {}
        bj = r.get("base_judge") or {}
        lj = r.get("lora_judge") or {}

        if br.get("score") is not None:
            base_rules.append(float(br["score"]))
            by_cat[cat]["base_rule"].append(float(br["score"]))
            base_fail_count += len(br.get("fails") or [])
        if lr.get("score") is not None:
            lora_rules.append(float(lr["score"]))
            by_cat[cat]["lora_rule"].append(float(lr["score"]))
            lora_fail_count += len(lr.get("fails") or [])

        if bj and bj.get("overall") and not bj.get("error"):
            base_judges.append(float(bj["overall"]))
            by_cat[cat]["base_judge"].append(float(bj["overall"]))
        if lj and lj.get("overall") and not lj.get("error"):
            lora_judges.append(float(lj["overall"]))
            by_cat[cat]["lora_judge"].append(float(lj["overall"]))

    cat_summary: Dict[str, Any] = {}
    for cat, buckets in sorted(by_cat.items()):
        br_avg = _avg(buckets["base_rule"])
        lr_avg = _avg(buckets["lora_rule"])
        bj_avg = _avg(buckets["base_judge"])
        lj_avg = _avg(buckets["lora_judge"])
        cat_summary[cat] = {
            "base_rule_avg": round(br_avg, 2) if br_avg is not None else None,
            "lora_rule_avg": round(lr_avg, 2) if lr_avg is not None else None,
            "delta_rule": round(lr_avg - br_avg, 2)
            if br_avg is not None and lr_avg is not None
            else None,
            "base_judge_avg": round(bj_avg, 2) if bj_avg is not None else None,
            "lora_judge_avg": round(lj_avg, 2) if lj_avg is not None else None,
            "delta_judge": round(lj_avg - bj_avg, 2)
            if bj_avg is not None and lj_avg is not None
            else None,
            "n": max(len(buckets["base_rule"]), len(buckets["lora_rule"])),
        }

    br_avg = _avg(base_rules)
    lr_avg = _avg(lora_rules)
    bj_avg = _avg(base_judges)
    lj_avg = _avg(lora_judges)

    return {
        "n_cases": len(results),
        "base_rule_avg": round(br_avg, 2) if br_avg is not None else None,
        "lora_rule_avg": round(lr_avg, 2) if lr_avg is not None else None,
        "delta_rule": round(lr_avg - br_avg, 2)
        if br_avg is not None and lr_avg is not None
        else None,
        "base_judge_avg": round(bj_avg, 2) if bj_avg is not None else None,
        "lora_judge_avg": round(lj_avg, 2) if lj_avg is not None else None,
        "delta_judge": round(lj_avg - bj_avg, 2)
        if bj_avg is not None and lj_avg is not None
        else None,
        "base_fail_count": base_fail_count,
        "lora_fail_count": lora_fail_count,
        "by_category": cat_summary,
    }


def print_console_summary(
    results: List[Dict[str, Any]],
    summary: Dict[str, Any],
    *,
    multi_merged: Optional[List[Dict[str, Any]]] = None,
    multi_summary: Optional[Dict[str, Any]] = None,
    train_probe_results: Optional[List[Dict[str, Any]]] = None,
    train_probe_summary: Optional[Dict[str, Any]] = None,
    llm_summary: Optional[Dict[str, Any]] = None,
) -> None:
    print()
    print("=" * 72)
    print("  阿洛娜微调评测摘要（Base vs LoRA）")
    print("=" * 72)
    print(
        f"用例数: {summary.get('n_cases')}  |  "
        f"规则均分 Base {summary.get('base_rule_avg')} → LoRA {summary.get('lora_rule_avg')} "
        f"(Δ {summary.get('delta_rule')})"
    )
    if summary.get("base_judge_avg") is not None or summary.get("lora_judge_avg") is not None:
        print(
            f"Judge均分: Base {summary.get('base_judge_avg')} → LoRA {summary.get('lora_judge_avg')} "
            f"(Δ {summary.get('delta_judge')})"
        )
    print(
        f"规则 fail 计数: Base {summary.get('base_fail_count')} / "
        f"LoRA {summary.get('lora_fail_count')}"
    )
    if multi_summary:
        print(
            f"多轮会话: {multi_summary.get('n_sessions')} × {multi_summary.get('turns_per_session')} 轮  |  "
            f"规则均分 Base {multi_summary.get('base_rule_avg')} → LoRA {multi_summary.get('lora_rule_avg')} "
            f"(Δ {multi_summary.get('delta_rule')})  |  "
            f"off_topic Base {multi_summary.get('base_off_topic_total')} / "
            f"LoRA {multi_summary.get('lora_off_topic_total')}"
        )
    if train_probe_summary and train_probe_summary.get("n"):
        print(
            f"训练集探针: n={train_probe_summary.get('n')}  |  "
            f"金标相似 Base {train_probe_summary.get('base_gold_sim_avg')} → "
            f"LoRA {train_probe_summary.get('lora_gold_sim_avg')} "
            f"(Δ {train_probe_summary.get('delta_gold_sim')})  |  "
            f"exact LoRA {train_probe_summary.get('lora_exact_rate')}"
        )
    print()
    print(f"{'ID':<22} {'Cat':<16} {'B.rule':>7} {'L.rule':>7} {'Δr':>6} "
          f"{'B.j':>5} {'L.j':>5} {'Δj':>5}")
    print("-" * 72)
    for r in results:
        br = (r.get("base_rule") or {}).get("score")
        lr = (r.get("lora_rule") or {}).get("score")
        bj = (r.get("base_judge") or {}).get("overall")
        lj = (r.get("lora_judge") or {}).get("overall")
        dr = r.get("delta_rule")
        dj = r.get("delta_judge")
        print(
            f"{str(r.get('id', '')):<22} {str(r.get('category', '')):<16} "
            f"{_fmt(br):>7} {_fmt(lr):>7} {_fmt(dr):>6} "
            f"{_fmt(bj):>5} {_fmt(lj):>5} {_fmt(dj):>5}"
        )
    print("-" * 72)
    print("按类别：")
    for cat, info in (summary.get("by_category") or {}).items():
        print(
            f"  [{cat}] n={info.get('n')}  "
            f"rule Δ={info.get('delta_rule')}  "
            f"judge Δ={info.get('delta_judge')}"
        )
    if multi_merged:
        print("-" * 72)
        print("多轮会话：")
        for m in multi_merged:
            print(
                f"  [{m.get('id')}] rule Base {m.get('base_rule_avg')} → "
                f"LoRA {m.get('lora_rule_avg')} (Δ {m.get('delta_rule')})  "
                f"off_topic {m.get('base_n_off_topic')}/{m.get('lora_n_off_topic')}"
            )
    if llm_summary and not llm_summary.get("error"):
        print("-" * 72)
        print(f"LLM总结: {llm_summary.get('overall_verdict')}")
        if llm_summary.get("fit_diagnosis"):
            print(f"  拟合诊断: {llm_summary.get('fit_diagnosis')} — {llm_summary.get('fit_analysis')}")
        scores = llm_summary.get("scores") or {}
        if scores:
            print(
                f"  scores character={scores.get('character')} "
                f"multi_turn={scores.get('multi_turn')} "
                f"stability={scores.get('stability')} "
                f"train_fit={scores.get('train_fit')} "
                f"overall={scores.get('overall')}"
            )
    elif llm_summary and llm_summary.get("error"):
        print(f"LLM总结失败: {llm_summary.get('error')}")
    print("=" * 72)


def _fmt(v: Any) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.1f}"
    return str(v)


def _md_escape(s: str) -> str:
    return (s or "").replace("|", "\\|").replace("\n", " ")


def write_reports(
    results: List[Dict[str, Any]],
    summary: Dict[str, Any],
    output_dir: Path,
    *,
    meta: Optional[Dict[str, Any]] = None,
    multi_merged: Optional[List[Dict[str, Any]]] = None,
    multi_summary: Optional[Dict[str, Any]] = None,
    train_probe_results: Optional[List[Dict[str, Any]]] = None,
    train_probe_summary: Optional[Dict[str, Any]] = None,
    llm_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"eval_{stamp}.json"
    md_path = output_dir / f"eval_{stamp}.md"

    payload = {
        "meta": meta or {},
        "summary": summary,
        "results": results,
        "multi_summary": multi_summary,
        "multi_sessions": multi_merged or [],
        "train_probe_summary": train_probe_summary,
        "train_probe_results": train_probe_results or [],
        "llm_summary": llm_summary,
    }
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    lines: List[str] = [
        f"# 阿洛娜微调评测报告 ({stamp})",
        "",
        "## 摘要",
        "",
        f"- 用例数: {summary.get('n_cases')}",
        f"- 规则均分: Base `{summary.get('base_rule_avg')}` → LoRA `{summary.get('lora_rule_avg')}` "
        f"(Δ `{summary.get('delta_rule')}`)",
        f"- Judge均分: Base `{summary.get('base_judge_avg')}` → LoRA `{summary.get('lora_judge_avg')}` "
        f"(Δ `{summary.get('delta_judge')}`)",
        f"- 规则 fail: Base `{summary.get('base_fail_count')}` / LoRA `{summary.get('lora_fail_count')}`",
    ]
    if multi_summary:
        lines.extend(
            [
                f"- 多轮会话: `{multi_summary.get('n_sessions')}` × "
                f"`{multi_summary.get('turns_per_session')}` 轮",
                f"- 多轮规则均分: Base `{multi_summary.get('base_rule_avg')}` → "
                f"LoRA `{multi_summary.get('lora_rule_avg')}` "
                f"(Δ `{multi_summary.get('delta_rule')}`)",
                f"- 多轮 off_topic: Base `{multi_summary.get('base_off_topic_total')}` / "
                f"LoRA `{multi_summary.get('lora_off_topic_total')}`",
            ]
        )
    if train_probe_summary and train_probe_summary.get("n"):
        lines.extend(
            [
                f"- 训练集探针: n=`{train_probe_summary.get('n')}`",
                f"- 金标相似: Base `{train_probe_summary.get('base_gold_sim_avg')}` → "
                f"LoRA `{train_probe_summary.get('lora_gold_sim_avg')}` "
                f"(Δ `{train_probe_summary.get('delta_gold_sim')}`)",
                f"- 完全匹配率: Base `{train_probe_summary.get('base_exact_rate')}` / "
                f"LoRA `{train_probe_summary.get('lora_exact_rate')}`",
            ]
        )
    lines.extend(
        [
            "",
            "### 按类别",
            "",
            "| Category | n | Base rule | LoRA rule | Δ rule | Base judge | LoRA judge | Δ judge |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for cat, info in (summary.get("by_category") or {}).items():
        lines.append(
            f"| {cat} | {info.get('n')} | {info.get('base_rule_avg')} | {info.get('lora_rule_avg')} | "
            f"{info.get('delta_rule')} | {info.get('base_judge_avg')} | {info.get('lora_judge_avg')} | "
            f"{info.get('delta_judge')} |"
        )

    if llm_summary:
        lines.extend(["", "## LLM 总结评估", ""])
        if llm_summary.get("error"):
            lines.append(f"- 总结失败: `{llm_summary.get('error')}`")
        else:
            lines.append(f"**结论:** {llm_summary.get('overall_verdict')}")
            lines.append("")
            if llm_summary.get("fit_diagnosis"):
                lines.append(
                    f"**拟合诊断:** `{llm_summary.get('fit_diagnosis')}` — "
                    f"{llm_summary.get('fit_analysis')}"
                )
                lines.append("")
            lines.append(f"**LoRA vs Base:** {llm_summary.get('lora_vs_base')}")
            lines.append("")
            lines.append(f"**多轮连贯性:** {llm_summary.get('multi_turn_coherence')}")
            lines.append("")
            scores = llm_summary.get("scores") or {}
            lines.append(
                f"**Scores:** character=`{scores.get('character')}` "
                f"multi_turn=`{scores.get('multi_turn')}` "
                f"stability=`{scores.get('stability')}` "
                f"train_fit=`{scores.get('train_fit')}` "
                f"overall=`{scores.get('overall')}`"
            )
            lines.append("")
            lines.append("### 优点")
            for s in llm_summary.get("strengths") or []:
                lines.append(f"- {s}")
            lines.append("")
            lines.append("### 不足")
            for s in llm_summary.get("weaknesses") or []:
                lines.append(f"- {s}")
            lines.append("")
            lines.append("### 风险")
            for s in llm_summary.get("risks") or []:
                lines.append(f"- {s}")
            lines.append("")
            lines.append("### 建议")
            for s in llm_summary.get("recommendations") or []:
                lines.append(f"- {s}")

    lines.extend(["", "## 单轮明细", ""])
    for r in results:
        lines.append(f"### `{r.get('id')}` ({r.get('category')})")
        lines.append("")
        lines.append(f"**Prompt:** {_md_escape(str(r.get('prompt', '')))}")
        lines.append("")
        lines.append("| | Base | LoRA | Δ |")
        lines.append("|---|---|---|---|")
        lines.append(
            f"| 回复 | {_md_escape(str(r.get('base_reply', '')))} | "
            f"{_md_escape(str(r.get('lora_reply', '')))} | |"
        )
        br = (r.get("base_rule") or {}).get("score")
        lr = (r.get("lora_rule") or {}).get("score")
        lines.append(f"| 规则分 | {br} | {lr} | {r.get('delta_rule')} |")
        bj = (r.get("base_judge") or {}).get("overall")
        lj = (r.get("lora_judge") or {}).get("overall")
        lines.append(f"| Judge | {bj} | {lj} | {r.get('delta_judge')} |")
        lines.append("")
        bf = (r.get("base_rule") or {}).get("fails") or []
        lf = (r.get("lora_rule") or {}).get("fails") or []
        if bf or lf:
            lines.append(f"- Base fails: `{bf}`")
            lines.append(f"- LoRA fails: `{lf}`")
            lines.append("")
        bj_reason = (r.get("base_judge") or {}).get("reason")
        lj_reason = (r.get("lora_judge") or {}).get("reason")
        if bj_reason or lj_reason:
            lines.append(f"- Base judge reason: {bj_reason or '-'}")
            lines.append(f"- LoRA judge reason: {lj_reason or '-'}")
            lines.append("")

    if train_probe_results:
        lines.extend(["", "## 训练集探针（欠拟合/过拟合）", ""])
        if train_probe_summary:
            lines.append(
                f"- 金标相似均分: Base `{train_probe_summary.get('base_gold_sim_avg')}` → "
                f"LoRA `{train_probe_summary.get('lora_gold_sim_avg')}` "
                f"(Δ `{train_probe_summary.get('delta_gold_sim')}`)"
            )
            lines.append(
                f"- exact rate: Base `{train_probe_summary.get('base_exact_rate')}` / "
                f"LoRA `{train_probe_summary.get('lora_exact_rate')}`"
            )
            lines.append("")
        lines.append("| ID | Prompt | Gold | Base | LoRA | B.sim | L.sim | Δsim |")
        lines.append("|---|---|---|---|---|---:|---:|---:|")
        for r in train_probe_results:
            lines.append(
                f"| `{r.get('id')}` | {_md_escape(str(r.get('prompt') or ''))} | "
                f"{_md_escape(str(r.get('gold') or ''))} | "
                f"{_md_escape(str(r.get('base_reply') or ''))} | "
                f"{_md_escape(str(r.get('lora_reply') or ''))} | "
                f"{r.get('base_gold_sim')} | {r.get('lora_gold_sim')} | {r.get('delta_gold_sim')} |"
            )
        lines.append("")

    if multi_merged:
        lines.extend(["", "## 多轮会话明细", ""])
        for m in multi_merged:
            lines.append(f"### `{m.get('id')}`")
            lines.append("")
            lines.append(f"**Goal:** {_md_escape(str(m.get('goal') or ''))}")
            lines.append("")
            lines.append(
                f"- 规则均分: Base `{m.get('base_rule_avg')}` → LoRA `{m.get('lora_rule_avg')}` "
                f"(Δ `{m.get('delta_rule')}`)"
            )
            lines.append(
                f"- off_topic: Base `{m.get('base_n_off_topic')}` / LoRA `{m.get('lora_n_off_topic')}`"
            )
            lines.append("")
            lines.append("| Turn | Agenda | Base 老师 | Base 阿洛娜 | LoRA 老师 | LoRA 阿洛娜 | B.rule | L.rule |")
            lines.append("|---:|---|---|---|---|---|---:|---:|")
            for t in m.get("turns") or []:
                brs = (t.get("base_rule") or {}).get("score")
                lrs = (t.get("lora_rule") or {}).get("score")
                lines.append(
                    f"| {t.get('turn')} | {_md_escape(str(t.get('agenda') or ''))} | "
                    f"{_md_escape(str(t.get('base_user') or ''))} | "
                    f"{_md_escape(str(t.get('base_assistant') or ''))} | "
                    f"{_md_escape(str(t.get('lora_user') or ''))} | "
                    f"{_md_escape(str(t.get('lora_assistant') or ''))} | "
                    f"{brs} | {lrs} |"
                )
            lines.append("")

    with md_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return {"json": json_path, "md": md_path}
