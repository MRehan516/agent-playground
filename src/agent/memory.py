"""Persistent lessons learned from evaluation rounds."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .state import write_state


MEMORY_PATH = Path("memory.md")


def read_lessons() -> list[str]:
    """Return non-empty lesson lines, preserving their file order."""
    if not MEMORY_PATH.exists():
        return []
    return [
        line.strip()
        for line in MEMORY_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def regenerate_prompt(
    source_path: str = "prompts/system_v1.md",
    target_path: str = "prompts/system_v2.md",
) -> None:
    """Write system_v2 with the literal contents of memory.md inline."""
    source = Path(source_path).read_text(encoding="utf-8").rstrip()
    memory_text = MEMORY_PATH.read_text(encoding="utf-8").strip() if MEMORY_PATH.exists() else ""
    section = "\n\n## Lessons from previous attempts\n"
    Path(target_path).write_text(source + section + memory_text + "\n", encoding="utf-8")


def append_new_lessons(lessons: list[str], added_round: int) -> list[dict[str, Any]]:
    """Append unique lessons and record each new line in persistent state."""
    existing = read_lessons()
    known = set(existing)
    new_lessons = []
    for lesson in lessons:
        normalized = lesson.strip()
        if normalized and normalized not in known:
            new_lessons.append(normalized)
            known.add(normalized)

    all_lessons = list(dict.fromkeys([*existing, *new_lessons]))
    MEMORY_PATH.write_text("\n".join(all_lessons) + ("\n" if all_lessons else ""), encoding="utf-8")

    entries = [
        {"lesson": lesson, "is_new": True, "added_round": added_round}
        for lesson in new_lessons
    ]
    state_path = Path("state.json")
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        memory_lines = state.get("memory_lines", [])
    else:
        memory_lines = []
    unique_state_entries = []
    state_lessons = set()
    for entry in [*memory_lines, *entries]:
        lesson = entry.get("lesson") if isinstance(entry, dict) else entry
        if lesson and lesson not in state_lessons:
            unique_state_entries.append(entry)
            state_lessons.add(lesson)
    write_state({"memory_lines": unique_state_entries})
    return entries
