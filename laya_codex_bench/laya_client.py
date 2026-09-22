from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


class LayaClient:
    def __init__(self, project_root: Path, port: int = 8765) -> None:
        self.project_root = project_root
        self.port = port
        self.base_url = f"http://127.0.0.1:{port}"

    def health(self) -> dict[str, Any] | None:
        try:
            with urllib.request.urlopen(f"{self.base_url}/health", timeout=2) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return None

    def ensure_started(self) -> dict[str, Any]:
        health = self.health()
        if health and health.get("model_loaded") and health.get("api_version") == 2:
            return health
        if health:
            raise RuntimeError(
                "An outdated Laya service is already using the benchmark port; restart it once."
            )
        runtime_dir = self.project_root / ".runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        python = self.project_root / ".venv" / "Scripts" / "python.exe"
        stdout_handle = (runtime_dir / "laya-server.stdout.log").open("a", encoding="utf-8")
        stderr_handle = (runtime_dir / "laya-server.stderr.log").open("a", encoding="utf-8")
        creationflags = 0
        start_new_session = False
        if os.name == "nt":
            creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            start_new_session = True
        try:
            subprocess.Popen(
                [str(python), "-u", str(self.project_root / "laya_local.py"), "serve", "--port", str(self.port)],
                cwd=self.project_root,
                stdin=subprocess.DEVNULL,
                stdout=stdout_handle,
                stderr=stderr_handle,
                creationflags=creationflags,
                start_new_session=start_new_session,
                close_fds=True,
            )
        finally:
            stdout_handle.close()
            stderr_handle.close()
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            health = self.health()
            if health and health.get("model_loaded") and health.get("api_version") == 2:
                (runtime_dir / "laya-server.pid").write_text(str(health["pid"]), encoding="ascii")
                return health
            time.sleep(0.25)
        raise TimeoutError("Laya did not report model_loaded=true within 600 seconds")

    def predict(
        self,
        state: Any,
        questions: dict[str, Any],
        *,
        model: str | None = None,
        task: str | None = None,
        lang: str | None = None,
    ) -> dict[str, Any]:
        self.ensure_started()
        payload: dict[str, Any] = {"state": state, "questions": questions}
        if model is not None:
            payload["model"] = model
        if task is not None:
            payload["task"] = task
        if lang is not None:
            payload["lang"] = lang
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/predict",
            data=data,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.load(response)


def normalized_laya_decisions(result: dict[str, Any]) -> list[dict[str, str]]:
    decisions: list[dict[str, str]] = []
    for qid, answer in result["answers"].items():
        kind = answer["type"]
        if kind == "choice":
            value = str(answer["choice"])
        elif kind == "noul":
            value = "true" if float(answer["noul"]) >= 0.5 else "false"
        elif kind == "score":
            value = str(round(float(answer["score"])))
        else:
            raise ValueError(f"Unsupported Laya answer type: {kind}")
        decisions.append({"id": qid, "value": value})
    return decisions
