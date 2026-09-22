from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    language: str
    category: str
    state: Any
    questions: dict[str, dict[str, Any]]
    expected: dict[str, list[str]]

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Task":
        required = {"id", "title", "language", "category", "state", "questions", "expected"}
        missing = required - value.keys()
        if missing:
            raise ValueError(f"Task is missing fields: {sorted(missing)}")
        task = cls(**{key: value[key] for key in required})
        task.validate()
        return task

    def validate(self) -> None:
        if not self.id or not self.questions:
            raise ValueError("Task id and questions must be non-empty")
        if set(self.questions) != set(self.expected):
            raise ValueError(f"{self.id}: expected keys must match question keys")
        for qid, question in self.questions.items():
            if question.get("type") not in {"choice", "score", "noul"}:
                raise ValueError(f"{self.id}/{qid}: unsupported question type")
            if not self.expected[qid]:
                raise ValueError(f"{self.id}/{qid}: expected answers must not be empty")


@dataclass(frozen=True)
class RunConfig:
    model: str
    reasoning_effort: str
    repetitions: int
    seed: int
    conditions: tuple[str, ...]
    dataset: str

