# Upwork CLI

A Python command-line toolkit for managing your Upwork freelancing workflow from the terminal. Search jobs, generate AI-powered proposals with Claude, track earnings, manage contracts, and handle messages -- all without leaving your shell.

## Features

- **Job Search** -- Query the Upwork marketplace via GraphQL API with budget, job type, and recency filters.
- **AI Job Scoring** -- Score job postings (1-10) against your freelancer profile using Anthropic Claude, so you can focus on the best-fit opportunities.
- **AI Proposal Generation** -- Generate tailored cover letters for specific jobs, or from a pasted job description with `--from-file` (no Upwork API access required). Choose tone (professional, casual, technical, enthusiastic) and length (short, medium, long). Refine proposals iteratively with natural-language feedback.
- **Applications Dashboard** -- List and inspect your submitted applications with proposal status, timestamps, cached cover letters, and related offers.
- **Job Monitoring** -- Watch for new postings on a schedule with `jobs watch`. Get notified in the terminal or via Discord webhook when high-scoring jobs appear.
- **Saved Searches** -- Store your recurring queries and run or watch them as a batch with `jobs searches`.
- **Offer Management** -- Review active offers, inspect rate or budget terms, and withdraw stale offers directly through GraphQL.
- **Earnings Tracking** -- View earnings summaries (all-time, this month, this week), generate date-range reports, and export to CSV.
- **Contract Management** -- List active contracts, view details and milestones, submit work for approval.
- **Messaging** -- List conversations, read message threads, send replies, and find rooms by contract reference.
- **Bookmarking** -- Save interesting jobs locally for later review.
- **Profile Import** -- Import your freelancer profile from a Markdown or YAML file so the AI can write better proposals.
- **Secure Credential Storage** -- API keys and secrets are stored in the system keychain via `keyring`, not in plaintext config files.

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.10+ |
| CLI framework | [Click](https://click.palletsprojects.com/) |
| Terminal UI | [Rich](https://rich.readthedocs.io/) |
| Upwork API | [python-upwork-oauth2](https://github.com/upwork/python-upwork) (OAuth2, GraphQL, REST) |
| AI | [Anthropic Claude](https://docs.anthropic.com/) (claude-opus-5 by default; configurable via `ai_model` in settings) |
| Local storage | SQLite (jobs, scores, proposals, bookmarks) |
| Config format | YAML (settings, profile) |
| Secret storage | [keyring](https://pypi.org/project/keyring/) (system keychain) |
| Build system | setuptools |

## Getting Started

### Prerequisites

- Python 3.10 or later
- An [Upwork API application](https://www.upwork.com/developer/keys/apply) (Client ID + Client Secret)
- An [Anthropic API key](https://console.anthropic.com/) (optional -- required for AI features)

### Installation

**To use the tool**, install it as a standalone command:

```bash
git clone https://github.com/gr8monk3ys/upwork.git
cd upwork
uv tool install .
```

That puts `upwork` on your PATH (usually `~/.local/bin`). Re-run it after
pulling changes, or use `uv tool install --editable .` to have it track your
working copy.

**To work on the tool**, create the locked dev environment instead:

```bash
uv sync --extra test          # exact versions from uv.lock
.venv/bin/pytest              # or `source .venv/bin/activate` first
```

Without `uv`:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[test]"
```

`uv sync` and `pip install -e` put `upwork` in `.venv/bin`, **not** on your
PATH — you need the venv activated, or the full path `.venv/bin/upwork`.
Only `uv tool install` gives you a bare `upwork` command.

### Quick Start

```bash
# Run the interactive setup wizard (configures API keys + OAuth2)
upwork config setup

# Import your freelancer profile for better AI proposals
upwork config profile --file profile.md

# Check your configuration status
upwork config status

# Prove every external path actually works, in one read-only pass
upwork doctor

# Inspect or clear keychain-backed secrets
upwork config secrets status
upwork config secrets clear anthropic-api-key
```

### Checking that it works

The test suite runs against in-memory fakes, which prove the code agrees with
itself. `upwork doctor` proves it agrees with Upwork:

```bash
upwork doctor            # every read-only path: auth, search, applications,
                         # offers, earnings, contracts, messages, and one
                         # small Anthropic completion
upwork doctor --no-ai    # skip the completion, which spends a few tokens
```

It is read-only — nothing is submitted, sent or changed — and it reports
everything that is broken in one run rather than stopping at the first
failure. Exit code is 1 if any check failed, so it works in a cron job.

An account with no contracts or no applications reports `skipped`, not
`failed`: an empty account is a working account.

## Configuration

All configuration is stored in `~/.config/upwork-cli/`:

| File | Contents |
|------|----------|
| `settings.yaml` | Client ID, redirect URI, search defaults, scoring threshold |
| `auth.json` | OAuth2 tokens (file permissions set to 600) |
| `profile.yaml` | Freelancer profile (title, overview, skills, portfolio, rate) |
| `upwork.db` | SQLite database for cached jobs, scores, proposals, bookmarks |

### Environment Variables

Secrets can be provided via environment variables instead of the keychain:

| Variable | Purpose |
|----------|---------|
| `UPWORK_CLIENT_SECRET` | Upwork API client secret |
| `ANTHROPIC_API_KEY` | Anthropic API key for AI features |
| `DISCORD_WEBHOOK_URL` | Discord webhook for job watch notifications |

If an environment variable is set, it takes precedence over the keychain value.

During `upwork config setup`, secret prompts do not echo existing values. Press Enter to keep the current secret, or type `clear` to remove the keychain value.

### Settings Reference

`settings.yaml` stores core CLI settings. The setup wizard writes `client_id` and
`redirect_uri`; advanced users can also edit watch defaults and saved searches manually:

```yaml
client_id: "your-upwork-client-id"
redirect_uri: "https://localhost:8080/callback"
default_search_terms:
  - "python developer"
  - "react native"
watch_interval_minutes: 5
min_score_threshold: 7
# Claude model for scoring/drafting. Set a cheaper model (e.g.
# claude-haiku-4-5) if you score large batches often.
ai_model: claude-opus-5
```

## Usage

### Job Search

```bash
# Search for jobs
upwork jobs search "python backend developer"

# Filter by budget range
upwork jobs search "react frontend" --budget-min 500 --budget-max 5000

# Filter by job type and recency
upwork jobs search "data science" --type fixed --posted 24h --limit 10
```

### AI Job Scoring

```bash
# Score all unscored cached jobs against your profile
upwork jobs score
```

Jobs are scored 1-10 based on skill match, budget appropriateness, client quality, project scope fit, and competition level.

### Job Monitoring

```bash
# Watch for new jobs every 5 minutes (default)
upwork jobs watch "python developer"

# Custom interval and score threshold, with Discord notifications
upwork jobs watch "react native" --interval 10 --min-score 8 --notify discord
```

Press Ctrl+C to stop watching.

### Saved Searches

```bash
# Save recurring searches
upwork jobs searches add "python developer"
upwork jobs searches add "react native"
upwork jobs searches list

# Run all saved searches once
upwork jobs searches run

# Continuously watch all saved searches
upwork jobs searches watch --interval 5
```

### Job Details and Bookmarks

```bash
# View full details for a specific job
upwork jobs detail <job-id>

# Bookmark a job for later
upwork jobs save <job-id> --note "Interesting project, good budget"

# List all bookmarked jobs
upwork jobs saved

# Remove a bookmark
upwork jobs unsave <job-id>
```

### AI Proposal Generation

```bash
# Generate a proposal for a specific job
upwork propose generate <job-id>

# No API access? Paste the job posting into a file and draft from that
upwork propose generate --from-file job.md

# Choose tone and length
upwork propose generate <job-id> --tone technical --length long

# Open the generated proposal in your editor for manual tweaks
upwork propose generate <job-id> --edit

# Refine the most recent proposal (or a specific one by ID) with feedback
upwork propose refine --feedback "emphasize my Python experience and add a question about their timeline"
upwork propose refine 3 --feedback "make it shorter"

# View proposal history
upwork propose history

# Show a specific proposal and copy it to the clipboard
# (pbcopy, wl-copy, xclip, or xsel)
upwork propose show 3 --copy

# Generate interview prep notes for a saved job
upwork propose prep <job-id>

# Mark outcomes and learn from winning proposals
upwork propose mark 3 won
upwork propose learn
```

Generating a proposal moves the job to the `drafted` pipeline stage. After you
actually submit it on Upwork, run `upwork pipeline move <job-id> applied` so
win-rate stats only count proposals you really sent.

Available tones: `professional`, `casual`, `technical`, `enthusiastic`
Available lengths: `short` (~100 words), `medium` (~200 words), `long` (~350 words)

### Applications and Offers

```bash
# List submitted applications
upwork applications list

# Include multiple statuses by querying across them
upwork applications list --status all --sort modified

# Inspect one application and any linked offers
upwork applications show <application-id>

# List current offers
upwork offers list

# Filter current offers by state
upwork offers list --state pending

# Inspect terms and client message for a specific offer
upwork offers show <offer-id>

# Withdraw an offer
upwork offers withdraw <offer-id> --reason no-response --message "Closing this out on my side."
```

### Earnings

```bash
# Show earnings overview (all-time, this month, this week)
upwork earnings summary

# Detailed report with date range
upwork earnings report --from 2026-01-01 --to 2026-01-31

# Export to CSV
upwork earnings export --output january-2026.csv
```

### Contracts

```bash
# List active contracts
upwork contracts list

# View contract details and milestones
upwork contracts detail <reference>

# Submit work for a milestone
upwork contracts submit <reference> --message "Completed phase 1"
```

### Messages

```bash
# List recent conversations
upwork messages list

# Read messages in a conversation
upwork messages read <room-id>

# Send a message
upwork messages send <room-id> "Thanks for the update, I'll have the deliverable ready by Friday."

# Find a conversation room by contract reference
upwork messages find --contract <reference>
```

### Profile Audit and Pipeline

```bash
# Audit your imported profile for completeness
upwork config audit

# View and manage your application pipeline
upwork pipeline view
upwork pipeline stats
upwork pipeline move <job-id> interviewing --notes "Client replied"
upwork pipeline digest --days 7
```

## Project Structure

```
upwork/
  src/upwork_cli/
    __init__.py
    cli.py              # Click entry point, command registration
    client.py           # Upwork API wrapper (GraphQL + REST)
    config.py           # Settings, auth tokens, profile (YAML + keyring)
    db.py               # SQLite schema and data access layer
    models.py           # Dataclasses: JobPosting, Contract, Message
    ai/
      __init__.py
      scorer.py         # AI job-profile match scoring (1-10)
      drafter.py        # AI proposal generation and refinement
      auditor.py        # AI profile audit
      learner.py        # Winning proposal pattern extraction
      interview_prep.py # Interview preparation notes
    commands/
      __init__.py
      config.py         # setup, status, profile, reset, audit
      applications.py  # applications and offers GraphQL workflows
      jobs.py           # search, score, watch, detail, save, saved
      propose.py        # generate, refine, prep, mark, learn, history, show
      earnings.py       # summary, report, export, contracts
      messages.py       # list, read, send, find
      pipeline.py       # pipeline dashboard and stage tracking
  tests/
  docs/
    plans/              # Design documents
  .github/
    workflows/
      ci.yml            # GitHub Actions CI pipeline
  pyproject.toml
```

## API Limitations

Note that Upwork's API does not support:

- **Profile updates** (bio, title, skills, rate) -- must be done through the Upwork web UI.
- **Proposal submission** -- explicitly prohibited by Upwork Terms of Service. This tool generates proposals locally; you must copy and submit them manually.
- **Connects management** -- no API endpoint available.

## Development

```bash
# Preferred: sync the locked test environment
uv sync --extra test

# Run tests
uv run pytest -v --tb=short

# Run repository hooks (installed with the test extra)
uv run pre-commit run --all-files
```

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
