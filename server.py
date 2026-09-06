"""FastAPI server for the web interface and current application state."""

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles


BASE_DIR = Path(__file__).resolve().parent
STATE_FILE = BASE_DIR / "state.json"
WEB_DIR = BASE_DIR / "web"

app = FastAPI()


@app.get("/api/state")
def get_state() -> JSONResponse:
    """Return the current parsed state without allowing browser caching."""
    with STATE_FILE.open(encoding="utf-8") as state_file:
        state = json.load(state_file)

    return JSONResponse(content=state, headers={"Cache-Control": "no-store"})


app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
