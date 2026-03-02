# Upwork CLI

A Python command-line toolkit for managing your Upwork freelancing workflow from the terminal. Search jobs, generate AI-powered proposals with Claude, track earnings, manage contracts, and handle messages -- all without leaving your shell.

## Features

- **Job Search** -- Query the Upwork marketplace via GraphQL API (with RSS fallback for unauthenticated use). Filter by budget, job type, and recency.
- **AI Job Scoring** -- Score job postings (1-10) against your freelancer profile using Anthropic Claude, so you can focus on the best-fit opportunities.
- **AI Proposal Generation** -- Generate tailored cover letters for specific jobs. Choose tone (professional, casual, technical, enthusiastic) and length (short, medium, long). Refine proposals iteratively with natural-language feedback.
- **Job Monitoring** -- Watch for new postings on a schedule with `jobs watch`. Get notified in the terminal or via Discord webhook when high-scoring jobs appear.
- **Earnings Tracking** -- View earnings summaries (all-time, this month, this week), generate date-range reports, and export to CSV.
- **Contract Management** -- List active contracts, view details and milestones, submit work for approval.
- **Messaging** -- List conversations, read message threads, send replies, and find rooms by contract reference.
- **Bookmarking** -- Save interesting jobs locally for later review.
- **Profile Import** -- Import your freelancer profile from a Markdown or YAML file so the AI can write better proposals.
- **Secure Credential Storage** -- API keys and secrets are stored in the system keychain via `keyring`, not in plaintext config files.

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.9+ |
| CLI framework | [Click](https://click.palletsprojects.com/) |
| Terminal UI | [Rich](https://rich.readthedocs.io/) |
| Upwork API | [python-upwork-oauth2](https://github.com/upwork/python-upwork) (OAuth2, GraphQL, REST) |
| AI | [Anthropic Claude](https://docs.anthropic.com/) (claude-sonnet-4-5) |
| Local storage | SQLite (jobs, scores, proposals, bookmarks) |
| Config format | YAML (settings, profile) |
| Secret storage | [keyring](https://pypi.org/project/keyring/) (system keychain) |
| RSS fallback | [feedparser](https://pypi.org/project/feedparser/) |
| Build system | setuptools |

## Getting Started

### Prerequisites

- Python 3.9 or later
- An [Upwork API application](https://www.upwork.com/developer/keys/apply) (Client ID + Client Secret)
- An [Anthropic API key](https://console.anthropic.com/) (optional -- required for AI features)

### Installation

```bash
# Clone the repository
git clone https://github.com/gr8monk3ys/upwork.git
cd upwork

# Create a virtual environment and install
python -m venv .venv
source .venv/bin/activate
pip install -e .

# Or with uv
uv venv
source .venv/bin/activate
uv pip install -e .
```

After installation the `upwork` command is available on your PATH.

### Quick Start

```bash
# Run the interactive setup wizard (configures API keys + OAuth2)
upwork config setup

# Import your freelancer profile for better AI proposals
upwork config profile --file profile.md

# Check your configuration status
upwork config status
```

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

### Settings Reference

The setup wizard configures these via `settings.yaml`:

```yaml
client_id: "your-upwork-client-id"
redirect_uri: "https://localhost:8080/callback"
default_search_terms:
  - "python developer"
  - "full stack"
watch_interval_minutes: 5
min_score_threshold: 7
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

### Job Details and Bookmarks

```bash
# View full details for a specific job
upwork jobs detail <job-id>

# Bookmark a job for later
upwork jobs save <job-id> --note "Interesting project, good budget"

# List all bookmarked jobs
upwork jobs saved
```

### AI Proposal Generation

```bash
# Generate a proposal for a specific job
upwork propose generate <job-id>

# Choose tone and length
upwork propose generate <job-id> --tone technical --length long

# Open the generated proposal in your editor for manual tweaks
upwork propose generate <job-id> --edit

# Refine the most recent proposal with feedback
upwork propose refine --feedback "emphasize my Python experience and add a question about their timeline"

# View proposal history
upwork propose history

# Show a specific proposal (and copy to clipboard on macOS)
upwork propose show 3 --copy
```

Available tones: `professional`, `casual`, `technical`, `enthusiastic`
Available lengths: `short` (~100 words), `medium` (~200 words), `long` (~350 words)

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
    commands/
      __init__.py
      config.py         # setup, status, profile, reset
      jobs.py           # search, score, watch, detail, save, saved
      propose.py        # generate, refine, history, show
      earnings.py       # summary, report, export, contracts
      messages.py       # list, read, send, find
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
# Install with test dependencies
pip install -e ".[test]"

# Run tests
pytest
```

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
