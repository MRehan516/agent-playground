"""Small helpers for querying the GitHub REST API."""

from __future__ import annotations

import os
import re
from typing import Any

import requests


API_ROOT = "https://api.github.com"


def call_github_api(endpoint: str, params: dict) -> dict:
    """Call a GitHub endpoint and merge all pages for list responses."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN must be set")

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    endpoint = endpoint.rstrip("/")
    endpoint = endpoint.replace("/issues/pulls", "/pulls")
    if endpoint == "/search/pulls":
        search_params = params if isinstance(params, dict) else {}
        endpoint = "/search/issues"
        params = {**search_params, "q": f"{search_params.get('q', '')} type:pr"}
    label_match = re.match(r"^(?P<issues>/repos/[^/]+/[^/]+/issues)/labels/(?P<label>[^/]+)$", endpoint)
    if label_match:
        endpoint = label_match.group("issues")
        params = {**(params if isinstance(params, dict) else {}), "labels": label_match.group("label")}
    url = f"{API_ROOT}/{endpoint.lstrip('/')}"
    request_params = dict(params) if isinstance(params, dict) else {}
    if endpoint.endswith("/issues"):
        request_params.pop("type", None)
    response = requests.get(url, headers=headers, params=request_params)
    response.raise_for_status()
    result: Any = response.json()

    if not isinstance(result, list):
        return result

    items = result
    while response.links.get("next"):
        response = requests.get(
            response.links["next"]["url"],
            headers=headers,
        )
        response.raise_for_status()
        page = response.json()
        if not isinstance(page, list):
            raise TypeError("GitHub pagination returned a non-list page")
        items.extend(page)

    return items