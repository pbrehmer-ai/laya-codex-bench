from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any


def run_codex(
    *,
    project_root: Path,
    prompt: str,
    model: str,
    reasoning_effort: str,
    schema_path: Path,
    run_dir: Path,
    ignore_user_config: bool = False,
    ignore_rules: bool = False,
) -> dict[str, Any]:
    run_dir.mkdir(parents=True, exist_ok=True)
    events_path = run_dir / "events.jsonl"
    stderr_path = run_dir / "stderr.log"
    final_path = run_dir / "final.json"
    prompt_path = run_dir / "prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")

    command = [
        "codex",
        "exec",
        "-",
        "--json",
        "--ephemeral",
    ]
    if ignore_user_config:
        command.append("--ignore-user-config")
    if ignore_rules:
        command.append("--ignore-rules")
    command.extend([
        "--model",
        model,
        "--sandbox",
        "workspace-write",
        "--color",
        "never",
        "--output-schema",
        str(schema_path),
        "--output-last-message",
        str(final_path),
        "-c",
        f'model_reasoning_effort="{reasoning_effort}"',
        "-C",
        str(project_root),
    ])
    env = os.environ.copy()
    started_ns = time.perf_counter_ns()
    with prompt_path.open("r", encoding="utf-8") as prompt_file, events_path.open(
        "w", encoding="utf-8"
    ) as events_file, stderr_path.open("w", encoding="utf-8") as stderr_file:
        completed = subprocess.run(
            command,
            stdin=prompt_file,
            stdout=events_file,
            stderr=stderr_file,
            cwd=project_root,
            env=env,
            text=True,
            timeout=600,
            check=False,
        )
    elapsed_ms = (time.perf_counter_ns() - started_ns) / 1_000_000

    events: list[dict[str, Any]] = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    completed_event = next((event for event in reversed(events) if event.get("type") == "turn.completed"), {})
    usage = completed_event.get("usage", {})
    commands = [
        event.get("item", {}).get("command", "")
        for event in events
        if event.get("type") == "item.completed"
        and event.get("item", {}).get("type") == "command_execution"
    ]
    successful_laya_calls = [
        event.get("item", {})
        for event in events
        if event.get("type") == "item.completed"
        and event.get("item", {}).get("type") == "mcp_tool_call"
        and event.get("item", {}).get("tool") == "laya_predict"
        and event.get("item", {}).get("status") == "completed"
        and event.get("item", {}).get("error") is None
        and event.get("item", {}).get("result") is not None
    ]
    laya_inference_ms = 0.0
    if successful_laya_calls:
        structured = successful_laya_calls[0].get("result", {}).get("structured_content", {})
        laya_inference_ms = float(structured.get("deployment", {}).get("inference_ms", 0.0))
    final: dict[str, Any] | None = None
    if final_path.exists():
        try:
            final = json.loads(final_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            final = None
    return {
        "exit_code": completed.returncode,
        "elapsed_ms": round(elapsed_ms, 2),
        "usage": usage,
        "commands": commands,
        "laya_called_by_codex": len(successful_laya_calls) == 1,
        "laya_inference_ms": laya_inference_ms,
        "final": final,
        "event_count": len(events),
    }
