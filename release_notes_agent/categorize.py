"""Bucket changes into release-note sections.

Two signals, in priority order:
1. PR labels (maintainers' explicit intent)
2. Conventional-commit prefixes in the title (feat:, fix:, docs:, ...)
"""

from __future__ import annotations

import re

from .collector import Change

# Section name -> (label names, title prefixes)
CATEGORIES: dict[str, tuple[set[str], set[str]]] = {
    "Breaking Changes": ({"breaking", "breaking-change"}, {"feat!", "fix!", "refactor!"}),
    "Features": ({"feature", "enhancement", "feat"}, {"feat"}),
    "Bug Fixes": ({"bug", "fix", "bugfix"}, {"fix", "hotfix"}),
    "Performance": ({"performance", "perf"}, {"perf"}),
    "Documentation": ({"documentation", "docs"}, {"docs", "doc"}),
    "Maintenance": (
        {"chore", "dependencies", "ci", "refactor", "maintenance"},
        {"chore", "ci", "build", "refactor", "test", "style", "deps"},
    ),
}

OTHER = "Other Changes"

_PREFIX_RE = re.compile(r"^(?P<type>[a-zA-Z]+!?)(\([^)]*\))?!?\s*:")


def _title_prefix(title: str) -> str | None:
    m = _PREFIX_RE.match(title)
    if not m:
        return None
    t = m.group("type").lower()
    # "feat(api)!:" → breaking marker can sit after the scope too
    if "!" in title.split(":")[0]:
        t = t.rstrip("!") + "!"
    return t


def categorize(changes: list[Change]) -> dict[str, list[Change]]:
    """Return {section: [changes]} preserving CATEGORIES order, OTHER last."""
    sections: dict[str, list[Change]] = {name: [] for name in CATEGORIES}
    sections[OTHER] = []

    for change in changes:
        placed = False
        labels = {l.lower() for l in change.labels}
        prefix = _title_prefix(change.title)

        for name, (cat_labels, cat_prefixes) in CATEGORIES.items():
            if labels & cat_labels or (prefix and prefix in cat_prefixes):
                sections[name].append(change)
                placed = True
                break
        if not placed:
            sections[OTHER].append(change)

    return {name: items for name, items in sections.items() if items}


def strip_prefix(title: str) -> str:
    """'feat(api): add webhooks' → 'Add webhooks'."""
    cleaned = _PREFIX_RE.sub("", title).strip()
    return cleaned[:1].upper() + cleaned[1:] if cleaned else title
