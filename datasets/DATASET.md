# Pilot dataset

The pilot dataset contains 12 original, manually labelled decision scenarios across support, CI, security, privacy, sales, billing, account recovery, and moderation. They are realistic fixtures, not copied customer records or scraped GitHub issues.

Each JSONL row contains:

- a stable task id and category;
- a state document in German or English;
- typed Laya questions (`choice`, `score`, or `noul`);
- one or more accepted ground-truth values for every question.

The pilot is deliberately small. It verifies the harness and reveals obvious quality or orchestration failures. It is not large enough for a general claim about Codex or Laya. A confirmatory benchmark must freeze a larger held-out test set before collecting headline results.

Ground truth was assigned from explicit textual evidence. Ambiguous values should be represented by multiple accepted values rather than retroactively changing labels after seeing model output.

