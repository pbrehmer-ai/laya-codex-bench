import io
import json
import os
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from laya_codex_bench.laya_client import LayaClient


class LayaClientTransportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = LayaClient(Path(__file__).resolve().parents[1])

    @staticmethod
    def completed_json(value: dict[str, object]) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(
            args=["powershell.exe"],
            returncode=0,
            stdout=json.dumps(value, ensure_ascii=False).encode("utf-8"),
            stderr=b"",
        )

    def require_posix(self) -> None:
        if os.name == "nt":
            self.skipTest("WSL transport tests require a POSIX host")

    def test_wsl_health_uses_windows_loopback_transport(self) -> None:
        self.require_posix()
        health = {
            "status": "ok",
            "api_version": 2,
            "model_loaded": True,
            "loaded_models": ["multilingual"],
        }
        with (
            patch.dict(os.environ, {"WSL_INTEROP": "/run/WSL/123"}),
            patch(
                "laya_codex_bench.laya_client.subprocess.run",
                return_value=self.completed_json(health),
            ) as run,
            patch(
                "laya_codex_bench.laya_client.urllib.request.urlopen",
                side_effect=AssertionError("WSL must not call Linux loopback directly"),
            ),
        ):
            self.assertEqual(health, self.client.health())

        command = run.call_args.args[0]
        self.assertEqual("powershell.exe", command[0])
        self.assertIn("-EncodedCommand", command)
        envelope = json.loads(run.call_args.kwargs["input"].decode("utf-8"))
        self.assertEqual(
            {"method": "GET", "path": "/health", "port": 8765, "timeout": 2, "body": None},
            envelope,
        )

    def test_wsl_predict_preserves_request_and_response_json(self) -> None:
        self.require_posix()
        health = {
            "status": "ok",
            "api_version": 2,
            "model_loaded": True,
            "loaded_models": ["multilingual"],
        }
        result = {
            "answers": {"q0": {"type": "choice", "choice": "billing"}},
            "deployment": {"inference_ms": 42.5},
            "note": "Prüfung abgeschlossen",
        }
        state = {"subject": "Änderung", "body": "Bitte prüfen"}
        questions = {
            "q0": {
                "type": "choice",
                "instructions": "Welche Abteilung ist zuständig?",
                "criteria": {"billing": "Rechnungen", "other": "Sonstiges"},
            }
        }
        with (
            patch.dict(os.environ, {"WSL_INTEROP": "/run/WSL/123"}),
            patch(
                "laya_codex_bench.laya_client.subprocess.run",
                side_effect=[self.completed_json(health), self.completed_json(result)],
            ) as run,
            patch(
                "laya_codex_bench.laya_client.urllib.request.urlopen",
                side_effect=AssertionError("WSL must not call Linux loopback directly"),
            ),
        ):
            self.assertEqual(result, self.client.predict(state, questions))

        self.assertEqual(2, run.call_count)
        envelope = json.loads(run.call_args_list[1].kwargs["input"].decode("utf-8"))
        self.assertEqual("POST", envelope["method"])
        self.assertEqual("/predict", envelope["path"])
        self.assertEqual(
            {"state": state, "questions": questions},
            json.loads(envelope["body"]),
        )

    def test_wsl_unavailable_bridge_does_not_start_service(self) -> None:
        self.require_posix()
        failure = subprocess.CompletedProcess(
            args=["powershell.exe"],
            returncode=1,
            stdout=b"",
            stderr=b"connection refused",
        )
        with (
            patch.dict(os.environ, {"WSL_INTEROP": "/run/WSL/123"}),
            patch("laya_codex_bench.laya_client.subprocess.run", return_value=failure),
            patch("laya_codex_bench.laya_client.subprocess.Popen") as start,
        ):
            self.assertIsNone(self.client.health())
            with self.assertRaisesRegex(RuntimeError, "start the service separately on Windows"):
                self.client.ensure_started()
            start.assert_not_called()

    def test_wsl_rejects_non_multilingual_service_without_starting(self) -> None:
        self.require_posix()
        english_only = {
            "status": "ok",
            "api_version": 2,
            "model_loaded": True,
            "loaded_models": ["english"],
        }
        with (
            patch.dict(os.environ, {"WSL_INTEROP": "/run/WSL/123"}),
            patch.object(self.client, "health", return_value=english_only),
            patch("laya_codex_bench.laya_client.subprocess.Popen") as start,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "requires multilingual to be already loaded",
            ):
                self.client.ensure_started()
            start.assert_not_called()

    def test_non_wsl_health_keeps_native_urllib_transport(self) -> None:
        health = {"status": "ok", "api_version": 2, "model_loaded": True}
        response = io.BytesIO(json.dumps(health).encode("utf-8"))
        with (
            patch.object(LayaClient, "_is_wsl", return_value=False),
            patch("laya_codex_bench.laya_client.urllib.request.urlopen", return_value=response),
            patch("laya_codex_bench.laya_client.subprocess.run") as run,
        ):
            self.assertEqual(health, self.client.health())
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
