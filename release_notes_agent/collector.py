"""Collect changes (merged PRs + commits) since the last release."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .github_client import GitHubClient


@dataclass
class Change:
    """A single unit of change — a merged PR, or a commit with no PR."""

    title: str
    number: Optional[int] = None  # PR number if it came from a PR
    author: Optional[str] = None
    labels: list[str] = field(default_factory=list)
    body: str = ""
    url: str = ""
    sha: Optional[str] = None


@dataclass
class ChangeSet:
    repo: str
    base_ref: Optional[str]  # tag/release we're diffing from (None = first release)
    head_ref: str
    changes: list[Change] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.changes


def collect_changes(
    client: GitHubClient,
    repo: str,
    base_ref: Optional[str] = None,
    head_ref: Optional[str] = None,
) -> ChangeSet:
    """Gather everything merged since the last release (or `base_ref` if given).

    Strategy: prefer merged PRs (they carry titles, labels, and descriptions);
    commits that didn't come through a PR are appended as plain changes.
    """
    head = head_ref or client.default_branch(repo)

    since_iso = None
    if base_ref is None:
        release = client.latest_release(repo)
        if release:
            base_ref = release["tag_name"]
            since_iso = release.get("published_at") or release.get("created_at")
        else:
            tag = client.latest_tag(repo)
            if tag:
                base_ref = tag["name"]

    commits = client.commits_since(repo, base_ref, head)
    commit_shas = {c["sha"] for c in commits}

    changes: list[Change] = []
    seen_shas: set[str] = set()

    prs = client.merged_prs_since(repo, since_iso)
    for pr in prs:
        merge_sha = pr.get("merge_commit_sha")
        # Only count PRs whose merge commit is actually in the diff range
        # (guards against PRs merged into other branches).
        if base_ref and merge_sha and merge_sha not in commit_shas:
            continue
        changes.append(
            Change(
                title=pr["title"].strip(),
                number=pr["number"],
                author=(pr.get("user") or {}).get("login"),
                labels=[l["name"] for l in pr.get("labels", [])],
                body=(pr.get("body") or "")[:2000],
                url=pr["html_url"],
                sha=merge_sha,
            )
        )
        if merge_sha:
            seen_shas.add(merge_sha)

    for c in commits:
        if c["sha"] in seen_shas:
            continue
        message = c["commit"]["message"].split("\n")[0].strip()
        # Skip merge-commit noise; the PR entry already covers it.
        if message.startswith("Merge pull request") or message.startswith("Merge branch"):
            continue
        changes.append(
            Change(
                title=message,
                author=(c.get("author") or {}).get("login")
                or c["commit"]["author"]["name"],
                url=c["html_url"],
                sha=c["sha"],
            )
        )

    return ChangeSet(repo=repo, base_ref=base_ref, head_ref=head, changes=changes)
