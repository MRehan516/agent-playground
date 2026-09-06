"""Seed a GitHub repository with representative issues and pull requests."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from typing import Any

import requests
from dotenv import load_dotenv


API_ROOT = "https://api.github.com"
ISSUE_COUNT = 40
PR_COUNT = 15


def repository_from_remote() -> str:
    remote = subprocess.check_output(
        ["git", "config", "--get", "remote.origin.url"],
        text=True,
    ).strip()
    match = re.search(r"github\.com[:/]([^/]+/[^/.]+?)(?:\.git)?$", remote)
    if not match:
        raise RuntimeError("Could not determine the GitHub repository from origin")
    return match.group(1)


def github_request(
    session: requests.Session,
    method: str,
    path: str,
    **kwargs: Any,
) -> dict[str, Any]:
    response = session.request(method, f"{API_ROOT}{path}", **kwargs)
    if not response.ok:
        raise RuntimeError(
            f"GitHub API {method} {path} failed ({response.status_code}): "
            f"{response.text[:500]}"
        )
    return response.json() if response.content else {}


def seed_repository(repository: str, token: str) -> None:
    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
    )
    repo = github_request(session, "GET", f"/repos/{repository}")
    default_branch = repo["default_branch"]
    base = github_request(
        session, "GET", f"/repos/{repository}/git/ref/heads/{default_branch}"
    )["object"]["sha"]

    labels = {"bug", "question"}
    existing_labels = {
        label["name"].lower()
        for label in github_request(session, "GET", f"/repos/{repository}/labels")
    }
    for label in labels - existing_labels:
        github_request(
            session,
            "POST",
            f"/repos/{repository}/labels",
            json={"name": label, "color": "B60205" if label == "bug" else "D4C5F9"},
        )

    for index in range(1, ISSUE_COUNT + 1):
        issue = {
            "title": f"Seed issue {index:02d}",
            "body": (
                "Synthetic seed issue for exercising issue triage and memory "
                f"workflows. Record {index:02d}."
            ),
        }
        if index % 4 == 0:
            issue["labels"] = ["bug"]
        elif index % 7 == 0:
            issue["labels"] = ["question"]
        created = github_request(session, "POST", f"/repos/{repository}/issues", json=issue)
        if index % 3 == 0:
            github_request(
                session,
                "PATCH",
                f"/repos/{repository}/issues/{created['number']}",
                json={"state": "closed"},
            )

    for index in range(1, PR_COUNT + 1):
        branch = f"seed/pr-{index:02d}"
        path = f"seed-data/pull-request-{index:02d}.md"
        content = (
            f"Seed pull request {index:02d}\n\n"
            "This file exists to provide realistic pull request history.\n"
        )
        import base64

        github_request(
            session,
            "POST",
            f"/repos/{repository}/git/refs",
            json={"ref": f"refs/heads/{branch}", "sha": base},
        )
        github_request(
            session,
            "PUT",
            f"/repos/{repository}/contents/{path}",
            json={
                "message": f"Add seed pull request {index:02d} content",
                "content": base64.b64encode(content.encode()).decode(),
                "branch": branch,
            },
        )
        pull = github_request(
            session,
            "POST",
            f"/repos/{repository}/pulls",
            json={
                "title": f"Seed pull request {index:02d}",
                "body": "Synthetic seed pull request for workflow testing.",
                "head": branch,
                "base": default_branch,
            },
        )
        if index <= 5:
            github_request(
                session,
                "PUT",
                f"/repos/{repository}/pulls/{pull['number']}/merge",
                json={"merge_method": "merge"},
            )
        elif index <= 10:
            github_request(
                session,
                "PATCH",
                f"/repos/{repository}/pulls/{pull['number']}",
                json={"state": "closed"},
            )


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY"))
    args = parser.parse_args()
    repository = args.repo or repository_from_remote()
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN must be set to seed the repository")
    seed_repository(repository, token)
    print(f"Created {ISSUE_COUNT} issues and {PR_COUNT} pull requests in {repository}.")


if __name__ == "__main__":
    main()
