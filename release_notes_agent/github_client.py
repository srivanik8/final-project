"""Minimal GitHub REST API client.

Only the endpoints this agent needs — no heavy SDK dependency.
Authentication is via a token (GITHUB_TOKEN in Actions, or a PAT locally).
"""

from __future__ import annotations

import time
from typing import Any, Iterator, Optional

import requests

API_ROOT = "https://api.github.com"


class GitHubError(RuntimeError):
    pass


class GitHubClient:
    def __init__(self, token: Optional[str] = None, api_root: str = API_ROOT):
        self.api_root = api_root.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "release-notes-agent",
            }
        )
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    def _get(self, path: str, params: Optional[dict] = None) -> Any:
        url = path if path.startswith("http") else f"{self.api_root}{path}"
        for attempt in range(4):
            resp = self.session.get(url, params=params, timeout=30)
            # Retry on secondary rate limits / transient server errors
            if resp.status_code in (403, 429) and "rate limit" in resp.text.lower():
                wait = int(resp.headers.get("Retry-After", 2 ** (attempt + 1)))
                time.sleep(wait)
                continue
            if resp.status_code >= 500:
                time.sleep(2 ** (attempt + 1))
                continue
            if resp.status_code == 404:
                return None
            if not resp.ok:
                raise GitHubError(f"GitHub API {resp.status_code} for {url}: {resp.text[:300]}")
            return resp.json()
        raise GitHubError(f"GitHub API kept failing for {url}")

    def _paginate(self, path: str, params: Optional[dict] = None) -> Iterator[dict]:
        params = dict(params or {})
        params.setdefault("per_page", 100)
        page = 1
        while True:
            params["page"] = page
            batch = self._get(path, params)
            if not batch:
                return
            yield from batch
            if len(batch) < params["per_page"]:
                return
            page += 1

    # --- endpoints ---------------------------------------------------------

    def latest_release(self, repo: str) -> Optional[dict]:
        """Most recent published release, or None if the repo has never released."""
        return self._get(f"/repos/{repo}/releases/latest")

    def latest_tag(self, repo: str) -> Optional[dict]:
        tags = self._get(f"/repos/{repo}/tags", {"per_page": 1})
        return tags[0] if tags else None

    def default_branch(self, repo: str) -> str:
        info = self._get(f"/repos/{repo}")
        if info is None:
            raise GitHubError(f"Repository not found: {repo}")
        return info["default_branch"]

    def commits_since(self, repo: str, base_ref: Optional[str], head_ref: str) -> list[dict]:
        """Commits between base_ref and head_ref (or the whole history if no base)."""
        if base_ref:
            cmp = self._get(f"/repos/{repo}/compare/{base_ref}...{head_ref}")
            return cmp.get("commits", []) if cmp else []
        return list(self._paginate(f"/repos/{repo}/commits", {"sha": head_ref}))

    def merged_prs_since(self, repo: str, since_iso: Optional[str]) -> list[dict]:
        """Merged PRs, newest first, optionally cut off at a timestamp."""
        merged = []
        for pr in self._paginate(
            f"/repos/{repo}/pulls",
            {"state": "closed", "sort": "updated", "direction": "desc"},
        ):
            if not pr.get("merged_at"):
                continue
            if since_iso and pr["merged_at"] <= since_iso:
                # PRs are sorted by update time, not merge time, so keep
                # scanning a bit; old merges can still appear late.
                continue
            merged.append(pr)
        return merged
