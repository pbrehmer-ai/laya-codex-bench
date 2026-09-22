# Laya context-filter benchmark

Pinned source: `https://github.com/NandhaKishorM/laya.git` at `573e5b62696ba441230cd6be71d593331b5d23af`.

- Frozen Laya filter: `english` at threshold `0.7243`
- Candidate files per task: `21`
- Laya filter input: `one batched request over path + module docstring + top-level class/function names`
- Mean selection recall: **66.7%**
- Codex-token savings: **61.3%**
- Mean Codex F1, full context: **0.933**
- Mean Codex F1, Laya-filtered context: **0.667**
- Median end-to-end latency, full/filtered: **8942 / 48060 ms**
- Laya PID before/after: `24284` / `24284`

| Task | Files kept | Selection recall | Baseline F1 | Filtered F1 | Baseline tokens | Filtered tokens |
|---|---:|---:|---:|---:|---:|---:|
| model-download-loading | 1/21 | 0.0% | 0.800 | 0.000 | 76008 | 15747 |
| criteria-normalization | 11/21 | 100.0% | 1.000 | 1.000 | 76076 | 38660 |
| latency-benchmark | 4/21 | 100.0% | 1.000 | 1.000 | 76016 | 33815 |

> This is a three-task integration pilot. The development tasks selected the checkpoint
> and threshold. The test tasks were not used to tune the filter.
