from __future__ import annotations

import json
from pathlib import Path

from .models import Task


def load_tasks(path: Path) -> list[Task]:
    tasks: list[Task] = []
    seen: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
        task = Task.from_dict(raw)
        if task.id in seen:
            raise ValueError(f"{path}:{line_number}: duplicate id {task.id!r}")
        seen.add(task.id)
        tasks.append(task)
    if not tasks:
        raise ValueError(f"Dataset is empty: {path}")
    return tasks

