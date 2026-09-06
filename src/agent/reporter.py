"""Generate a before/after summary for evaluation rounds."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROUND_PATHS = (
    Path("results/runs/round1.json"),
    Path("results/runs/round2.json"),
    Path("results/runs/round3.json"),
)
STATE_PATH = Path("state.json")
OUTPUT_PATH = Path("results/before_after.md")


def _read_round(path: Path) -> dict[str, Any]:
    result = json.loads(path.read_text(encoding="utf-8"))
    summary = result.get("round")
    if not isinstance(summary, dict):
        raise ValueError(f"Missing round summary in {path}")
    required = ("round_name", "success_rate", "avg_tokens", "avg_latency")
    missing = [field for field in required if field not in summary]
    if missing:
        raise ValueError(f"Missing {', '.join(missing)} in {path}")
    return summary


def _lesson_counts(rounds: list[dict[str, Any]], state_path: Path) -> list[int]:
    state = json.loads(state_path.read_text(encoding="utf-8"))
    entries = state.get("memory_lines", [])
    counts = []
    for round_summary in rounds:
        round_number = int(round_summary["round_name"].removeprefix("round"))
        counts.append(
            sum(
                1
                for entry in entries
                if isinstance(entry, dict)
                and int(entry.get("added_round", round_number)) < round_number
            )
        )
    return counts


def build_report(
    round_paths: tuple[Path, ...] = ROUND_PATHS,
    state_path: Path = STATE_PATH,
) -> str:
    """Read round results and return the comparison report as Markdown."""
    rounds = [_read_round(path) for path in round_paths]
    lesson_counts = _lesson_counts(rounds, state_path)

    lines = [
        "# Before/after evaluation",
        "",
        "| Round | Success rate | Avg tokens | Avg latency (s) |",
        "|---|---:|---:|---:|",
    ]
    for summary in rounds:
        lines.append(
            f"| {summary['round_name']} | "
            f"{float(summary['success_rate']):.1%} | "
            f"{float(summary['avg_tokens']):.1f} | "
            f"{float(summary['avg_latency']):.2f} |"
        )
    counts = ", ".join(
        f"{summary['round_name']}: {count} lessons"
        for summary, count in zip(rounds, lesson_counts)
    )
    lines.extend(["", f"Lessons in memory.md after each round: {counts}.", ""])
    return "\n".join(lines)


def main() -> None:
    """Write the comparison report to the results directory."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(build_report(), encoding="utf-8")


if __name__ == "__main__":
    main()