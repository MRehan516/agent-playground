"""Run evaluation rounds against the GitHub question-answering suite."""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
load_dotenv()

import neatlogs
from neatlogs import span

from .github_tool import call_github_api
from .state import write_state


neatlogs.init(
    api_key=os.environ["NEATLOGS_API_KEY"],
    workflow_name="github-agent",
    instrumentations=["openai"],
)


GITHUB_API_TOOL = {
    "type": "function",
    "function": {
        "name": "call_github_api",
        "description": "Call the GitHub REST API with an endpoint and query parameters.",
        "parameters": {
            "type": "object",
            "properties": {
                "endpoint": {"type": "string"},
                "params": {"type": "object"},
            },
            "required": ["endpoint", "params"],
            "additionalProperties": False,
        },
    },
}


def _answer_matches(answer: str, expected: Any) -> bool:
    if isinstance(expected, bool):
        return answer.strip().lower() == str(expected).lower()
    if isinstance(expected, (int, float)):
        return re.search(rf"(?<![\d.]){re.escape(str(expected))}(?![\d.])", answer) is not None
    return answer.strip().casefold() == str(expected).strip().casefold()


def _compact_tool_result(result: Any) -> Any:
    if not isinstance(result, list):
        return result
    fields = {"state", "labels", "pull_request", "merged_at", "title"}
    return [{key: item[key] for key in fields if key in item} for item in result]


def run_round(
    round_name: str,
    round_number: int,
    system_prompt_path: str,
    suite_path: str,
) -> dict[str, Any]:
    """Run every question in a suite and persist task and round results."""

    @span(kind='WORKFLOW', name=round_name)
    def _run() -> dict[str, Any]:
        # Import after telemetry initialization so the OpenAI instrumentation is active.
        from openai import OpenAI

        client = OpenAI(
            api_key=os.environ["TENSORMUX_API_KEY"],
            base_url="https://api.tensormux.com/v1",
        )
        system_prompt = Path(system_prompt_path).read_text(encoding="utf-8")
        suite = json.loads(Path(suite_path).read_text(encoding="utf-8"))
        repository = os.getenv("GITHUB_REPOSITORY", "MRehan516/agent-playground")
        task_results: list[dict[str, Any]] = []

        for task_number, task in enumerate(suite, start=1):
            question = task["question"]
            write_state(
                {
                    "round": round_number,
                    "tasks": [
                        *task_results,
                        {"task_number": task_number, "question": question, "status": "running"},
                    ],
                }
            )
            started = time.perf_counter()
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"{question}\nRepository: {repository}",
                },
            ]
            total_tokens = 0

            tool_calls_used = 0
            for _ in range(5):
                response = client.chat.completions.create(
                    model="glm-4-7-flash",
                    messages=messages,
                    tools=[GITHUB_API_TOOL],
                )
                if response.usage:
                    total_tokens += response.usage.total_tokens or 0
                message = response.choices[0].message
                if not message.tool_calls:
                    final_answer = message.content or ""
                    break

                tool_calls_used += len(message.tool_calls)
                if tool_calls_used > 5:
                    raise RuntimeError(f"Task {task_number} exceeded the five-call tool limit")
                messages.append(message.model_dump(exclude_none=True))
                for tool_call in message.tool_calls:
                    arguments = json.loads(tool_call.function.arguments)
                    result = call_github_api(
                        arguments["endpoint"],
                        arguments.get("params", {}),
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(_compact_tool_result(result)),
                        }
                    )
            else:
                raise RuntimeError(f"Task {task_number} exceeded the five-call tool limit")

            latency = time.perf_counter() - started
            passed = _answer_matches(final_answer, task["expected_answer"])
            task_result = {
                "task_number": task_number,
                "question": question,
                "expected_answer": task["expected_answer"],
                "answer": final_answer,
                "passed": passed,
                "status": "passed" if passed else "failed",
                "tokens_used": total_tokens,
                "latency": latency,
            }
            task_results.append(task_result)
            write_state({"tasks": task_results})

        success_rate = sum(task["passed"] for task in task_results) / len(task_results)
        round_result = {
            "round_name": round_name,
            "round_number": round_number,
            "success_rate": success_rate,
            "avg_tokens": sum(task["tokens_used"] for task in task_results) / len(task_results),
            "avg_latency": sum(task["latency"] for task in task_results) / len(task_results),
        }
        state_path = Path("state.json")
        if state_path.exists():
            state = json.loads(state_path.read_text(encoding="utf-8"))
            round_results = state.get("round_results", [None, None, None])
        else:
            round_results = [None, None, None]
        while len(round_results) <= round_number - 1:
            round_results.append(None)
        round_results[round_number - 1] = round_result
        write_state({"round_results": round_results})
        output_path = Path("results") / "runs" / f"{round_name}.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps({"round": round_result, "tasks": task_results}, indent=2) + "\n",
            encoding="utf-8",
        )
        return {"round": round_result, "tasks": task_results}

    return _run()