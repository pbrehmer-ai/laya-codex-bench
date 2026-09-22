from __future__ import annotations

import json

from .models import Task


COMMON = """Return only the structured result required by the supplied JSON schema.
Do not edit project source files, browse the web, or perform unrelated work.
Each decision value must be a string. For noul questions use exactly \"true\" or \"false\".
For score questions use the nearest zero-based level index as a string.
Include every question id exactly once. Keep action_summary to one short sentence.
"""


def decision_packet(task: Task) -> str:
    return json.dumps(
        {"state": task.state, "questions": task.questions}, ensure_ascii=False, sort_keys=True
    )


def baseline_prompt(task: Task) -> str:
    return f"""{COMMON}
Condition: direct Codex baseline.
Make the decisions yourself from the packet. Do not use Laya, any local decision model,
or shell commands.

Decision packet:
{decision_packet(task)}
"""


def skill_prompt(task: Task) -> str:
    return f"""Condition: Laya called from inside Codex.
This is an instrumentation requirement, not a suggestion. Before producing the final JSON,
call the MCP tool laya.laya_predict exactly once, passing the state and questions from the
decision packet. The benchmark is invalid if no laya_predict tool event appears. Even when the
answer looks obvious, do not answer from your own judgment. Base every decision value on the
returned Laya answer and do not silently override it. The output schema constrains only the
final answer, not the intermediate tool call.

{COMMON}

Decision packet (identical semantic input to the baseline):
{decision_packet(task)}
"""


def preflight_prompt(task: Task, decisions: list[dict[str, str]]) -> str:
    compact = json.dumps(decisions, ensure_ascii=False, sort_keys=True)
    return f"""{COMMON}
Condition: external Laya preflight router.
The local decision model already evaluated the source state. Preserve these decisions exactly;
do not re-open or independently reclassify the original state.

Task title: {task.title}
Precomputed decisions:
{compact}
"""
