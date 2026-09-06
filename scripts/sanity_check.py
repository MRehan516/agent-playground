"""Validate persisted evaluation-round result files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def check_result(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        return [f"{path}: cannot read JSON ({error})"]

    round_data = result.get("round")
    tasks = result.get("tasks")
    if not isinstance(round_data, dict):
        errors.append(f"{path}: missing round object")
    if not isinstance(tasks, list) or len(tasks) != 10:
        errors.append(f"{path}: expected 10 tasks")
        return errors

    passed_count = 0
    for index, task in enumerate(tasks, start=1):
        for field in ("task_number", "question", "expected_answer", "answer", "passed", "status"):
            if field not in task:
                errors.append(f"{path}: task {index} missing {field}")
        if task.get("passed") is True:
            passed_count += 1
        expected_status = "passed" if task.get("passed") else "failed"
        if task.get("status") not in ("fail", expected_status):
            errors.append(f"{path}: task {index} has inconsistent status")

    if isinstance(round_data, dict):
        expected_rate = passed_count / len(tasks)
        if round_data.get("success_rate") != expected_rate:
            errors.append(f"{path}: success_rate does not match task results")

    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("results", nargs="+")
    args = parser.parse_args()
    errors = [error for name in args.results for error in check_result(Path(name))]
    if errors:
        print("SANITY CHECK: FAILED")
        print("\n".join(errors))
    else:
        print("SANITY CHECK: CLEAN")


if __name__ == "__main__":
    main()
