"""Project-local CLI and HTTP service for the Laya decision model."""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
CACHE_ROOT = ROOT / ".cache"
os.environ.setdefault("HF_HOME", str(CACHE_ROOT / "huggingface"))
os.environ.setdefault("HF_HUB_CACHE", str(CACHE_ROOT / "huggingface" / "hub"))
os.environ.setdefault("TRANSFORMERS_CACHE", str(CACHE_ROOT / "huggingface" / "transformers"))
os.environ.setdefault("TORCH_HOME", str(CACHE_ROOT / "torch"))
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

MODEL_ID = "convaiinnovations/laya"
DEFAULT_PRELOAD_MODELS = ("multilingual",)
MODEL_ROOT = ROOT / "models" / "laya"

_router: Any | None = None
_agent_lock = threading.Lock()
_predict_lock = threading.Lock()
_loaded_at: float | None = None


def load_router() -> Any:
    """Preload the configured checkpoints once and retain them for this process."""
    global _router, _loaded_at
    if _router is None:
        with _agent_lock:
            if _router is None:
                import laya
                from huggingface_hub import snapshot_download

                started = time.perf_counter()
                preload_models = tuple(
                    item.strip()
                    for item in os.environ.get(
                        "LAYA_PRELOAD_MODELS", ",".join(DEFAULT_PRELOAD_MODELS)
                    ).split(",")
                    if item.strip()
                )
                layouts = {
                    "english": (MODEL_ROOT / "english", None),
                    "multilingual": (MODEL_ROOT / "multilingual", "multilingual"),
                    "typed-decisions": (MODEL_ROOT / "typed-decisions", "typed-decisions"),
                }
                unknown = sorted(set(preload_models) - set(layouts))
                if unknown:
                    raise ValueError(f"Unknown Laya checkpoint(s): {', '.join(unknown)}")
                required = ["model.safetensors", "rl_agent_config.json", "encoder/*", "tokenizer/*"]
                for name in preload_models:
                    directory, hub_subfolder = layouts[name]
                    if not (directory / "model.safetensors").exists():
                        directory.mkdir(parents=True, exist_ok=True)
                        patterns = required if hub_subfolder is None else [f"{hub_subfolder}/{item}" for item in required]
                        snapshot_download(
                            repo_id=MODEL_ID,
                            allow_patterns=patterns,
                            local_dir=MODEL_ROOT if hub_subfolder else directory,
                        )
                _router = laya.Router(
                    models={name: str(directory) for name, (directory, _) in layouts.items()},
                    device="cpu",
                    max_loaded=max(1, len(preload_models)),
                )
                _router.preload(list(preload_models))
                _loaded_at = time.perf_counter() - started
    return _router


def validate_request(payload: Any) -> tuple[Any, dict[str, dict[str, Any]]]:
    if not isinstance(payload, dict):
        raise ValueError("Request must be a JSON object.")
    if "state" not in payload:
        raise ValueError("Missing required field: state")
    questions = payload.get("questions")
    if not isinstance(questions, dict) or not questions:
        raise ValueError("questions must be a non-empty JSON object.")
    return payload["state"], questions


def predict(payload: Any) -> dict[str, Any]:
    state, questions = validate_request(payload)
    router = load_router()
    started = time.perf_counter()
    with _predict_lock:
        result = router.predict(
            state,
            questions,
            model=payload.get("model"),
            task=payload.get("task"),
            lang=payload.get("lang"),
        )
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    return {
        **result,
        "deployment": {
            "checkpoint": result.get("routing", {}).get("repo", MODEL_ID),
            "device": "cpu",
            "inference_ms": elapsed_ms,
            "initial_load_seconds": round(_loaded_at or 0.0, 2),
        },
    }


def read_payload(input_path: str | None) -> Any:
    if input_path:
        return json.loads(Path(input_path).read_text(encoding="utf-8"))
    if sys.stdin.isatty():
        raise ValueError("Pass --input REQUEST.json or pipe a JSON request to stdin.")
    return json.load(sys.stdin)


class LayaHandler(BaseHTTPRequestHandler):
    server_version = "LayaLocal/0.2"

    def _send_json(self, status: int, value: Any) -> None:
        body = json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send_json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "api_version": 2,
                    "model_loaded": _router is not None,
                    "checkpoint": MODEL_ID,
                    "loaded_models": list(_router.loaded) if _router is not None else [],
                    "device": "cpu",
                    "pid": os.getpid(),
                    "initial_load_seconds": round(_loaded_at or 0.0, 2),
                },
            )
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "Use GET /health or POST /predict"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/predict":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Use POST /predict"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 1_000_000:
                raise ValueError("Content-Length must be between 1 and 1,000,000 bytes.")
            payload = json.loads(self.rfile.read(length))
            self._send_json(HTTPStatus.OK, predict(payload))
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:  # Keep errors visible during this local experiment.
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"{type(exc).__name__}: {exc}"})

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}", file=sys.stderr)


def command_predict(args: argparse.Namespace) -> int:
    try:
        result = predict(read_payload(args.input))
    except Exception as exc:
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def command_serve(args: argparse.Namespace) -> int:
    if not args.lazy:
        print("Preloading configured Laya checkpoints on CPU...", flush=True)
        load_router()
    server = ThreadingHTTPServer((args.host, args.port), LayaHandler)
    print(f"Laya listening on http://{args.host}:{args.port}", flush=True)
    print("Endpoints: GET /health, POST /predict", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Laya.", flush=True)
    finally:
        server.server_close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Laya locally from this project.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    predict_parser = subparsers.add_parser("predict", help="Evaluate one JSON request.")
    predict_parser.add_argument("--input", help="UTF-8 JSON file; omit to read stdin.")
    predict_parser.set_defaults(func=command_predict)

    serve_parser = subparsers.add_parser("serve", help="Start the local HTTP API.")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8765)
    serve_parser.add_argument("--lazy", action="store_true", help="Load the model on first prediction.")
    serve_parser.set_defaults(func=command_serve)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
