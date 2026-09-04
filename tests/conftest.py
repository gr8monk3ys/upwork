"""Shared fixtures for the Upwork CLI test suite."""

from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from upwork_cli.models import JobPosting

# ---------------------------------------------------------------------------
# Filesystem isolation
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Redirect ALL config/DB paths to a temp directory.

    This patches both the canonical definitions in ``upwork_cli.config`` AND
    the locally-bound names re-imported in other modules (e.g. ``upwork_cli.db``
    does ``from upwork_cli.config import DB_FILE``).
    """
    cfg = tmp_path / ".config" / "upwork-cli"
    cfg.mkdir(parents=True)

    paths = {
        "CONFIG_DIR": cfg,
        "AUTH_FILE": cfg / "auth.json",
        "PROFILE_FILE": cfg / "profile.yaml",
        "SETTINGS_FILE": cfg / "settings.yaml",
        "DB_FILE": cfg / "upwork.db",
    }

    # Patch in config (canonical) and all known re-importers
    for mod in ("upwork_cli.config", "upwork_cli.db", "upwork_cli.commands.config"):
        for name, value in paths.items():
            monkeypatch.setattr(f"{mod}.{name}", value, raising=False)

    return cfg


# ---------------------------------------------------------------------------
# Keyring isolation
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def mock_keyring(monkeypatch):
    """In-memory keyring -- never touch the real system keychain."""
    store: dict[str, str] = {}

    monkeypatch.setattr(
        "keyring.get_password",
        lambda svc, key: store.get(f"{svc}:{key}"),
    )
    monkeypatch.setattr(
        "keyring.set_password",
        lambda svc, key, val: store.__setitem__(f"{svc}:{key}", val),
    )
    monkeypatch.setattr(
        "keyring.delete_password",
        lambda svc, key: store.pop(f"{svc}:{key}", None),
    )
    return store


# ---------------------------------------------------------------------------
# Click CLI runner
# ---------------------------------------------------------------------------


@pytest.fixture
def cli_runner():
    """Pre-configured Click CliRunner with isolated environment."""
    return CliRunner()


# ---------------------------------------------------------------------------
# Sample data factories
# ---------------------------------------------------------------------------


def _make_job_dict(**overrides) -> dict:
    """Return a minimal valid job dict (the shape a ``jobs`` row holds)."""
    base = {
        "id": "~01abc123",
        "title": "Python Developer Needed",
        "description": "Build a REST API using FastAPI.",
        "skills": ["Python", "FastAPI", "PostgreSQL"],
        "budget_amount": 5000.0,
        "budget_currency": "USD",
        "duration": "1 to 3 months",
        "engagement": "30+ hrs/week",
        "client_country": "United States",
        "client_total_spent": 150000.0,
        "client_total_hires": 42,
        "client_feedback": 4.9,
        "client_verified": True,
        "created_at": "2025-01-15T10:00:00Z",
    }
    base.update(overrides)
    return base


def _make_graphql_node(**overrides) -> dict:
    """Return a minimal GraphQL job node for ``JobPosting.from_graphql``."""
    base = {
        "id": "~01abc123",
        "title": "Python Developer Needed",
        "description": "Build a REST API.",
        "skills": [{"prettyName": "Python"}, {"prettyName": "FastAPI"}],
        "amount": {"amount": "5000", "currencyCode": "USD"},
        "duration": "1 to 3 months",
        "engagement": "30+ hrs/week",
        "createdDateTime": "2025-01-15T10:00:00Z",
        "client": {
            "location": {"country": "United States"},
            "totalSpent": {"amount": "150000"},
            "totalHires": 42,
            "totalFeedback": 4.9,
            "verificationStatus": "VERIFIED",
        },
        "occupations": {
            "category": {"prefLabel": "Web Development"},
            "subcategory": {"prefLabel": "Backend Development"},
        },
    }
    base.update(overrides)
    return base


def _make_rest_job(**overrides) -> dict:
    """Return a minimal REST API job dict for ``JobPosting.from_rest``."""
    base = {
        "id": "~01rest456",
        "title": "Frontend React Dev",
        "description": "Build a dashboard.",
        "skills": ["React", "TypeScript"],
        "budget": {"amount": "3000", "currencyCode": "USD"},
        "duration": "Less than 1 month",
        "engagement": "Less than 30 hrs/week",
        "date_created": "2025-02-01T12:00:00Z",
        "client": {
            "country": "Canada",
            "total_charge": 50000.0,
            "total_hires": 10,
            "feedback": 4.5,
        },
    }
    base.update(overrides)
    return base


def _make_job_posting(**overrides) -> JobPosting:
    """Return a minimal valid ``JobPosting`` for ``upsert_job``."""
    return JobPosting(**_make_job_dict(**overrides))


@pytest.fixture
def sample_job():
    return _make_job_dict()


@pytest.fixture
def sample_graphql_node():
    return _make_graphql_node()


@pytest.fixture
def sample_rest_job():
    return _make_rest_job()


# ---------------------------------------------------------------------------
# Anthropic mock factory
# ---------------------------------------------------------------------------


def mock_anthropic_response(text: str, include_thinking: bool = False) -> MagicMock:
    """Build a mock Anthropic ``messages.create`` return value.

    With ``include_thinking``, a thinking block precedes the text block —
    mirroring current models, where indexing ``content[0]`` is unsafe.
    """
    blocks = []
    if include_thinking:
        thinking_block = MagicMock()
        thinking_block.type = "thinking"
        thinking_block.thinking = "reasoning..."
        blocks.append(thinking_block)
    content_block = MagicMock()
    content_block.type = "text"
    content_block.text = text
    blocks.append(content_block)
    response = MagicMock()
    response.content = blocks
    return response


@pytest.fixture
def completer(monkeypatch):
    """Substitute a FakeCompleter at the AI seam.

    Yields the fake so a test can read what reached the model. Set its
    responses with ``completer.set(...)`` or build one directly and pass it
    to :func:`use_completer`.
    """
    from tests.fakes import FakeCompleter

    fake = FakeCompleter("")
    monkeypatch.setattr("upwork_cli.ai.utils.get_completer", lambda _key: fake)
    return fake


@pytest.fixture
def use_completer(monkeypatch):
    """Install a specific FakeCompleter at the AI seam."""

    def install(fake):
        monkeypatch.setattr("upwork_cli.ai.utils.get_completer", lambda _key: fake)
        return fake

    return install
