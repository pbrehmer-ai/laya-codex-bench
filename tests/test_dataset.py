from pathlib import Path
import unittest

from laya_codex_bench.dataset import load_tasks


ROOT = Path(__file__).resolve().parents[1]


class DatasetTests(unittest.TestCase):
    def test_pilot_dataset_is_valid_and_bilingual(self) -> None:
        tasks = load_tasks(ROOT / "datasets" / "pilot.jsonl")
        self.assertEqual(12, len(tasks))
        self.assertEqual({"de", "en"}, {task.language for task in tasks})
        self.assertGreaterEqual(sum(len(task.questions) for task in tasks), 25)


if __name__ == "__main__":
    unittest.main()

