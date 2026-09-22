# Laya context-filter benchmark

Pinned source: `https://github.com/NandhaKishorM/laya.git` at `573e5b62696ba441230cd6be71d593331b5d23af`.

- Frozen Laya filter: `typed-decisions` at threshold `0.5326`
- Candidate files per task: `21`
- Laya filter input: `path + module docstring + top-level class/function names`
- Mean selection recall: **66.7%**
- Codex-token savings: **32.8%**
- Mean Codex F1, full context: **1.000**
- Mean Codex F1, Laya-filtered context: **0.733**
- Median end-to-end latency, full/filtered: **7251 / 26927 ms**
- Laya PID before/after: `24284` / `24284`

| Task | Files kept | Selection recall | Baseline F1 | Filtered F1 | Baseline tokens | Filtered tokens |
|---|---:|---:|---:|---:|---:|---:|
| model-download-loading | 13/21 | 100.0% | 1.000 | 0.800 | 75929 | 53567 |
| criteria-normalization | 14/21 | 50.0% | 1.000 | 0.400 | 76025 | 52043 |
| latency-benchmark | 11/21 | 50.0% | 1.000 | 1.000 | 75986 | 47525 |

> This is a three-task integration pilot. The development tasks selected the checkpoint
> and threshold. The test tasks were not used to tune the filter.
