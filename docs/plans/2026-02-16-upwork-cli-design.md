# Upwork CLI Toolkit - Design Document

**Date:** 2026-02-16
**Author:** Lorenzo Scaturchio
**Status:** Historical design draft (some planned features, such as RSS fallback, were not shipped)

## Overview

A Python CLI toolkit for managing an Upwork freelancing workflow from the terminal. Wraps the official Upwork API (OAuth2 + GraphQL) with AI-powered features for job scoring and proposal generation.

## Architecture

**Approach:** Monolithic CLI with click subcommands (same pattern as protonmail-organizer).

```
upwork/
  src/upwork_cli/
    cli.py              # click entry point
    auth.py             # OAuth2 flow + token storage
    client.py           # Upwork API wrapper (GraphQL + REST)
    config.py           # settings, token, profile storage
    db.py               # SQLite for local data
    models.py           # dataclasses for API responses
    ai/
      scorer.py         # AI job-profile match scoring
      drafter.py        # AI proposal generation
    commands/
      config.py         # setup, status, profile import
      jobs.py           # search, score, watch, bookmark
      propose.py        # generate, refine, history
      earnings.py       # earnings summary, contracts
      messages.py       # read, send, find rooms
  tests/
  pyproject.toml
```

## Command Groups

### `upwork config`
- `setup` - OAuth2 flow + API keys
- `status` - Auth status, token expiry
- `profile` - Import profile for AI context
- `reset` - Clear all config

### `upwork jobs`
- `search <query>` - GraphQL search
- `score` - AI-score cached jobs against profile
- `watch <query>` - Monitor loop with alerts
- `detail <id>` - Full job info
- `save/saved` - Bookmarking

### `upwork propose`
- `generate <job-id>` - AI cover letter
- `refine` - Iterate on last proposal
- `history` - Past proposals
- `show <id>` - Full proposal view

### `upwork earnings`
- `summary` - Earnings overview
- `report` - Detailed with date range
- `export` - CSV export

### `upwork contracts`
- `list` - Active contracts
- `detail <ref>` - Contract info + milestones
- `submit <ref>` - Submit work for approval

### `upwork messages`
- `list` - Recent conversations
- `read <room-id>` - Chat view
- `send <room-id> <text>` - Send message
- `find --contract <ref>` - Find room

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Language | Python | Official SDK, matches existing repos |
| Package manager | uv | User's standard |
| CLI framework | click + rich | Matches protonmail-organizer |
| API SDK | python-upwork-oauth2 | Official, OAuth2 + GraphQL |
| AI | Anthropic Claude (sonnet) | User already uses Claude |
| Local storage | SQLite | Simple, no server, portable |
| Token storage | ~/.config/upwork-cli/ | XDG-compliant |
| Job alerts | Terminal + Discord webhook | Lightweight, extensible |
| RSS fallback | feedparser | Planned, not implemented |

## API Limitations

- Profile updates (bio, title, skills, rate): NOT available via API
- Proposal submission: Explicitly prohibited by Upwork ToS
- Connects management: No API endpoint
- All profile modifications must be done through Upwork web UI

## Dependencies

- python-upwork-oauth2 >= 3.2.0
- click >= 8.1
- rich >= 13.0
- anthropic >= 0.40.0
- pyyaml >= 6.0
- keyring >= 25.0
- feedparser >= 6.0 (planned only)
