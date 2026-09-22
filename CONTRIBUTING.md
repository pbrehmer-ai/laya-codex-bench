# Contributing

Contributions should preserve benchmark comparability and avoid result-driven prompt tuning.

1. Open an issue describing the proposed task family or metric.
2. Add or change fixtures only in development datasets until the next benchmark version is declared.
3. Run `python -m laya_codex_bench validate` and `python -m unittest discover -s tests -v`.
4. Never commit model files, credentials, private prompts, or raw Codex reasoning traces.
5. Document any change that affects prompts, model routing, scoring, or runtime configuration.

Benchmark-result pull requests must include the exact Git commit, CLI/model versions, hardware metadata, seed, repetitions, and an explicit statement of whether Laya was warm or cold.

