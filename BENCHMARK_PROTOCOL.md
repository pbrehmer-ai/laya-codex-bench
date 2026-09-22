# Benchmark protocol

## Research questions

1. How many complete Codex calls and Codex tokens can a confidence-gated local Laya cascade avoid?
2. Does the resulting pipeline remain within a predeclared decision-quality target?
3. Can Laya reduce repository context before Codex without removing required evidence?
4. What CPU, memory, and latency cost does the persistent local service add?

## Conditions

### Component and cascade

- `codex`: every test item receives one clean, ephemeral Codex structured-output run.
- `laya`: the selected local checkpoint decides without Codex.
- `cascade`: Laya is accepted only above a threshold chosen on the development split; all other cases reuse the same direct-Codex decision as the baseline.

The cascade is evaluated as a production policy. It does not start Codex merely to repeat an accepted Laya answer.

### Repository context

- `full-context`: Codex receives every candidate file.
- `laya-filtered`: a frozen Laya policy chooses files first; Codex receives complete content only for selected files.
- `serial-content`, `serial-symbol`, and `batch-symbol` are explicit engineering ablations.

## Frozen selection policy

For every public-data suite:

1. Evaluate English, multilingual, and typed-decisions checkpoints on the development subset.
2. Select the checkpoint with highest development accuracy; use median inference latency only as a tie-breaker.
3. Choose the threshold with greatest coverage that reaches 95% accepted-case development accuracy with at least three accepted cases.
4. If no threshold qualifies, set it above 1.0 and route every test item to Codex.
5. Do not revise checkpoint, prompt, or threshold after reading test outcomes.

For repository filtering, development tasks select checkpoint and threshold with perfect development recall first, then F1 and selected fraction. Test-task recall and downstream Codex F1 are both reported.

## Controls

- Use public dataset IDs and a fixed seed.
- Keep development and test indices disjoint.
- Start Codex with `--ephemeral --json --ignore-user-config --ignore-rules` and a strict output schema.
- Prohibit tools, skills, web search, and Laya inside the direct Codex classification prompt.
- Record exact CLI model and reasoning effort.
- Interleave conditions when independent calls are necessary.
- Warm Laya before measurement and record service PID before and after.
- Keep cold-start time separate.

## Token accounting

Codex tokens are read from `turn.completed.usage`. Primary totals are input plus output tokens. Cached-input and reasoning-output tokens remain separate columns. A locally computed Laya token count is not comparable and is not added.

Cascade token savings are:

`1 - cascade Codex tokens / direct-Codex tokens`

Accepted local cases consume zero Codex tokens. Fallback cases consume the paired direct-Codex usage.

## Quality

- Classification: exact accuracy by suite and overall.
- Context filtering: selection recall and downstream file-list F1.
- Report component, cascade, and baseline quality separately.
- A token reduction is not considered useful if it violates the frozen quality target.
- Confidence is a routing signal to validate, not proof of correctness.

## Statistics

- Report totals, medians, p90 latency, avoided-call rate, and paired deltas.
- Use a fixed-seed paired bootstrap with 5,000 samples for 95% intervals.
- Keep retention controls separate from held-out suites.
- The current reports are pilots. A confirmatory release requires at least three Codex repetitions and substantially more held-out tasks.

## Publication and safety

- Publish source dataset identities, fingerprints, indices, prompts, schemas, code, derived rows, and environment metadata.
- Do not publish model reasoning events, credentials, customer data, local authentication, caches, or model weights.
- Record failed runs instead of silently dropping them.
- Never tune on the test split.
