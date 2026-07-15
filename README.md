# Release Notes Agent 📝

Point it at a GitHub repo and it reads every merged PR and commit since your
last release, then drafts **human-readable release notes**, a **tweet**, and a
**LinkedIn post** — ready to review and publish.

Ships as a **GitHub Action** so any repo can install it in ~15 lines of YAML.

## How it works

```
GitHub API ──▶ collect ──▶ categorize ──▶ summarize ──▶ outputs
              merged PRs   feat/fix/docs   Claude API    RELEASE_NOTES.md
              + commits    via labels &    (or template  tweet.txt
              since last   conventional    fallback)     linkedin.txt
              release      commits
```

1. **Collect** — finds your last published release (falls back to the latest
   tag, then full history), and gathers every merged PR and commit since.
   PRs are preferred over raw commits because they carry titles, labels, and
   descriptions; direct pushes are still included.
2. **Categorize** — buckets changes into Breaking Changes / Features /
   Bug Fixes / Performance / Docs / Maintenance using PR labels first, then
   conventional-commit prefixes (`feat:`, `fix:`, `feat!:` …).
3. **Summarize** — sends the digest to Claude (`claude-opus-4-8`, structured
   JSON output) to write notes that lead with *what changed for users*, plus
   matching social posts. **No API key? It still works** — a deterministic
   template renderer produces clean, category-grouped notes.

## Install as a GitHub Action

Add `.github/workflows/release-notes.yml` to your repo:

```yaml
name: Draft release notes
on:
  push:
    tags: ["v*"]

permissions:
  contents: write
  pull-requests: read

jobs:
  release-notes:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - id: notes
        uses: srivanik8/final-project@main
        with:
          version: ${{ github.ref_name }}
          anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}  # optional
      - name: Create draft release
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          gh release create "${{ github.ref_name }}" --draft \
            --notes-file "${{ steps.notes.outputs.notes-file }}"
```

Push a tag like `v1.2.0` and a **draft** release appears with the generated
notes — you always review before publishing. The tweet and LinkedIn drafts
are uploaded as workflow artifacts.

### Action inputs

| Input | Required | Default | Description |
|---|---|---|---|
| `version` | ✅ | — | Version being released (e.g. `v1.2.0`) |
| `repo` | | current repo | `owner/name` to analyze |
| `base` | | latest release | Tag to diff from |
| `github-token` | | workflow token | Token for reading PRs/commits |
| `anthropic-api-key` | | — | Enables AI-written notes; omit for template output |
| `output-dir` | | `release-notes-output` | Where the three files are written |

### Action outputs

`notes-file`, `tweet-file`, `linkedin-file`, and `generated-by`
(`claude` or `template`).

## Run locally (CLI)

```bash
pip install "release-notes-agent[ai] @ git+https://github.com/srivanik8/final-project"

export GITHUB_TOKEN=ghp_...          # for private repos / higher rate limits
export ANTHROPIC_API_KEY=sk-ant-...  # optional — omit for template mode

release-notes-agent owner/repo --version v1.2.0
```

Outputs land in `release-notes-output/`:

```
RELEASE_NOTES.md   # markdown notes, grouped by category, with PR links + credits
tweet.txt          # ≤280 chars, version + one highlight + release link
linkedin.txt       # short post aimed at engineers evaluating the project
```

## Sample output (template mode)

```markdown
# v1.1.0

## ✨ Features
- Add dark mode (#42) @alice

## 🐛 Bug Fixes
- Handle crash on empty config (#43) @bob

## 🙌 Contributors
@alice, @bob
```

With an Anthropic key, Claude rewrites the bullets for end users, adds a
release summary paragraph, and puts migration guidance under any breaking
changes.

## Project layout

```
release_notes_agent/
  github_client.py   # minimal GitHub REST client (retries, pagination)
  collector.py       # merged PRs + commits since last release → ChangeSet
  categorize.py      # labels + conventional commits → sections
  render.py          # deterministic markdown/tweet/linkedin templates
  summarizer.py      # Claude call (structured output) with template fallback
  cli.py             # entrypoint
action.yml           # composite GitHub Action
tests/               # pytest suite (no network needed)
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

## Design decisions

- **Works without an AI key.** Adoption first: the template output is genuinely
  useful, and the AI output is an upgrade, not a requirement.
- **Structured outputs, not prompt-and-pray.** The Claude call uses
  `output_config.format` with a JSON schema, so the response is guaranteed
  parseable — no regex scraping of model output.
- **Drafts, never auto-publish.** The action creates *draft* releases and
  text files. A human always approves before anything goes public.
- **PRs over commits.** PR titles + labels are the richest signal of intent;
  commits fill the gaps for direct pushes.

## License

MIT
