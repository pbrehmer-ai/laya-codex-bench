from __future__ import annotations

import json
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable


def normalize_decisions(final: dict[str, Any] | None) -> dict[str, str]:
    if not final or not isinstance(final.get("decisions"), list):
        return {}
    result: dict[str, str] = {}
    for item in final["decisions"]:
        if isinstance(item, dict) and "id" in item and "value" in item:
            result[str(item["id"])] = str(item["value"]).strip().lower()
    return result


def score_decisions(final: dict[str, Any] | None, expected: dict[str, list[str]]) -> tuple[int, int]:
    actual = normalize_decisions(final)
    correct = 0
    for qid, accepted in expected.items():
        if actual.get(qid) in {str(value).strip().lower() for value in accepted}:
            correct += 1
    return correct, len(expected)


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    index = (len(ordered) - 1) * quantile
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - index) + ordered[upper] * (index - lower)


def bootstrap_ci(
    values: list[float], statistic: Callable[[list[float]], float], seed: int = 20260922, samples: int = 5000
) -> tuple[float, float]:
    if not values:
        return math.nan, math.nan
    rng = random.Random(seed)
    estimates = [statistic([rng.choice(values) for _ in values]) for _ in range(samples)]
    return percentile(estimates, 0.025), percentile(estimates, 0.975)


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["condition"]].append(row)
    conditions: dict[str, Any] = {}
    for condition, items in grouped.items():
        elapsed = [float(item["elapsed_ms"]) for item in items if item["success"]]
        input_tokens = [int(item["input_tokens"]) for item in items if item["success"]]
        cached_tokens = [int(item.get("cached_input_tokens", 0)) for item in items if item["success"]]
        output_tokens = [int(item["output_tokens"]) for item in items if item["success"]]
        uncached_tokens = [
            max(0, int(item["input_tokens"]) - int(item.get("cached_input_tokens", 0)))
            for item in items
            if item["success"]
        ]
        total_codex_tokens = [
            int(item["input_tokens"]) + int(item["output_tokens"])
            for item in items
            if item["success"]
        ]
        correct = sum(int(item["correct"]) for item in items)
        total = sum(int(item["total_decisions"]) for item in items)
        conditions[condition] = {
            "runs": len(items),
            "successful_runs": sum(bool(item["success"]) for item in items),
            "decision_accuracy": correct / total if total else 0.0,
            "input_tokens_total": sum(input_tokens),
            "cached_input_tokens_total": sum(cached_tokens),
            "uncached_input_tokens_total": sum(uncached_tokens),
            "output_tokens_total": sum(output_tokens),
            "codex_tokens_total": sum(total_codex_tokens),
            "input_tokens_median": statistics.median(input_tokens) if input_tokens else math.nan,
            "uncached_input_tokens_median": statistics.median(uncached_tokens) if uncached_tokens else math.nan,
            "output_tokens_median": statistics.median(output_tokens) if output_tokens else math.nan,
            "elapsed_ms_median": statistics.median(elapsed) if elapsed else math.nan,
            "elapsed_ms_p90": percentile(elapsed, 0.9),
        }

    comparisons: dict[str, Any] = {}
    baseline_index = {
        (row["task_id"], row["repetition"]): row
        for row in grouped.get("baseline", [])
        if row["success"]
    }
    for condition in ("skill", "preflight"):
        token_savings: list[float] = []
        uncached_savings: list[float] = []
        total_savings: list[float] = []
        speedups: list[float] = []
        for row in grouped.get(condition, []):
            baseline = baseline_index.get((row["task_id"], row["repetition"]))
            if not baseline or not row["success"]:
                continue
            token_savings.append(float(baseline["input_tokens"] - row["input_tokens"]))
            uncached_savings.append(
                float(
                    (baseline["input_tokens"] - baseline.get("cached_input_tokens", 0))
                    - (row["input_tokens"] - row.get("cached_input_tokens", 0))
                )
            )
            total_savings.append(
                float(
                    (baseline["input_tokens"] + baseline["output_tokens"])
                    - (row["input_tokens"] + row["output_tokens"])
                )
            )
            if row["elapsed_ms"] > 0:
                speedups.append(float(baseline["elapsed_ms"] / row["elapsed_ms"]))
        token_ci = bootstrap_ci(token_savings, statistics.mean) if token_savings else (math.nan, math.nan)
        speed_ci = bootstrap_ci(speedups, statistics.mean) if speedups else (math.nan, math.nan)
        comparisons[condition] = {
            "paired_runs": len(token_savings),
            "mean_input_tokens_saved": statistics.mean(token_savings) if token_savings else math.nan,
            "median_input_tokens_saved": statistics.median(token_savings) if token_savings else math.nan,
            "mean_input_tokens_saved_ci95": token_ci,
            "median_uncached_input_tokens_saved": statistics.median(uncached_savings)
            if uncached_savings
            else math.nan,
            "median_total_codex_tokens_saved": statistics.median(total_savings)
            if total_savings
            else math.nan,
            "median_speedup": statistics.median(speedups) if speedups else math.nan,
            "mean_speedup_ci95": speed_ci,
        }
    return {"conditions": conditions, "comparisons": comparisons}


def load_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
