from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from .metrics import build_summary


def _number(value: Any, digits: int = 2) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/a"
    return f"{float(value):.{digits}f}"


def write_reports(rows: list[dict[str, Any]], report_dir: Path, metadata: dict[str, Any]) -> dict[str, Any]:
    report_dir.mkdir(parents=True, exist_ok=True)
    summary = build_summary(rows)
    payload = {"metadata": metadata, **summary}
    (report_dir / "summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if rows:
        with (report_dir / "runs.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

    lines = [
        "# Pilot benchmark results",
        "",
        "> These are exploratory pilot results, not a general performance claim. The dataset,",
        "> hardware, Codex model, reasoning effort, repetitions, and warm/cold state are part of",
        "> the result and must be cited with any numbers below.",
        "",
        "## Run metadata",
        "",
        f"- Timestamp: `{metadata.get('timestamp')}`",
        f"- Dataset: `{metadata.get('dataset')}`",
        f"- Tasks: `{metadata.get('tasks')}`",
        f"- Repetitions: `{metadata.get('repetitions')}`",
        f"- Codex CLI: `{metadata.get('codex_version')}`",
        f"- Codex model: `{metadata.get('model')}`",
        f"- Reasoning effort: `{metadata.get('reasoning_effort')}`",
        f"- Laya: `{metadata.get('laya_checkpoint')}` on `{metadata.get('laya_device')}`",
        f"- Laya PID before/after: `{metadata.get('laya_service_pid')}` / `{metadata.get('laya_service_pid_after')}`",
        f"- Persistent warm Laya service: `{metadata.get('laya_service_persistent')}`",
        f"- Warm-up inference: `{_number(metadata.get('laya_warmup_inference_ms'), 2)} ms`",
        f"- CPU: `{metadata.get('cpu')}`",
        f"- RAM: `{metadata.get('ram_gb')} GB`",
        "",
        "## Conditions",
        "",
        "| Condition | Runs | Success | Accuracy | Median input | Median uncached input | Median output | Total Codex tokens | Median latency | p90 latency |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in ("baseline", "skill", "preflight"):
        item = summary["conditions"].get(name, {})
        lines.append(
            f"| {name} | {item.get('runs', 0)} | {item.get('successful_runs', 0)} | "
            f"{_number(100 * item.get('decision_accuracy', 0), 1)}% | "
            f"{_number(item.get('input_tokens_median'), 0)} | "
            f"{_number(item.get('uncached_input_tokens_median'), 0)} | "
            f"{_number(item.get('output_tokens_median'), 0)} | "
            f"{item.get('codex_tokens_total', 0)} | "
            f"{_number(item.get('elapsed_ms_median'), 0)} ms | {_number(item.get('elapsed_ms_p90'), 0)} ms |"
        )
    lines.extend(["", "## Paired comparisons against direct Codex", ""])
    for name in ("skill", "preflight"):
        item = summary["comparisons"].get(name, {})
        lines.extend(
            [
                f"### {name}",
                "",
                f"- Paired runs: `{item.get('paired_runs', 0)}`",
                f"- Mean input tokens saved: `{_number(item.get('mean_input_tokens_saved'), 1)}`",
                f"- Median input tokens saved: `{_number(item.get('median_input_tokens_saved'), 1)}`",
                f"- Median uncached input tokens saved: `{_number(item.get('median_uncached_input_tokens_saved'), 1)}`",
                f"- Median total Codex tokens saved (input + output): `{_number(item.get('median_total_codex_tokens_saved'), 1)}`",
                f"- 95% bootstrap CI for mean input-token savings: "
                f"`[{_number((item.get('mean_input_tokens_saved_ci95') or [math.nan])[0], 1)}, "
                f"{_number((item.get('mean_input_tokens_saved_ci95') or [math.nan, math.nan])[1], 1)}]`",
                f"- Median end-to-end speedup: `{_number(item.get('median_speedup'), 3)}x`",
                f"- 95% bootstrap CI for mean speedup: "
                f"`[{_number((item.get('mean_speedup_ci95') or [math.nan])[0], 3)}, "
                f"{_number((item.get('mean_speedup_ci95') or [math.nan, math.nan])[1], 3)}]x`",
                "",
            ]
        )
    lines.extend(
        [
            "## Interpretation rules",
            "",
            "- Laya tokenizer counts are intentionally not added to Codex tokens; they are different tokenizers and local inference has no API-token charge.",
            "- The skill condition includes Codex orchestration and tool-call overhead.",
            "- The preflight condition is a production-style router and gives Codex only compact typed decisions, so it is not a fixed-context ablation.",
            "- A lower token count is useful only when task success and decision accuracy remain acceptable.",
            "- Raw event logs remain local because they may contain machine paths or model reasoning artifacts.",
            "",
        ]
    )
    (report_dir / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    return payload
