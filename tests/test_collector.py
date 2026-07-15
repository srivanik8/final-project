"""Collector tests using a fake GitHub client — no network calls."""

from release_notes_agent.collector import collect_changes


class FakeClient:
    def __init__(self, release=None, tag=None, commits=None, prs=None):
        self._release = release
        self._tag = tag
        self._commits = commits or []
        self._prs = prs or []

    def default_branch(self, repo):
        return "main"

    def latest_release(self, repo):
        return self._release

    def latest_tag(self, repo):
        return self._tag

    def commits_since(self, repo, base_ref, head_ref):
        return self._commits

    def merged_prs_since(self, repo, since_iso):
        return self._prs


def make_commit(sha, message, author="alice"):
    return {
        "sha": sha,
        "html_url": f"https://github.com/o/r/commit/{sha}",
        "author": {"login": author},
        "commit": {"message": message, "author": {"name": author}},
    }


def make_pr(number, title, merge_sha, author="alice", labels=()):
    return {
        "number": number,
        "title": title,
        "merge_commit_sha": merge_sha,
        "merged_at": "2026-07-01T00:00:00Z",
        "user": {"login": author},
        "labels": [{"name": l} for l in labels],
        "body": "some description",
        "html_url": f"https://github.com/o/r/pull/{number}",
    }


def test_prs_preferred_over_their_commits():
    commits = [make_commit("abc", "feat: thing"), make_commit("def", "unrelated direct push")]
    prs = [make_pr(7, "feat: thing", "abc")]
    client = FakeClient(
        release={"tag_name": "v1.0.0", "published_at": "2026-06-01T00:00:00Z"},
        commits=commits,
        prs=prs,
    )
    cs = collect_changes(client, "o/r")
    titles = [c.title for c in cs.changes]
    assert "feat: thing" in titles
    assert "unrelated direct push" in titles
    assert len(cs.changes) == 2  # PR commit not double-counted
    assert cs.base_ref == "v1.0.0"


def test_prs_outside_diff_range_excluded():
    commits = [make_commit("abc", "feat: in range")]
    prs = [make_pr(1, "feat: in range", "abc"), make_pr(2, "feat: other branch", "zzz")]
    client = FakeClient(
        release={"tag_name": "v1.0.0", "published_at": "2026-06-01T00:00:00Z"},
        commits=commits,
        prs=prs,
    )
    cs = collect_changes(client, "o/r")
    numbers = [c.number for c in cs.changes if c.number]
    assert numbers == [1]


def test_merge_commits_skipped():
    commits = [
        make_commit("abc", "Merge pull request #5 from o/feature"),
        make_commit("def", "fix: real change"),
    ]
    client = FakeClient(release=None, tag=None, commits=commits)
    cs = collect_changes(client, "o/r")
    assert [c.title for c in cs.changes] == ["fix: real change"]
    assert cs.base_ref is None  # first release


def test_falls_back_to_latest_tag_without_release():
    client = FakeClient(release=None, tag={"name": "v0.9.0"}, commits=[])
    cs = collect_changes(client, "o/r")
    assert cs.base_ref == "v0.9.0"
