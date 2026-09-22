# Laya × Codex Bench

An open, reproducible benchmark for testing where a persistent local [Laya](https://huggingface.co/convaiinnovations/laya) decision service actually reduces Codex calls, tokens, and latency without hiding quality regressions.

The benchmark deliberately separates three architectures:

1. **Laya only** — a typed decision is completed locally; Codex is never started.
2. **Confidence-gated cascade** — Laya handles development-calibrated high-confidence cases and sends every other case to Codex.
3. **Context filter** — Laya selects relevant repository files before a clean Codex run.

Calling Laya from inside an already-running Codex turn is supported through MCP, but is an optional overhead ablation rather than the headline architecture.

## Current public-data results

The main 40-case cascade pilot used disjoint development and test subsets from AG News and Deepset Prompt Injections. All three Laya checkpoints were warmed in one persistent process before selection. Codex used `gpt-5.6-luna` at low reasoning effort.

| Metric | Direct Codex | Laya-only | Laya→Codex cascade |
|---|---:|---:|---:|
| Accuracy | 75.0% | 80.0% | 80.0% |
| Codex calls | 40 | 0 | 23 |
| Codex tokens | 496,584 | 0 | 284,869 |
| Median end-to-end latency | 4,760 ms | 422 ms | 4,124 ms |

The cascade avoided **42.5% of Codex calls** and **42.6% of Codex tokens**. Its observed accuracy was 5 percentage points higher; the paired bootstrap 95% interval was 0.0 to 12.5 points, so this pilot does not establish a general quality improvement.

Mean end-to-end latency fell **34.2%** (4,893 to 3,221 ms), and the aggregate median fell **13.4%**. The paired median speedup was only **0.954x** because the 57.5% fallback cases first pay Laya latency and then still call Codex; the much larger 4.875x mean is driven by locally accepted cases. Both figures are reported to avoid presenting one favorable latency statistic in isolation.

The result is heterogeneous: AG News, which upstream discloses as training-overlap retention data, saved 85%; the held-out prompt-injection suite met no 95%-accuracy development threshold and therefore correctly fell back to Codex for every test case.

Read the [complete cascade report](reports/cascade-20260922T071229Z/RESULTS.md) and the [combined findings](reports/2026-09-22-findings.md) before citing a number.

For the recommended multilingual-only service, the measured model/runtime increment was **1.93 GB private memory / 1.63 GB working set**, idle CPU was **0%**, and the 1/4/12-question probes took **112/532/2,408 ms**. See the [process-only resource report](reports/resource-usage-2026-09-22.md).

## Context-filter findings

On three held-out repository-navigation tasks over 21 candidate files:

- conservative full-content filtering saved **22.7% Codex tokens** while preserving mean Codex F1 at **1.000**, but was slower on this CPU;
- a compact serial symbol index saved **32.8%**, but mean Codex F1 fell to **0.733**;
- a single 21-question symbol batch saved **61.3%**, but mean Codex F1 fell to **0.667** and CPU latency increased sharply.

These ablations demonstrate the token mechanism and its cost: aggressive filtering can reproduce large token reductions, but those reductions are not useful when relevant files are dropped. The conservative mode remains the default.

## Quick start on Windows

Everything except the global Codex skill stays inside this repository.

```powershell
.\scripts\setup.ps1
.\scripts\start-background.ps1
.\scripts\smoke-test.ps1
```

The normal service keeps only the multilingual checkpoint warm. For benchmark checkpoint selection, start all three once:

```powershell
.\scripts\start-benchmark-service.ps1
```

Do not run both commands on the same port. The scripts reuse a healthy service and never start one model per request.

Run the public cascade benchmark:

```powershell
.\.venv\Scripts\python.exe -m laya_codex_bench `
  --dev-per-suite 40 `
  --test-per-suite 20 `
  --target-accuracy 0.95 `
  --model gpt-5.6-luna `
  --reasoning-effort low
```

Run the conservative repository-context benchmark:

```powershell
.\.venv\Scripts\python.exe -m laya_codex_bench.context_filter_benchmark `
  --filter-mode serial-content `
  --model gpt-5.6-luna `
  --reasoning-effort low
```

The other explicit ablations are `serial-symbol` and `batch-symbol`.

## What is measured

Codex usage comes directly from `codex exec --json` `turn.completed.usage` events:

- input and cached-input tokens;
- output and reasoning-output tokens;
- complete process wall time;
- structured-output success.

Laya reports its own inference time. Its tokenizer counts are never added to Codex token counts. The service PID is captured before and after each suite to prove that the same loaded process remained resident.

The public reports contain derived CSV/JSON only. Raw Codex events, prompts, local paths, model weights, caches, and authentication stay ignored locally.

## Important limitations

- These are integration pilots, not universal model rankings.
- AG News is a retention control, not held-out generalization.
- Prompt-injection quality is reported separately and is not hidden by the aggregate.
- Thresholds and checkpoint choice come only from development subsets.
- The i3-12100 CPU is not comparable to upstream Tesla T4 latency figures.
- Preloading all three checkpoints caused severe Windows memory commitment and paging; it is for checkpoint selection, not the recommended always-on configuration.
- A confirmatory claim needs more held-out tasks, at least three Codex repetitions, and a predeclared quality non-inferiority margin.

See [BENCHMARK_PROTOCOL.md](BENCHMARK_PROTOCOL.md) for the frozen protocol and [datasets/DATASET.md](datasets/DATASET.md) for provenance.

## Local API and Codex skill

The localhost service exposes:

- `GET http://127.0.0.1:8765/health`
- `POST http://127.0.0.1:8765/predict`

The committed `.codex/config.toml` exposes the read-only `laya_predict` MCP tool. The personal `$laya-local-decisions` skill prefers MCP when available and otherwise calls the localhost API. Both paths reuse the existing process.

## License

Apache-2.0. Laya is developed by Convai Innovations and distributed separately under Apache-2.0. This repository does not redistribute model weights or public benchmark datasets.
