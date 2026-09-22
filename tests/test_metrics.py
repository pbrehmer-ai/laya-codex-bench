import unittest

from laya_codex_bench.cascade_benchmark import tune_threshold
from laya_codex_bench.context_filter_benchmark import f1, recall
from laya_codex_bench.public_cases import _stratified_indices


class MetricTests(unittest.TestCase):
    def test_threshold_uses_only_accurate_coverage(self) -> None:
        rows = [
            {"confidence": 0.99, "correct": True},
            {"confidence": 0.90, "correct": True},
            {"confidence": 0.80, "correct": True},
            {"confidence": 0.70, "correct": False},
        ]
        policy = tune_threshold(rows, 0.95)
        self.assertEqual(3, policy["accepted"])
        self.assertAlmostEqual(0.8, policy["threshold"])

    def test_file_metrics(self) -> None:
        expected = {"a.py", "b.py"}
        self.assertEqual(1.0, recall({"a.py", "b.py", "c.py"}, expected))
        self.assertAlmostEqual(0.8, f1({"a.py", "b.py", "c.py"}, expected))

    def test_stratified_sampling_is_deterministic(self) -> None:
        labels = [0, 0, 0, 1, 1, 1]
        self.assertEqual(
            _stratified_indices(labels, 4, 7),
            _stratified_indices(labels, 4, 7),
        )
        selected = _stratified_indices(labels, 4, 7)
        self.assertEqual({0, 1}, {labels[index] for index in selected})


if __name__ == "__main__":
    unittest.main()
