"""Persistent state helpers for agent runs."""

import json
import os
from pathlib import Path
from typing import Any


STATE_PATH = Path("state.json")


def _empty_state() -> dict[str, Any]:
    return {
        "round": 0,
        "total_rounds": 3,
        "tasks": [],
        "memory_lines": [],
        "round_results": [None, None, None],
    }


def write_state(partial_update: dict) -> None:
    """Merge an update into state.json and replace it atomically."""
    if STATE_PATH.exists():
        with STATE_PATH.open("r", encoding="utf-8") as state_file:
            state = json.load(state_file)
    else:
        state = _empty_state()

    state.update(partial_update)
    temporary_path = STATE_PATH.with_name(f"{STATE_PATH.name}.tmp")
    with temporary_path.open("w", encoding="utf-8") as state_file:
        json.dump(state, state_file, indent=2)
        state_file.write("\n")
        state_file.flush()
        os.fsync(state_file.fileno())
    os.replace(temporary_path, STATE_PATH)
