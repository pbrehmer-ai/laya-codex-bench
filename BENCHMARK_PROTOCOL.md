# Benchmark protocol

## Research question

How do local Laya decisions affect Codex token usage, end-to-end latency, and decision quality in realistic typed-decision workflows?

## Conditions

1. `baseline`: Codex receives the complete decision packet and decides directly. It is explicitly prohibited from using Laya.
2. `skill`: Codex receives the same semantic packet and must call `laya_predict` through the project-local, read-only MCP server. The installed `$laya-local-decisions` skill supplies the operating instructions.
3. `preflight`: the harness calls Laya before Codex and sends Codex only the task title and typed decision results. This is a production routing condition, not a fixed-context ablation.

The baseline/skill pair measures in-agent orchestration overhead. Baseline/preflight measures the production architecture that can reduce Codex context.

## Controlled variables

- Pin Codex CLI version, Codex model, and reasoning effort.
- Start every Codex run with `codex exec --ephemeral --json`.
- Use the same output schema and sandbox for all conditions.
- Randomize condition order with a recorded seed.
- Use a warm, persistent Laya server for headline measurements.
- Perform one unscored warm-up inference before scheduling runs, then record and compare the service PID before and after the suite.
- Record Laya cold-start measurements separately.
- Run conditions sequentially on the same machine.
- Never tune prompts, labels, or thresholds on confirmatory test results.

## Token accounting

Codex usage comes from the final `turn.completed` JSONL event:

- `input_tokens`
- `cached_input_tokens`
- `output_tokens`
- `reasoning_output_tokens`

Laya's tokenizer count is recorded separately and is never added to or subtracted from Codex tokens. The tokenizers have different vocabularies, and local Laya inference has no remote API-token charge.

## Timing

The harness measures wall-clock time around the complete `codex exec` process. The Laya service reports its own inference time. Results distinguish warm model inference from process/model cold start.

## Quality

Every returned decision is matched against frozen accepted labels. Token or latency improvements are not considered beneficial if success or decision accuracy becomes materially worse.

For future coding-task extensions, deterministic tests must be the primary quality signal. LLM-as-judge scoring may supplement but not replace executable checks.

## Statistics

- Report totals, medians, p90 latency, and paired per-task deltas.
- Report bootstrap 95% confidence intervals over paired task-level differences.
- Keep pilot and confirmatory reports separate.
- A public headline requires at least three repetitions on a frozen held-out set and a predeclared non-inferiority margin for quality.

## Publication rules

- Include hardware, OS, Codex CLI version, model, reasoning effort, dataset revision, repetitions, and seed.
- Publish derived CSV/JSON and the prompts needed to reproduce the run.
- Do not publish credentials, private customer data, raw reasoning, or unsanitized event streams.
- Describe synthetic fixtures as realistic fixtures, not as production traffic.
