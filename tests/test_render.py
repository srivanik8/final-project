from release_notes_agent.collector import Change, ChangeSet
from release_notes_agent.render import (
    changes_digest,
    render_linkedin,
    render_notes,
    render_tweet,
)


def sample_changeset() -> ChangeSet:
    return ChangeSet(
        repo="octo/widget",
        base_ref="v1.0.0",
        head_ref="main",
        changes=[
            Change(title="feat: add dark mode", number=42, author="alice"),
            Change(title="fix: crash on empty config", number=43, author="bob"),
            Change(title="docs: rewrite quickstart", number=44, author="alice"),
        ],
    )


def test_render_notes_structure():
    notes = render_notes(sample_changeset(), "v1.1.0")
    assert notes.startswith("# v1.1.0")
    assert "## ✨ Features" in notes
    assert "Add dark mode (#42) @alice" in notes
    assert "## 🐛 Bug Fixes" in notes
    assert "@alice, @bob" in notes  # contributors, deduped


def test_tweet_fits_and_links():
    tweet = render_tweet(sample_changeset(), "v1.1.0")
    assert len(tweet) <= 280
    assert "v1.1.0" in tweet
    assert "https://github.com/octo/widget/releases" in tweet


def test_linkedin_mentions_highlights():
    post = render_linkedin(sample_changeset(), "v1.1.0")
    assert "widget v1.1.0" in post
    assert "Add dark mode" in post
    # maintenance/other noise should not appear
    assert "chore" not in post.lower()


def test_digest_includes_pr_metadata():
    digest = changes_digest(sample_changeset())
    assert "[Features]" in digest
    assert "PR #42 by @alice" in digest
