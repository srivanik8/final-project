"""Deterministic (no-LLM) rendering of release notes and social posts.

Used as the fallback when no ANTHROPIC_API_KEY is available, and as the
structured input we hand to Claude for polishing.
"""

from __future__ import annotations

from .categorize import categorize, strip_prefix
from .collector import ChangeSet

SECTION_EMOJI = {
    "Breaking Changes": "⚠️",
    "Features": "✨",
    "Bug Fixes": "🐛",
    "Performance": "⚡",
    "Documentation": "📚",
    "Maintenance": "🔧",
    "Other Changes": "📦",
}


def render_notes(changeset: ChangeSet, version: str) -> str:
    """Plain markdown release notes built purely from PR/commit metadata."""
    lines = [f"# {version}", ""]
    if changeset.base_ref:
        lines.append(
            f"Changes since [`{changeset.base_ref}`]"
            f"(https://github.com/{changeset.repo}/compare/{changeset.base_ref}...{version})"
        )
        lines.append("")

    contributors: list[str] = []
    for section, changes in categorize(changeset.changes).items():
        emoji = SECTION_EMOJI.get(section, "")
        lines.append(f"## {emoji} {section}".strip())
        lines.append("")
        for c in changes:
            entry = f"- {strip_prefix(c.title)}"
            if c.number:
                entry += f" (#{c.number})"
            if c.author:
                entry += f" @{c.author}"
                if c.author not in contributors:
                    contributors.append(c.author)
            lines.append(entry)
        lines.append("")

    if contributors:
        lines.append("## 🙌 Contributors")
        lines.append("")
        lines.append(", ".join(f"@{a}" for a in contributors))
        lines.append("")

    return "\n".join(lines)


def render_tweet(changeset: ChangeSet, version: str) -> str:
    sections = categorize(changeset.changes)
    features = sections.get("Features", [])
    fixes = sections.get("Bug Fixes", [])
    repo_name = changeset.repo.split("/")[-1]

    highlight = ""
    if features:
        highlight = strip_prefix(features[0].title)
    elif fixes:
        highlight = strip_prefix(fixes[0].title)

    parts = [f"🚀 {repo_name} {version} is out!"]
    if highlight:
        parts.append(f"Highlight: {highlight}.")
    stats = []
    if features:
        stats.append(f"{len(features)} new feature{'s' if len(features) != 1 else ''}")
    if fixes:
        stats.append(f"{len(fixes)} fix{'es' if len(fixes) != 1 else ''}")
    if stats:
        parts.append(" + ".join(stats) + ".")
    parts.append(f"https://github.com/{changeset.repo}/releases")
    return " ".join(parts)[:280]


def render_linkedin(changeset: ChangeSet, version: str) -> str:
    sections = categorize(changeset.changes)
    repo_name = changeset.repo.split("/")[-1]
    lines = [
        f"We just shipped {repo_name} {version} 🎉",
        "",
        "What's new:",
    ]
    for section, changes in sections.items():
        if section in ("Maintenance", "Other Changes"):
            continue
        for c in changes[:3]:
            lines.append(f"• {strip_prefix(c.title)}")
    lines += [
        "",
        f"Full release notes: https://github.com/{changeset.repo}/releases",
        "",
        "#opensource #release #software",
    ]
    return "\n".join(lines)


def changes_digest(changeset: ChangeSet) -> str:
    """Compact plaintext digest of the raw changes — the input we give Claude."""
    out = []
    for section, changes in categorize(changeset.changes).items():
        out.append(f"[{section}]")
        for c in changes:
            line = f"- {c.title}"
            if c.number:
                line += f" (PR #{c.number} by @{c.author})"
            out.append(line)
            if c.body:
                first_para = c.body.strip().split("\n\n")[0][:400]
                out.append(f"  description: {first_para}")
    return "\n".join(out)
