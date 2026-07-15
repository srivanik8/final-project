"""Claude-powered summarization of the collected changes.

Falls back to the deterministic renderer when no API key is configured,
so the action always produces output.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from .collector import ChangeSet
from .render import changes_digest, render_linkedin, render_notes, render_tweet

MODEL = "claude-opus-4-8"

SYSTEM_PROMPT = """\
You are a release-notes writer for open-source projects. You receive a digest
of merged pull requests and commits, and produce polished, human-readable
release material. Write for the project's users, not its developers: lead with
what changed for them and why it matters, not with implementation details.
Never invent changes that are not in the digest. Keep contributor credits.
"""

USER_PROMPT = """\
Repository: {repo}
New version: {version}
Previous release: {base}

Change digest (grouped, raw titles from PRs/commits):
{digest}

Produce three pieces of content and return them as a single JSON object with
exactly these keys:

- "release_notes": Markdown release notes. Structure: a 1-3 sentence summary
  paragraph of the release as a whole, then sections (## headings) for the
  categories that have content, with rewritten human-readable bullet points.
  Keep PR numbers like (#123) and @author credits on each bullet. If there are
  breaking changes, put that section first with clear migration guidance.
- "tweet": A tweet (max 280 chars) announcing the release. Enthusiastic but
  not clickbait. Include the version and one concrete highlight. End with
  {release_url}
- "linkedin": A LinkedIn post (3-6 short paragraphs or bullets). Slightly more
  professional tone, aimed at engineers evaluating the project. Mention what
  the project does in one line for readers who don't know it.
"""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "release_notes": {"type": "string"},
        "tweet": {"type": "string"},
        "linkedin": {"type": "string"},
    },
    "required": ["release_notes", "tweet", "linkedin"],
    "additionalProperties": False,
}


@dataclass
class ReleaseContent:
    release_notes: str
    tweet: str
    linkedin: str
    generated_by: str  # "claude" or "template"


def _template_content(changeset: ChangeSet, version: str) -> ReleaseContent:
    return ReleaseContent(
        release_notes=render_notes(changeset, version),
        tweet=render_tweet(changeset, version),
        linkedin=render_linkedin(changeset, version),
        generated_by="template",
    )


def summarize(changeset: ChangeSet, version: str) -> ReleaseContent:
    """Draft release content with Claude; fall back to templates without a key."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return _template_content(changeset, version)

    import anthropic

    client = anthropic.Anthropic()
    prompt = USER_PROMPT.format(
        repo=changeset.repo,
        version=version,
        base=changeset.base_ref or "(first release)",
        digest=changes_digest(changeset),
        release_url=f"https://github.com/{changeset.repo}/releases/tag/{version}",
    )

    try:
        with client.messages.stream(
            model=MODEL,
            max_tokens=8000,
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT,
            output_config={"format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            message = stream.get_final_message()
    except anthropic.APIError as exc:
        print(f"::warning::Claude API call failed ({exc}); using template output")
        return _template_content(changeset, version)

    text = next((b.text for b in message.content if b.type == "text"), "")
    data = _parse_json(text)
    if data is None:
        print("::warning::Could not parse Claude output as JSON; using template output")
        return _template_content(changeset, version)

    return ReleaseContent(
        release_notes=data.get("release_notes", "").strip(),
        tweet=data.get("tweet", "").strip()[:280],
        linkedin=data.get("linkedin", "").strip(),
        generated_by="claude",
    )


def _parse_json(text: str) -> dict | None:
    """Parse JSON, tolerating markdown code fences around it."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        # last resort: grab the outermost braces
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                parsed = json.loads(text[start : end + 1])
                return parsed if isinstance(parsed, dict) else None
            except json.JSONDecodeError:
                return None
        return None
