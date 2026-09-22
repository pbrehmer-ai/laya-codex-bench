# Laya context-filter benchmark

Pinned source: `https://github.com/NandhaKishorM/laya.git` at `573e5b62696ba441230cd6be71d593331b5d23af`.

- Frozen Laya filter: `typed-decisions` at threshold `0.5771`
- Candidate files per task: `21`
- Laya filter input: `one request per file over path + first 800 characters`
- Mean selection recall: **100.0%**
- Codex-token savings: **22.7%**
- Mean Codex F1, full context: **1.000**
- Mean Codex F1, Laya-filtered context: **1.000**
- Median end-to-end latency, full/filtered: **9746 / 34524 ms**
- Laya PID before/after: `24284` / `24284`

| Task | Files kept | Selection recall | Baseline F1 | Filtered F1 | Baseline tokens | Filtered tokens |
|---|---:|---:|---:|---:|---:|---:|
| model-download-loading | 11/21 | 100.0% | 1.000 | 1.000 | 76003 | 49336 |
| criteria-normalization | 15/21 | 100.0% | 1.000 | 1.000 | 76040 | 61747 |
| latency-benchmark | 16/21 | 100.0% | 1.000 | 1.000 | 75986 | 65157 |

> This is a three-task integration pilot. The development tasks selected the checkpoint
> and threshold. The test tasks were not used to tune the filter.
