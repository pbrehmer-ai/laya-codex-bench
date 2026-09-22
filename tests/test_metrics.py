import unittest

from laya_codex_bench.metrics import build_summary, score_decisions


class MetricTests(unittest.TestCase):
    def test_decision_scoring(self) -> None:
        final = {"decisions": [{"id": "a", "value": "YES"}, {"id": "b", "value": "2"}]}
        correct, total = score_decisions(final, {"a": ["yes"], "b": ["1", "2"]})
        self.assertEqual((2, 2), (correct, total))

    def test_summary_pairs_by_task_and_repetition(self) -> None:
        base = {
            "task_id": "t1", "repetition": 1, "success": True, "correct": 1,
            "total_decisions": 1, "input_tokens": 100, "output_tokens": 10, "elapsed_ms": 1000,
        }
        rows = [
            {**base, "condition": "baseline"},
            {**base, "condition": "preflight", "input_tokens": 60, "elapsed_ms": 500},
        ]
        summary = build_summary(rows)
        self.assertEqual(40, summary["comparisons"]["preflight"]["mean_input_tokens_saved"])
        self.assertEqual(2, summary["comparisons"]["preflight"]["median_speedup"])


if __name__ == "__main__":
    unittest.main()

