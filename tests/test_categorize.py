from release_notes_agent.categorize import categorize, strip_prefix
from release_notes_agent.collector import Change


def test_conventional_prefixes():
    changes = [
        Change(title="feat: add webhook support"),
        Change(title="fix(api): handle null payloads"),
        Change(title="docs: update install guide"),
        Change(title="chore: bump deps"),
        Change(title="perf: cache token lookups"),
    ]
    sections = categorize(changes)
    assert [c.title for c in sections["Features"]] == ["feat: add webhook support"]
    assert [c.title for c in sections["Bug Fixes"]] == ["fix(api): handle null payloads"]
    assert [c.title for c in sections["Documentation"]] == ["docs: update install guide"]
    assert [c.title for c in sections["Maintenance"]] == ["chore: bump deps"]
    assert [c.title for c in sections["Performance"]] == ["perf: cache token lookups"]


def test_labels_beat_prefixes():
    change = Change(title="update parser", labels=["bug"])
    sections = categorize([change])
    assert change in sections["Bug Fixes"]


def test_breaking_change_bang():
    sections = categorize([Change(title="feat!: drop python 3.8")])
    assert "Breaking Changes" in sections

    sections = categorize([Change(title="feat(api)!: remove v1 endpoints")])
    assert "Breaking Changes" in sections


def test_uncategorized_goes_to_other():
    sections = categorize([Change(title="Improve error messages")])
    assert "Other Changes" in sections


def test_empty_sections_dropped():
    sections = categorize([Change(title="feat: one thing")])
    assert list(sections.keys()) == ["Features"]


def test_strip_prefix():
    assert strip_prefix("feat(api): add webhooks") == "Add webhooks"
    assert strip_prefix("fix: handle nulls") == "Handle nulls"
    assert strip_prefix("Plain title stays") == "Plain title stays"
