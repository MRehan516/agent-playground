"""Re-grade stored answers without making LLM or GitHub requests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent.runner import _answer_matches


def main() -> None:
    result_path = Path("results/runs/round1.json")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    for task in result["tasks"]:
        task["passed"] = _answer_matches(
            task.get("answer", ""),
            task["expected_answer"],
        )
        task["status"] = "passed" if task["passed"] else "failed"

    tasks = result["tasks"]
    result["round"]["success_rate"] = sum(task["passed"] for task in tasks) / len(tasks)
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"success_rate={result['round']['success_rate']}")


if __name__ == "__main__":
    main()
