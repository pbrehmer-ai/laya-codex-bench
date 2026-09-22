from __future__ import annotations

import argparse
import json
import math
import os
import platform
import statistics
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .codex_runner import run_codex
from .laya_client import LayaClient
from .metrics import bootstrap_ci, percentile
from .public_cases import PublicCase, load_public_cases


ROOT = Path(__file__).resolve().parents[1]
CHECKPOINTS = ("english", "multilingual", "typed-decisions")


def laya_value_and_confidence(result: dict[str, Any]) -> tuple[str, float]:
    answer = next(iter(result["answers"].values()))
    if answer["type"] == "choice":
        return str(answer["choice"]), float(answer.get("confidence", 0.0))
    if answer["type"] == "noul":
        probability = float(answer["noul"])
        return ("true" if probability >= 0.5 else "false"), max(probability, 1.0 - probability)
    raise ValueError(f"Unsupported public benchmark answer type: {answer['type']}")


def codex_prompt(case: PublicCase) -> str:
    packet = json.dumps(
        {"state": case.state, "question": next(iter(case.questions.values()))},
        ensure_ascii=False,
        sort_keys=True,
    )
    allowed = (
        list(next(iter(case.questions.values()))["criteria"].keys())
        if next(iter(case.questions.values()))["type"] == "choice"
        else ["true", "false"]
    )
    return (
        "Classify the supplied packet directly. Do not use tools, shell commands, skills, "
        "web search, or Laya. Return one JSON object matching the schema. The value must be "
        f"exactly one of {json.dumps(allowed)}.\nPacket:\n{packet}"
    )


def tune_threshold(rows: list[dict[str, Any]], target_accuracy: float) -> dict[str, Any]:
    candidates = sorted({float(row["confidence"]) for row in rows}, reverse=True)
    choices: list[dict[str, Any]] = []
    for threshold in candidates:
        accepted = [row for row in rows if float(row["confidence"]) >= threshold]
        if len(accepted) < 3:
            continue
        accuracy = sum(bool(row["correct"]) for row in accepted) / len(accepted)
        choices.append(
            {
                "threshold": threshold,
                "accepted": len(accepted),
                "coverage": len(accepted) / len(rows),
                "accuracy": accuracy,
            }
        )
    eligible = [choice for choice in choices if choice["accuracy"] >= target_accuracy]
    if not eligible:
        return {
            "threshold": 1.01,
            "accepted": 0,
            "coverage": 0.0,
            "accuracy": None,
            "target_accuracy": target_accuracy,
            "reason": "No development threshold met the target accuracy with at least three cases.",
        }
    best = max(eligible, key=lambda item: (item["coverage"], item["accuracy"], item["threshold"]))
    return {**best, "target_accuracy": target_accuracy, "reason": "selected on development split only"}


def benchmark(args: argparse.Namespace) -> int:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_root = ROOT / "runs" / "raw" / f"cascade-{timestamp}"
    run_root.mkdir(parents=True, exist_ok=True)
    dev_cases, test_cases, provenance = load_public_cases(
        dev_per_suite=args.dev_per_suite,
        test_per_suite=args.test_per_suite,
        seed=args.seed,
    )
    client = LayaClient(ROOT)
    health_before = client.ensure_started()

    dev_rows: list[dict[str, Any]] = []
    for index, case in enumerate(dev_cases, 1):
        print(f"[dev {index}/{len(dev_cases)}] {case.id}", flush=True)
        for checkpoint in CHECKPOINTS:
            result = client.predict(case.state, case.questions, model=checkpoint)
            value, confidence = laya_value_and_confidence(result)
            dev_rows.append(
                {
                    "case_id": case.id,
                    "suite": case.suite,
                    "checkpoint": checkpoint,
                    "expected": case.expected,
                    "value": value,
                    "confidence": confidence,
                    "correct": value == case.expected,
                    "inference_ms": float(result["deployment"]["inference_ms"]),
                }
            )

    suite_checkpoint: dict[str, str] = {}
    dev_scores: dict[str, Any] = {}
    policies: dict[str, Any] = {}
    for suite in sorted({case.suite for case in dev_cases}):
        dev_scores[suite] = {}
        for checkpoint in CHECKPOINTS:
            subset = [
                row for row in dev_rows if row["suite"] == suite and row["checkpoint"] == checkpoint
            ]
            accuracy = sum(row["correct"] for row in subset) / len(subset)
            dev_scores[suite][checkpoint] = {
                "accuracy": accuracy,
                "median_inference_ms": statistics.median(row["inference_ms"] for row in subset),
            }
        selected = max(
            CHECKPOINTS,
            key=lambda checkpoint: (
                dev_scores[suite][checkpoint]["accuracy"],
                -dev_scores[suite][checkpoint]["median_inference_ms"],
            ),
        )
        suite_checkpoint[suite] = selected
        selected_rows = [
            row for row in dev_rows if row["suite"] == suite and row["checkpoint"] == selected
        ]
        policies[suite] = tune_threshold(selected_rows, args.target_accuracy)
        policies[suite]["checkpoint"] = selected

    test_rows: list[dict[str, Any]] = []
    for index, case in enumerate(test_cases, 1):
        checkpoint = suite_checkpoint[case.suite]
        policy = policies[case.suite]
        print(f"[test {index}/{len(test_cases)}] {case.id} ({checkpoint})", flush=True)
        laya_result = client.predict(case.state, case.questions, model=checkpoint)
        laya_value, confidence = laya_value_and_confidence(laya_result)
        accepted = confidence >= float(policy["threshold"])

        codex_outcome = run_codex(
            project_root=ROOT,
            prompt=codex_prompt(case),
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            schema_path=ROOT / "schemas" / "single-decision.schema.json",
            run_dir=run_root / case.id / "codex-baseline",
            ignore_user_config=True,
            ignore_rules=True,
        )
        codex_value = str((codex_outcome.get("final") or {}).get("value", "")).strip().lower()
        usage = codex_outcome.get("usage", {})
        cascade_value = laya_value if accepted else codex_value
        laya_ms = float(laya_result["deployment"]["inference_ms"])
        codex_ms = float(codex_outcome["elapsed_ms"])
        test_rows.append(
            {
                "case_id": case.id,
                "suite": case.suite,
                "source_index": case.source_index,
                "expected": case.expected,
                "checkpoint": checkpoint,
                "threshold": policy["threshold"],
                "laya_value": laya_value,
                "laya_confidence": confidence,
                "laya_correct": laya_value == case.expected,
                "laya_inference_ms": laya_ms,
                "cascade_auto_accepted": accepted,
                "codex_value": codex_value,
                "codex_correct": codex_value == case.expected,
                "codex_success": codex_outcome["exit_code"] == 0 and bool(codex_value),
                "codex_elapsed_ms": codex_ms,
                "codex_input_tokens": int(usage.get("input_tokens", 0)),
                "codex_cached_input_tokens": int(usage.get("cached_input_tokens", 0)),
                "codex_output_tokens": int(usage.get("output_tokens", 0)),
                "codex_reasoning_tokens": int(usage.get("reasoning_output_tokens", 0)),
                "cascade_value": cascade_value,
                "cascade_correct": cascade_value == case.expected,
                "cascade_elapsed_ms": laya_ms if accepted else laya_ms + codex_ms,
                "cascade_codex_tokens": 0
                if accepted
                else int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0)),
            }
        )

    health_after = client.health() or {}
    metadata = {
        "timestamp": timestamp,
        "seed": args.seed,
        "dev_per_suite": args.dev_per_suite,
        "test_per_suite": args.test_per_suite,
        "target_accuracy": args.target_accuracy,
        "codex_model": args.model,
        "reasoning_effort": args.reasoning_effort,
        "codex_version": subprocess.run(
            ["codex", "--version"], capture_output=True, text=True, check=False
        ).stdout.strip(),
        "os": platform.platform(),
        "cpu": platform.processor() or os.environ.get("PROCESSOR_IDENTIFIER", "unknown"),
        "laya_pid_before": health_before.get("pid"),
        "laya_pid_after": health_after.get("pid"),
        "laya_persistent": health_before.get("pid") == health_after.get("pid"),
        "loaded_models": health_after.get("loaded_models", []),
        "provenance": provenance,
        "dev_scores": dev_scores,
        "policies": policies,
    }
    (run_root / "dev-results.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in dev_rows),
        encoding="utf-8",
    )
    (run_root / "test-results.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in test_rows),
        encoding="utf-8",
    )
    (run_root / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report_dir = ROOT / "reports" / f"cascade-{timestamp}"
    write_cascade_report(test_rows, metadata, report_dir)
    print(f"Report: {report_dir}", flush=True)
    return 0


def _condition_summary(rows: list[dict[str, Any]], condition: str) -> dict[str, Any]:
    if condition == "codex":
        correct = [bool(row["codex_correct"]) for row in rows]
        latency = [float(row["codex_elapsed_ms"]) for row in rows]
        tokens = [int(row["codex_input_tokens"]) + int(row["codex_output_tokens"]) for row in rows]
        calls = len(rows)
    elif condition == "laya":
        correct = [bool(row["laya_correct"]) for row in rows]
        latency = [float(row["laya_inference_ms"]) for row in rows]
        tokens = [0 for _ in rows]
        calls = 0
    else:
        correct = [bool(row["cascade_correct"]) for row in rows]
        latency = [float(row["cascade_elapsed_ms"]) for row in rows]
        tokens = [int(row["cascade_codex_tokens"]) for row in rows]
        calls = sum(not bool(row["cascade_auto_accepted"]) for row in rows)
    return {
        "cases": len(rows),
        "correct": sum(correct),
        "accuracy": sum(correct) / len(correct),
        "codex_calls": calls,
        "codex_tokens": sum(tokens),
        "mean_latency_ms": statistics.mean(latency),
        "median_latency_ms": statistics.median(latency),
        "p90_latency_ms": percentile(latency, 0.9),
    }


def write_cascade_report(
    rows: list[dict[str, Any]], metadata: dict[str, Any], output: Path
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    suites = sorted({row["suite"] for row in rows})
    summaries: dict[str, Any] = {}
    for suite in ["overall", *suites]:
        subset = rows if suite == "overall" else [row for row in rows if row["suite"] == suite]
        summaries[suite] = {
            condition: _condition_summary(subset, condition)
            for condition in ("codex", "laya", "cascade")
        }
        baseline_tokens = summaries[suite]["codex"]["codex_tokens"]
        cascade_tokens = summaries[suite]["cascade"]["codex_tokens"]
        summaries[suite]["cascade"]["token_savings_percent"] = (
            100.0 * (1.0 - cascade_tokens / baseline_tokens) if baseline_tokens else math.nan
        )
        summaries[suite]["cascade"]["avoided_codex_calls_percent"] = 100.0 * (
            1.0 - summaries[suite]["cascade"]["codex_calls"] / len(subset)
        )

    paired_token_savings = [
        float(row["codex_input_tokens"] + row["codex_output_tokens"] - row["cascade_codex_tokens"])
        for row in rows
    ]
    paired_speedups = [
        float(row["codex_elapsed_ms"] / row["cascade_elapsed_ms"])
        for row in rows
        if row["cascade_elapsed_ms"] > 0
    ]
    paired_accuracy_delta = [
        float(bool(row["cascade_correct"])) - float(bool(row["codex_correct"])) for row in rows
    ]
    token_ci = bootstrap_ci(paired_token_savings, statistics.mean)
    speed_ci = bootstrap_ci(paired_speedups, statistics.mean)
    accuracy_ci = bootstrap_ci(paired_accuracy_delta, statistics.mean)
    payload = {
        "metadata": metadata,
        "summaries": summaries,
        "paired": {
            "mean_codex_tokens_saved_ci95": token_ci,
            "mean_speedup": statistics.mean(paired_speedups),
            "median_speedup": statistics.median(paired_speedups),
            "mean_speedup_ci95": speed_ci,
            "mean_accuracy_delta_ci95": accuracy_ci,
        },
    }
    (output / "summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    import csv

    with (output / "cases.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Laya-first cascade benchmark",
        "",
        "> Public-data pilot. Thresholds and checkpoint selection were frozen on a disjoint",
        "> development subset before the test subset was evaluated.",
        "",
        "## Reproducibility",
        "",
        f"- Timestamp: `{metadata['timestamp']}`",
        f"- Codex: `{metadata['codex_model']}` / `{metadata['reasoning_effort']}`",
        f"- Codex CLI: `{metadata['codex_version']}`",
        f"- Laya models resident: `{', '.join(metadata['loaded_models'])}`",
        f"- Laya PID before/after: `{metadata['laya_pid_before']}` / `{metadata['laya_pid_after']}`",
        f"- Persistent service: `{metadata['laya_persistent']}`",
        f"- Development/test cases per suite: `{metadata['dev_per_suite']}` / `{metadata['test_per_suite']}`",
        "",
        "## Overall results",
        "",
        "| Condition | Accuracy | Codex calls | Codex tokens | Median latency | p90 latency |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for condition in ("codex", "laya", "cascade"):
        item = summaries["overall"][condition]
        lines.append(
            f"| {condition} | {100 * item['accuracy']:.1f}% | {item['codex_calls']} | "
            f"{item['codex_tokens']} | {item['median_latency_ms']:.0f} ms | "
            f"{item['p90_latency_ms']:.0f} ms |"
        )
    cascade = summaries["overall"]["cascade"]
    lines.extend(
        [
            "",
            f"- Codex-token savings: **{cascade['token_savings_percent']:.1f}%**",
            f"- Avoided Codex calls: **{cascade['avoided_codex_calls_percent']:.1f}%**",
            f"- 95% bootstrap CI, mean tokens saved per case: "
            f"`[{token_ci[0]:.1f}, {token_ci[1]:.1f}]`",
            f"- Mean / median paired speedup: "
            f"**{statistics.mean(paired_speedups):.3f}x / {statistics.median(paired_speedups):.3f}x**",
            f"- 95% bootstrap CI, mean paired speedup: `[{speed_ci[0]:.3f}, {speed_ci[1]:.3f}]x`",
            f"- 95% bootstrap CI, accuracy delta: `[{100 * accuracy_ci[0]:.1f}, {100 * accuracy_ci[1]:.1f}]` percentage points",
            "",
            "## Results by suite",
            "",
            "| Suite | Codex accuracy | Cascade accuracy | Codex-token savings | Avoided calls |",
            "|---|---:|---:|---:|---:|",
            *[
                f"| {suite} | {100 * summaries[suite]['codex']['accuracy']:.1f}% | "
                f"{100 * summaries[suite]['cascade']['accuracy']:.1f}% | "
                f"{summaries[suite]['cascade']['token_savings_percent']:.1f}% | "
                f"{summaries[suite]['cascade']['avoided_codex_calls_percent']:.1f}% |"
                for suite in suites
            ],
            "",
            "## Frozen development policies",
            "",
            "| Suite | Checkpoint | Threshold | Dev coverage | Dev accepted accuracy |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for suite in suites:
        policy = metadata["policies"][suite]
        accepted_accuracy = (
            "n/a" if policy["accuracy"] is None else f"{100 * policy['accuracy']:.1f}%"
        )
        lines.append(
            f"| {suite} | {policy['checkpoint']} | {policy['threshold']:.4f} | "
            f"{100 * policy['coverage']:.1f}% | {accepted_accuracy} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `laya` is a component comparison: accepted or not, it never spends Codex tokens.",
            "- `cascade` uses Laya only above the development-selected confidence threshold and otherwise falls back to the same direct Codex decision used by the baseline.",
            "- AG News is explicitly a retention control because upstream reports training overlap.",
            "- Prompt Injections is the held-out generalization suite.",
            "- Raw Codex event streams stay local; this report publishes derived measurements and public dataset indices only.",
            "",
        ]
    )
    (output / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Laya-first Codex cascade benchmark")
    parser.add_argument("--dev-per-suite", type=int, default=40)
    parser.add_argument("--test-per-suite", type=int, default=20)
    parser.add_argument("--target-accuracy", type=float, default=0.95)
    parser.add_argument("--seed", type=int, default=20260922)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--reasoning-effort", default="low")
    return parser


def main() -> int:
    return benchmark(build_parser().parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
