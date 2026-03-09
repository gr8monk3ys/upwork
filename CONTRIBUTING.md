# Contributing

## Workflow
1. Create a feature branch from the default branch.
2. Keep changes focused and small.
3. Add or update tests when behavior changes.
4. Run `uv sync --extra test`, then `uv run pytest -v --tb=short` before opening a pull request.
5. Run `uv run pre-commit run --all-files` before opening a pull request.
6. Open a pull request with context and validation steps.

## Pull Request Checklist
- Code builds or runs locally
- Tests pass locally
- Docs updated when needed
- No secrets or credentials committed

## Commit Style
Prefer Conventional Commit prefixes when possible, for example `feat:`, `fix:`, and `chore:`.
Keep the subject line imperative and scoped to one change.
