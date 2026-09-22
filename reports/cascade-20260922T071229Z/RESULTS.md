# Laya-first cascade benchmark

> Public-data pilot. Thresholds and checkpoint selection were frozen on a disjoint
> development subset before the test subset was evaluated.

## Reproducibility

- Timestamp: `20260922T071229Z`
- Codex: `gpt-5.6-luna` / `low`
- Codex CLI: `codex-cli 0.155.0-alpha.9.2`
- Laya models resident: `multilingual, typed-decisions, english`
- Laya PID before/after: `24284` / `24284`
- Persistent service: `True`
- Development/test cases per suite: `40` / `20`

## Overall results

| Condition | Accuracy | Codex calls | Codex tokens | Median latency | p90 latency |
|---|---:|---:|---:|---:|---:|
| codex | 75.0% | 40 | 496584 | 4760 ms | 6239 ms |
| laya | 80.0% | 0 | 0 | 422 ms | 559 ms |
| cascade | 80.0% | 23 | 284869 | 4124 ms | 5833 ms |

- Codex-token savings: **42.6%**
- Avoided Codex calls: **42.5%**
- Mean end-to-end latency fell from **4893 ms to 3221 ms (34.2%)**; aggregate median latency fell **13.4%**
- Mean / median paired speedup: **4.875x / 0.954x**
- 95% bootstrap CI, mean tokens saved per case: `[3423.6, 7166.1]`
- 95% bootstrap CI, mean paired speedup: `[3.432, 6.381]x`
- 95% bootstrap CI, accuracy delta: `[0.0, 12.5]` percentage points

## Results by suite

| Suite | Codex accuracy | Cascade accuracy | Codex-token savings | Avoided calls |
|---|---:|---:|---:|---:|
| ag_news_retention | 70.0% | 80.0% | 85.0% | 85.0% |
| prompt_injections_heldout | 80.0% | 80.0% | 0.0% | 0.0% |

## Frozen development policies

| Suite | Checkpoint | Threshold | Dev coverage | Dev accepted accuracy |
|---|---|---:|---:|---:|
| ag_news_retention | typed-decisions | 0.3223 | 87.5% | 97.1% |
| prompt_injections_heldout | english | 1.0100 | 0.0% | n/a |

## Interpretation

- `laya` is a component comparison: accepted or not, it never spends Codex tokens.
- `cascade` uses Laya only above the development-selected confidence threshold and otherwise falls back to the same direct Codex decision used by the baseline.
- The mean speedup is dominated by locally accepted cases. The paired median below 1x shows that fallback cases pay a small Laya-routing overhead.
- AG News is explicitly a retention control because upstream reports training overlap.
- Prompt Injections is the held-out generalization suite.
- Raw Codex event streams stay local; this report publishes derived measurements and public dataset indices only.
