# Repository Guidelines

## Project Structure & Module Organization
Core code lives in `src/upwork_cli/`. Use `cli.py` for the Click entry point, `commands/` for user-facing subcommands, `ai/` for Anthropic-backed workflows, and top-level modules such as `client.py`, `config.py`, `db.py`, and `models.py` for shared infrastructure. Tests live in `tests/` and generally mirror module names, for example `tests/test_messages.py` and `tests/test_db.py`. Keep design notes in `docs/`, and treat generated caches such as `__pycache__/` and local config files as non-source artifacts.

## Build, Test, and Development Commands
Prefer `uv sync --extra test` to create the locked local environment; it installs both pytest and pre-commit tooling. Run the full suite with `uv run pytest -v --tb=short`; CI uses the same pytest invocation on Python 3.11. Use `uv run pre-commit run --all-files` before opening a PR to apply repository checks, including `ruff` and `ruff-format`. For a quick manual smoke test, run `uv run upwork --help` or `uv run upwork config status`.

## Coding Style & Naming Conventions
Follow existing Python conventions: 4-space indentation, `snake_case` for modules, functions, and test files, and clear command names grouped by domain under `commands/`. Keep CLI handlers thin; push API, config, and database logic into reusable modules. Format and lint with `ruff` and `ruff-format` through pre-commit rather than ad hoc style changes.

## Testing Guidelines
Write pytest tests for every behavior change and add focused regression coverage near the touched module. Name files `test_<area>.py` and prefer descriptive test names such as `test_profile_from_markdown_file`. Reuse fixtures from `tests/conftest.py`, especially the isolated config and in-memory keyring helpers, so tests never hit a real Upwork account or system keychain. No coverage gate is configured, so maintain or improve coverage in changed areas.

## Commit & Pull Request Guidelines
Recent history follows Conventional Commit style, for example `feat: ...`, `fix: ...`, and `chore: ...`; keep the subject imperative and scoped to one change. PRs should include purpose, local validation steps, and any docs updates. For CLI-facing changes, include sample terminal output instead of screenshots when it clarifies behavior.

## Security & Configuration Tips
Do not commit API keys, OAuth tokens, or real client data. Runtime config lives under `~/.config/upwork-cli/`; secrets should stay in `keyring` or environment variables such as `UPWORK_CLIENT_SECRET` and `ANTHROPIC_API_KEY`.

## Agent skills

### Issue tracker

Issues live in GitHub Issues for `gr8monk3ys/upwork`, managed with the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles, each using its default label string. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
