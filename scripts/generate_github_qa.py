"""Generate question/answer data from a seeded GitHub repository."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from src.agent.github_tool import call_github_api


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--output", type=Path, default=Path("suites/github_qa.json"))
    args = parser.parse_args()

    issues = call_github_api(
        f"/repos/{args.repo}/issues",
        {"state": "all", "per_page": 10},
    )
    pull_requests = call_github_api(
        f"/repos/{args.repo}/pulls",
        {"state": "all", "per_page": 10},
    )
    real_issues = [issue for issue in issues if "pull_request" not in issue]
    open_issues = [issue for issue in real_issues if issue["state"] == "open"]
    closed_issues = [issue for issue in real_issues if issue["state"] == "closed"]

    def labeled(items: list[dict], name: str) -> list[dict]:
        return [
            item
            for item in items
            if any(label["name"].lower() == name for label in item["labels"])
        ]

    merged_prs = [pull for pull in pull_requests if pull["merged_at"] is not None]
    open_prs = [pull for pull in pull_requests if pull["state"] == "open"]
    closed_unmerged_prs = [
        pull
        for pull in pull_requests
        if pull["state"] == "closed" and pull["merged_at"] is None
    ]

    questions = [
        ("How many open issues are there, excluding pull requests?", len(open_issues)),
        ("How many closed issues are there, excluding pull requests?", len(closed_issues)),
        ("How many total issues are there, excluding pull requests?", len(real_issues)),
        ("How many issues have the bug label?", len(labeled(real_issues, "bug"))),
        ("How many issues have the question label?", len(labeled(real_issues, "question"))),
        ("How many pull requests are there in total?", len(pull_requests)),
        ("How many pull requests have been merged?", len(merged_prs)),
        ("How many pull requests are currently open?", len(open_prs)),
        ("How many pull requests are closed without being merged?", len(closed_unmerged_prs)),
        (
            "How many pull requests have titles beginning with 'Seed pull request'?",
            sum(pull["title"].startswith("Seed pull request") for pull in pull_requests),
        ),
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            [{"question": question, "expected_answer": answer} for question, answer in questions],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(questions, indent=2))


if __name__ == "__main__":
    main()
