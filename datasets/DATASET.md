# Dataset provenance

No previous synthetic pilot data remains in this repository.

## Public classification suites

The cascade harness downloads datasets into the ignored project-local Hugging Face cache.

| Suite | Hugging Face dataset | Source split | Role |
|---|---|---|---|
| `ag_news_retention` | `fancyzhx/ag_news` | `test` | Retention control; upstream Laya reports training overlap |
| `prompt_injections_heldout` | `deepset/prompt-injections` | `test` | Held-out generalization suite according to upstream Laya benchmark documentation |

Indices are stratified deterministically with seed `20260922`, then divided into disjoint development and test subsets. Dataset fingerprints are written into each report. Source texts are not copied into this repository.

## Repository-context tasks

`context-filter-tasks.json` contains six manually labelled semantic file-selection tasks against:

- repository: `https://github.com/NandhaKishorM/laya.git`
- commit: `573e5b62696ba441230cd6be71d593331b5d23af`

Three tasks are development tasks and three are held-out test tasks. The candidate set is generated from pinned Python source, tests, and research scripts. Expected paths are public repository paths, not private code.

## Limitations

- Forty classification test cases and three context-filter test tasks are sufficient for integration pilots, not universal rankings.
- AG News is intentionally disclosed as an upper-bound retention control.
- The manually labelled repository tasks should be expanded and independently reviewed before a confirmatory release.
