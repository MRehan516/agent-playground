"""Classify failed evaluation cases and turn them into reusable lessons."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load credentials before importing other agent modules that may initialize clients.
load_dotenv()

from .memory import append_new_lessons, regenerate_prompt


LABELS = (
    "WRONG_ENDPOINT",
    "PAGINATION_MISSED",
    "INCLUDED_PRS_AS_ISSUES",
    "RATE_LIMITED_OR_UNAUTH",
    "MISCOUNTED",
    "OTHER",
)

_FALLBACK_LESSONS = {
    "WRONG_ENDPOINT": "Use the endpoint and filters that match the requested resource before counting results.",
    "PAGINATION_MISSED": "Follow every pagination page before counting GitHub results.",
    "INCLUDED_PRS_AS_ISSUES": "Exclude pull requests from issue counts by filtering items with a pull_request field.",
    "RATE_LIMITED_OR_UNAUTH": "Check authentication and rate-limit responses before trusting GitHub API results.",
    "MISCOUNTED": "Count the complete filtered result set carefully instead of relying on a partial or inferred count.",
    "OTHER": "Verify the API data and counting logic against the question before answering.",
}


def _fallback_classification(case: dict[str, Any]) -> tuple[str, str]:
    text = f"{case.get('question', '')} {case.get('answer', '')}".casefold()
    if "excluding pull requests" in text and "issue" in text:
        label = "INCLUDED_PRS_AS_ISSUES"
    elif "pull request" in text and any(term in text for term in ("total", "merged", "count")):
        label = "PAGINATION_MISSED"
    elif any(term in text for term in ("api returned 0", "no pull requests", "not found", "unauthorized")):
        label = "WRONG_ENDPOINT"
    elif any(term in text for term in ("count", "how many", "issues", "pull request")):
        label = "MISCOUNTED"
    else:
        label = "OTHER"
    return label, _FALLBACK_LESSONS[label]


def _parse_model_output(content: str) -> tuple[str, str]:
    label_match = re.search(r"\b(" + "|".join(LABELS) + r")\b", content.upper())
    if not label_match:
        raise ValueError(f"GPT-5 Nano returned no valid classification label: {content!r}")
    label = label_match.group(1)
    lesson = content[label_match.end():].strip(" \n:-")
    if not lesson:
        raise ValueError("GPT-5 Nano returned no lesson sentence")
    return label, lesson.splitlines()[0].strip()


def classify_failure(case: dict[str, Any]) -> tuple[str, str]:
    """Return one allowed bucket and one crisp lesson for a failed case."""
    failure = {
        "question": case.get("question"),
        "expected": case.get("expected_answer"),
        "actual": case.get("answer"),
        "tool_call_trace": case.get(
            "tool_call_trace",
            "unavailable in historical result; rerun the case to capture it",
        ),
    }
    print(json.dumps(failure, indent=2, ensure_ascii=False))
    api_key = os.getenv("GPT5NANO_API_KEY")
    if not api_key:
        print("TODO: swap in GPT-5 Nano when GPT5NANO_API_KEY arrives")
        return _fallback_classification(case)

    from openai import OpenAI

    print(os.environ.get('GPT5NANO_API_KEY'))
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-5-nano",
        messages=[
            {
                "role": "system",
                "content": (
                    "Classify the failed evaluation into exactly one label: "
                    + ", ".join(LABELS)
                    + ". Output exactly two lines: LABEL, then one crisp lesson sentence."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(failure, ensure_ascii=False),
            },
        ],
    )
    content = response.choices[0].message.content or ""
    return _parse_model_output(content)


def classify_round(round_path: str = "results/runs/round1.json") -> list[dict[str, Any]]:
    """Classify every failed case and persist its deduplicated lesson."""
    result = json.loads(Path(round_path).read_text(encoding="utf-8"))
    classified = []
    for case in result["tasks"]:
        if not case.get("passed", False):
            label, lesson = classify_failure(case)
            classified.append({**case, "label": label, "lesson": lesson})
    append_new_lessons([item["lesson"] for item in classified], added_round=1)
    return classified


def generate_system_prompt(
    source_path: str = "prompts/system_v1.md",
    target_path: str = "prompts/system_v2.md",
) -> None:
    """Create a prompt with every currently persisted lesson."""
    regenerate_prompt(source_path, target_path)
