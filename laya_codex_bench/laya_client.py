from __future__ import annotations

import base64
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


_WINDOWS_LOOPBACK_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$utf8 = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = $utf8
try {
    $request = ConvertFrom-Json -InputObject ([Console]::In.ReadToEnd())
    Add-Type -AssemblyName System.Net.Http
    $handler = [System.Net.Http.HttpClientHandler]::new()
    $handler.UseProxy = $false
    $client = [System.Net.Http.HttpClient]::new($handler)
    try {
        $client.Timeout = [TimeSpan]::FromSeconds([double]$request.timeout)
        $uri = "http://127.0.0.1:$($request.port)$($request.path)"
        if ($request.method -eq 'GET') {
            $response = $client.GetAsync($uri).GetAwaiter().GetResult()
        } elseif ($request.method -eq 'POST') {
            $body = [System.Net.Http.ByteArrayContent]::new(
                [System.Text.Encoding]::UTF8.GetBytes([string]$request.body)
            )
            $body.Headers.ContentType =
                [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse(
                    'application/json; charset=utf-8'
                )
            $response = $client.PostAsync($uri, $body).GetAwaiter().GetResult()
        } else {
            throw "Unsupported HTTP method: $($request.method)"
        }
        try {
            if (-not $response.IsSuccessStatusCode) {
                $details = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
                throw ("HTTP {0}: {1}" -f [int]$response.StatusCode, $details)
            }
            $responseBody = $response.Content.ReadAsByteArrayAsync().GetAwaiter().GetResult()
            $stdout = [Console]::OpenStandardOutput()
            $stdout.Write($responseBody, 0, $responseBody.Length)
            $stdout.Flush()
        } finally {
            $response.Dispose()
        }
    } finally {
        $client.Dispose()
    }
} catch {
    [Console]::Error.Write($_.Exception.Message)
    exit 1
}
"""
_WINDOWS_LOOPBACK_COMMAND = base64.b64encode(
    _WINDOWS_LOOPBACK_SCRIPT.encode("utf-16le")
).decode("ascii")


class LayaClient:
    def __init__(self, project_root: Path, port: int = 8765) -> None:
        self.project_root = project_root
        self.port = port
        self.base_url = f"http://127.0.0.1:{port}"

    @staticmethod
    def _is_wsl() -> bool:
        if os.name == "nt":
            return False
        if os.environ.get("WSL_INTEROP") or os.environ.get("WSL_DISTRO_NAME"):
            return True
        try:
            release = Path("/proc/sys/kernel/osrelease").read_text(encoding="ascii")
        except OSError:
            return False
        return "microsoft" in release.lower()

    def _request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None,
        *,
        timeout: int,
    ) -> dict[str, Any]:
        data = (
            json.dumps(payload, ensure_ascii=False).encode("utf-8")
            if payload is not None
            else None
        )
        if self._is_wsl():
            request = {
                "method": method,
                "path": path,
                "port": self.port,
                "timeout": timeout,
                "body": data.decode("utf-8") if data is not None else None,
            }
            try:
                response = subprocess.run(
                    [
                        "powershell.exe",
                        "-NoLogo",
                        "-NoProfile",
                        "-NonInteractive",
                        "-EncodedCommand",
                        _WINDOWS_LOOPBACK_COMMAND,
                    ],
                    input=json.dumps(request, ensure_ascii=False).encode("utf-8"),
                    capture_output=True,
                    timeout=timeout + 5,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise TimeoutError("Windows PowerShell request to Laya timed out") from exc
            except OSError as exc:
                raise urllib.error.URLError(exc) from exc
            if response.returncode != 0:
                detail = response.stderr.decode("utf-8", errors="replace").strip()
                raise urllib.error.URLError(
                    detail or f"Windows PowerShell exited with status {response.returncode}"
                )
            return json.loads(response.stdout.decode("utf-8-sig"))

        headers = (
            {"Content-Type": "application/json; charset=utf-8"} if data is not None else {}
        )
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)

    def health(self) -> dict[str, Any] | None:
        try:
            return self._request_json("GET", "/health", None, timeout=2)
        except (
            urllib.error.URLError,
            TimeoutError,
            json.JSONDecodeError,
            UnicodeDecodeError,
        ):
            return None

    def ensure_started(self) -> dict[str, Any]:
        health = self.health()
        if self._is_wsl():
            if (
                health
                and health.get("model_loaded")
                and health.get("api_version") == 2
                and "multilingual" in (health.get("loaded_models") or ())
            ):
                return health
            if health and health.get("model_loaded") and health.get("api_version") == 2:
                raise RuntimeError(
                    "The WSL client requires multilingual to be already loaded; "
                    "it will not load or start another model."
                )
            if health:
                raise RuntimeError(
                    "An outdated Laya service is already using the benchmark port; "
                    "the WSL client will not restart it."
                )
            raise RuntimeError(
                "No healthy Laya service is reachable through Windows PowerShell loopback; "
                "start the service separately on Windows."
            )
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
        return self._request_json("POST", "/predict", payload, timeout=120)


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
