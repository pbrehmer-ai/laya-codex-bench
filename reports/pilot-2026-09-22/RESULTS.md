# Pilot benchmark results

> These are exploratory pilot results, not a general performance claim. The dataset,
> hardware, Codex model, reasoning effort, repetitions, and warm/cold state are part of
> the result and must be cited with any numbers below.

## Run metadata

- Timestamp: `20260922T064412Z`
- Dataset: `datasets\pilot.jsonl`
- Tasks: `12`
- Repetitions: `1`
- Codex CLI: `codex-cli 0.155.0-alpha.9.2`
- Codex model: `gpt-5.6-terra`
- Reasoning effort: `medium`
- Laya: `convaiinnovations/laya/multilingual` on `cpu`
- Laya PID before/after: `3592` / `3592`
- Persistent warm Laya service: `True`
- Warm-up inference: `331.52 ms`
- CPU: `Intel64 Family 6 Model 151 Stepping 5, GenuineIntel`
- RAM: `31.78 GB`

## Conditions

| Condition | Runs | Success | Accuracy | Median input | Median uncached input | Median output | Total Codex tokens | Median latency | p90 latency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 12 | 12 | 96.3% | 15912 | 1820 | 64 | 191816 | 6128 ms | 6739 ms |
| skill | 12 | 12 | 74.1% | 67130 | 5734 | 514 | 794116 | 19593 ms | 22413 ms |
| preflight | 12 | 12 | 59.3% | 15818 | 1739 | 48 | 190439 | 6261 ms | 8431 ms |

## Paired comparisons against direct Codex

### skill

- Paired runs: `12`
- Mean input tokens saved: `-49734.1`
- Median input tokens saved: `-51219.0`
- Median uncached input tokens saved: `-3976.0`
- Median total Codex tokens saved (input + output): `-51669.5`
- 95% bootstrap CI for mean input-token savings: `[-51322.8, -46641.5]`
- Median end-to-end speedup: `0.313x`
- 95% bootstrap CI for mean speedup: `[0.288, 0.335]x`

### preflight

- Paired runs: `12`
- Mean input tokens saved: `98.8`
- Median input tokens saved: `95.5`
- Median uncached input tokens saved: `93.5`
- Median total Codex tokens saved (input + output): `113.5`
- 95% bootstrap CI for mean input-token savings: `[89.2, 108.5]`
- Median end-to-end speedup: `0.973x`
- 95% bootstrap CI for mean speedup: `[0.844, 1.014]x`

## Interpretation rules

- Laya tokenizer counts are intentionally not added to Codex tokens; they are different tokenizers and local inference has no API-token charge.
- The skill condition includes Codex orchestration and tool-call overhead.
- The preflight condition is a production-style router and gives Codex only compact typed decisions, so it is not a fixed-context ablation.
- A lower token count is useful only when task success and decision accuracy remain acceptable.
- Raw event logs remain local because they may contain machine paths or model reasoning artifacts.
