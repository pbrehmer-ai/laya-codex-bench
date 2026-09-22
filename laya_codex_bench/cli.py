from __future__ import annotations

import argparse
import json
import os
import platform
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .codex_runner import run_codex
from .dataset import load_tasks
from .laya_client import LayaClient, normalized_laya_decisions
from .metrics import load_rows, score_decisions
from .prompts import baseline_prompt, preflight_prompt, skill_prompt
from .report import write_reports


ROOT = Path(__file__).resolve().parents[1]
CONDITIONS = ("baseline", "skill", "preflight")


def system_metadata() -> dict[str, Any]:
    codex_version = subprocess.run(
        ["codex", "--version"], capture_output=True, text=True, check=False
    ).stdout.strip()
    cpu = platform.processor() or os.environ.get("PROCESSOR_IDENTIFIER", "unknown")
    ram_gb = None
    if sys.platform == "win32":
        output = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "[math]::Round((Get-CimInstance Win32_OperatingSystem).TotalVisibleMemorySize/1MB,2)",
            ],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        try:
            ram_gb = float(output.replace(",", "."))
        except ValueError:
            ram_gb = None
    return {"codex_version": codex_version, "cpu": cpu, "ram_gb": ram_gb, "os": platform.platform()}


def write_request(task: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"state": task.state, "questions": task.questions}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def run_benchmark(args: argparse.Namespace) -> int:
    dataset_path = (ROOT / args.dataset).resolve()
    tasks = load_tasks(dataset_path)
    if args.limit:
        tasks = tasks[: args.limit]
    conditions = tuple(args.conditions.split(","))
    unknown = set(conditions) - set(CONDITIONS)
    if unknown:
        raise ValueError(f"Unknown conditions: {sorted(unknown)}")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_root = ROOT / "runs" / "raw" / timestamp
    run_root.mkdir(parents=True, exist_ok=True)
    result_path = run_root / "results.jsonl"
    schema_path = ROOT / "schemas" / "decision-output.schema.json"
    laya = LayaClient(ROOT)
    if "skill" in conditions or "preflight" in conditions:
        health = laya.ensure_started()
        warmup = laya.predict(tasks[0].state, tasks[0].questions)
    else:
        health = {}
        warmup = {}

    schedule = [(task, repetition, condition) for repetition in range(args.repetitions) for task in tasks for condition in conditions]
    random.Random(args.seed).shuffle(schedule)
    rows: list[dict[str, Any]] = []
    with result_path.open("a", encoding="utf-8") as result_file:
        for index, (task, repetition, condition) in enumerate(schedule, 1):
            run_id = f"{task.id}-r{repetition + 1}-{condition}"
            print(f"[{index}/{len(schedule)}] {run_id}", flush=True)
            request_path = ROOT / ".runtime" / "benchmark-inputs" / f"{run_id}.json"
            write_request(task, request_path)
            laya_result = None
            laya_ms = 0.0
            if condition == "baseline":
                prompt = baseline_prompt(task)
            elif condition == "skill":
                prompt = skill_prompt(task)
            else:
                laya_result = laya.predict(task.state, task.questions)
                laya_ms = float(laya_result.get("deployment", {}).get("inference_ms", 0.0))
                prompt = preflight_prompt(task, normalized_laya_decisions(laya_result))

            outcome = run_codex(
                project_root=ROOT,
                prompt=prompt,
                model=args.model,
                reasoning_effort=args.reasoning_effort,
                schema_path=schema_path,
                run_dir=run_root / run_id,
            )
            if condition == "skill":
                laya_ms = float(outcome.get("laya_inference_ms", 0.0))
            correct, total = score_decisions(outcome["final"], task.expected)
            usage = outcome.get("usage", {})
            valid_tool_use = condition != "skill" or outcome["laya_called_by_codex"]
            row = {
                "run_id": run_id,
                "task_id": task.id,
                "category": task.category,
                "language": task.language,
                "repetition": repetition + 1,
                "condition": condition,
                "success": outcome["exit_code"] == 0 and outcome["final"] is not None and valid_tool_use,
                "exit_code": outcome["exit_code"],
                "correct": correct,
                "total_decisions": total,
                "elapsed_ms": outcome["elapsed_ms"],
                "laya_inference_ms": laya_ms,
                "input_tokens": int(usage.get("input_tokens", 0)),
                "cached_input_tokens": int(usage.get("cached_input_tokens", 0)),
                "output_tokens": int(usage.get("output_tokens", 0)),
                "reasoning_output_tokens": int(usage.get("reasoning_output_tokens", 0)),
                "laya_called_by_codex": outcome["laya_called_by_codex"],
                "event_count": outcome["event_count"],
            }
            rows.append(row)
            result_file.write(json.dumps(row, ensure_ascii=False) + "\n")
            result_file.flush()

    final_health = laya.health() if health else {}
    metadata = {
        **system_metadata(),
        "timestamp": timestamp,
        "dataset": str(dataset_path.relative_to(ROOT)),
        "tasks": len(tasks),
        "repetitions": args.repetitions,
        "conditions": conditions,
        "seed": args.seed,
        "model": args.model,
        "reasoning_effort": args.reasoning_effort,
        "laya_checkpoint": health.get("checkpoint", "not used"),
        "laya_device": health.get("device", "not used"),
        "laya_service_pid": health.get("pid", "not used"),
        "laya_service_pid_after": (final_health or {}).get("pid", "not used"),
        "laya_service_persistent": bool(
            health and final_health and health.get("pid") == final_health.get("pid")
        ),
        "laya_warmup_inference_ms": warmup.get("deployment", {}).get("inference_ms", 0.0),
    }
    (run_root / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_reports(rows, ROOT / "reports" / "generated" / timestamp, metadata)
    print(f"Results: {result_path}")
    return 0


def validate(args: argparse.Namespace) -> int:
    tasks = load_tasks((ROOT / args.dataset).resolve())
    print(f"Valid dataset: {len(tasks)} tasks, {sum(len(task.questions) for task in tasks)} decisions")
    return 0


def analyze(args: argparse.Namespace) -> int:
    result_path = (ROOT / args.results).resolve()
    rows = load_rows(result_path)
    metadata_path = result_path.parent / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    output = (ROOT / args.output).resolve()
    write_reports(rows, output, metadata)
    print(f"Report: {output}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark Laya-assisted Codex workflows")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate a JSONL dataset")
    validate_parser.add_argument("--dataset", default="datasets/pilot.jsonl")
    validate_parser.set_defaults(func=validate)

    run_parser = subparsers.add_parser("run", help="Run a benchmark")
    run_parser.add_argument("--dataset", default="datasets/pilot.jsonl")
    run_parser.add_argument("--model", default="gpt-5.6-terra")
    run_parser.add_argument("--reasoning-effort", default="medium")
    run_parser.add_argument("--repetitions", type=int, default=1)
    run_parser.add_argument("--conditions", default=",".join(CONDITIONS))
    run_parser.add_argument("--seed", type=int, default=20260922)
    run_parser.add_argument("--limit", type=int)
    run_parser.set_defaults(func=run_benchmark)

    analyze_parser = subparsers.add_parser("analyze", help="Regenerate reports from raw results")
    analyze_parser.add_argument("--results", required=True)
    analyze_parser.add_argument("--output", default="reports/generated/manual")
    analyze_parser.set_defaults(func=analyze)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except Exception as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
