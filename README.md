# Laya × Codex Bench

An open, reproducible benchmark for measuring whether a local [Laya](https://huggingface.co/convaiinnovations/laya) decision model reduces Codex token usage and end-to-end latency without hiding quality regressions.

This repository measures three concrete architectures:

1. **Direct Codex (`baseline`)** — Codex makes typed decisions itself.
2. **Laya as a Codex skill (`skill`)** — Codex invokes the local model through the read-only project MCP tool.
3. **Laya before Codex (`preflight`)** — Laya runs first and passes compact typed decisions to Codex.

The benchmark records Codex's own `turn.completed.usage` fields from `codex exec --json`; it does not estimate tokens from text length. Laya tokenizer counts stay separate because the tokenizers are not comparable.

> **Status:** experimental pilot harness. Pilot results validate the measurement pipeline but are not a universal performance claim.

## Published pilot result

The first 12-task, one-repetition pilot found **no production win under this setup**:

- the in-agent Laya skill used 51,669.5 more total Codex tokens per paired task at the median and was about 3.2× slower than direct Codex;
- external Laya preflight saved 113.5 total Codex tokens per paired task at the median, but had no demonstrated speed advantage and reduced exact decision accuracy from 96.3% to 59.3%;
- Laya remained warm in one process for the complete run (same PID before and after); its warm-up inference took 331.52 ms.

These numbers are an integration pilot, not a general claim about either model. Read the complete [pilot report](reports/pilot-2026-09-22/RESULTS.md), including confidence intervals and methodology, before citing them.

The separate [resource report](reports/resource-usage-2026-09-22.md) records the warm service's RAM, CPU, and inference-time measurements on the reference machine.

## Why this benchmark exists

System-1 decision models are often described as cheaper and faster than generative models, but that does not automatically mean they save tokens inside an agent workflow. A tool call can add orchestration overhead. A preflight router can save much more by avoiding an agent run or shrinking its context. This project measures both cases rather than assuming either outcome.

## Quick start on Windows

The project keeps Python, packages, model files, and caches inside the repository directory.

```powershell
.\scripts\setup.ps1
.\scripts\start-background.ps1
.\scripts\smoke-test.ps1
```

The deployed checkpoint is `convaiinnovations/laya/multilingual` on CPU. The first load takes roughly 20–30 seconds on the reference machine; warm predictions are much faster.

Validate the public pilot dataset and unit tests:

```powershell
.\.venv\Scripts\python.exe -m laya_codex_bench validate
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Run a small benchmark:

```powershell
.\.venv\Scripts\python.exe -m laya_codex_bench run `
  --dataset datasets/pilot.jsonl `
  --model gpt-5.6-terra `
  --reasoning-effort medium `
  --repetitions 1
```

Every Codex run is new and ephemeral. Conditions are shuffled with a recorded seed. Raw event streams stay ignored locally; derived CSV, JSON, and Markdown reports can be reviewed before publication.

## Measurements

For each run the harness records:

- Codex input, cached input, output, and reasoning-output tokens;
- complete `codex exec` wall-clock latency;
- Laya inference latency where applicable;
- command/tool use and whether Codex actually invoked Laya;
- exact-match decision accuracy against frozen labels;
- CLI/model/reasoning configuration and local hardware metadata.

Read [BENCHMARK_PROTOCOL.md](BENCHMARK_PROTOCOL.md) before interpreting results. The generated report explicitly distinguishes the fixed-input skill comparison from the production-style preflight comparison.

## Dataset

`datasets/pilot.jsonl` contains 12 original, manually labelled German and English fixtures across support, CI, security, privacy, sales, billing, account recovery, and moderation. They are realistic synthetic fixtures, not customer data and not scraped benchmark answers.

The pilot is for harness validation. A confirmatory release needs a larger frozen held-out dataset, at least three repetitions, confidence intervals, and a predeclared quality non-inferiority margin. See [datasets/DATASET.md](datasets/DATASET.md).

## Local API

Start or reuse the hidden persistent service:

```powershell
.\scripts\start-background.ps1
.\scripts\api-predict.ps1 -InputFile .\examples\ticket-de.json
```

Endpoints:

- `GET http://127.0.0.1:8765/health`
- `POST http://127.0.0.1:8765/predict`

The server binds only to localhost. Runtime logs and PID files are kept in the ignored `.runtime` directory.

The committed `.codex/config.toml` exposes `laya_predict` to Codex. It reuses the same localhost service and does not load a separate model for each call.

## Reproducibility and limitations

- Laya is a beta model. Its shipped probabilities require domain calibration before production automation.
- `laya-multilingual` has a finite context and option-token budget; large label sets are outside this pilot's scope.
- Codex is stochastic and remote latency varies. Report medians, paired differences, repetitions, and confidence intervals.
- Prompt caching is reported separately through `cached_input_tokens`.
- Preflight receives less Codex context by design and must not be described as a fixed-context model ablation.
- Results apply to the pinned software versions, model, reasoning effort, hardware, dataset, and warm/cold state shown in the report.

## Repository safety

Never commit `.runtime`, model weights, virtual environments, Hugging Face caches, API keys, Codex authentication, customer content, or unsanitized reasoning traces. Public CI performs only offline validation and unit tests.

## License

Apache-2.0. Laya is developed by Convai Innovations and distributed separately under Apache-2.0. This repository does not redistribute Laya model weights.
