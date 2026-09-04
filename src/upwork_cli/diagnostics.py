"""Exercising every external path this tool has, once, and reporting back.

Test coverage measures how well the code agrees with `tests/fakes.py`. The
fakes were written from assumptions about Upwork's payload shapes, not from
captured responses, so the whole suite can be internally consistent and still
wrong at the boundary. Nothing here can be verified without a real call.

Every check is read-only. Nothing in this module writes to Upwork, submits
anything, or changes local state.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from upwork_cli import applications, contracts, earnings, jobs, messaging
from upwork_cli.client import NotAuthenticated, UpworkClient, get_client
from upwork_cli.config import load_profile, load_settings

#: What a check found. ``skipped`` is not a failure: an account with no
#: contracts is a working account, and saying "failed" there would be a lie.
OK, FAILED, SKIPPED = "ok", "failed", "skipped"


@dataclass
class Check:
    name: str
    status: str
    detail: str = ""

    @property
    def failed(self) -> bool:
        return self.status == FAILED


def _run(name: str, call: Callable[[], Any], describe: Callable[[Any], str]) -> Check:
    """One check, reporting rather than raising."""
    try:
        result = call()
    # A diagnostic that aborts on the first failure is useless: the point is
    # to learn everything that is broken in one run, not the first thing.
    except Exception as exc:  # noqa: BLE001
        return Check(name, FAILED, f"{type(exc).__name__}: {exc}")
    return Check(name, OK, describe(result))


def _plural(items: Any, noun: str) -> str:
    count = len(items)
    return f"{count} {noun}{'' if count == 1 else 's'}"


def configuration() -> list[Check]:
    """What is set up locally, before any network call."""
    settings = load_settings()
    profile = load_profile()
    checks = [
        Check(
            "Upwork credentials",
            OK if settings.client_id and settings.client_secret else FAILED,
            "client id and secret present"
            if settings.client_id and settings.client_secret
            else "run 'upwork config setup'",
        ),
        Check(
            "Anthropic API key",
            OK if settings.anthropic_api_key else SKIPPED,
            "present" if settings.anthropic_api_key else "AI features unavailable",
        ),
        Check(
            "Profile",
            OK if not profile.is_empty else SKIPPED,
            "loaded" if not profile.is_empty else "scoring and drafting need one",
        ),
    ]
    return checks


def upwork_api(client: UpworkClient) -> list[Check]:
    """Every read-only Upwork path, once each."""
    checks = [
        _run(
            "Authentication",
            client.get_user_info,
            lambda r: f"reference {(r or {}).get('info', {}).get('ref', '?')}",
        ),
        _run(
            "Job search",
            lambda: jobs.search(client, "python", limit=1),
            lambda r: _plural(r, "posting"),
        ),
        _run(
            "Applications",
            lambda: applications.list_applications(client, ["Submitted"], limit=1),
            lambda r: _plural(r, "application"),
        ),
        _run(
            "Offers",
            lambda: applications.list_offers(client, limit=1),
            lambda r: _plural(r, "offer"),
        ),
        _run(
            "Earnings report",
            lambda: earnings.fetch(client)[0],
            lambda r: _plural(r, "row"),
        ),
        _run(
            "Contracts",
            lambda: contracts.list_contracts(client),
            lambda r: _plural(r, "contract"),
        ),
        _run(
            "Messages",
            lambda: messaging.list_rooms(client, limit=1),
            lambda r: _plural(r, "room"),
        ),
    ]
    return checks


def ai() -> list[Check]:
    """One real completion, to prove the key and model resolve."""
    from upwork_cli.ai.utils import complete

    return [
        _run(
            "Anthropic completion",
            lambda: complete("Reply with the single word: ok", max_tokens=16),
            lambda r: f"model answered ({r.strip()[:20]})",
        )
    ]


def run_all(*, with_ai: bool = True) -> list[Check]:
    """Every check, in the order a first-time user would hit them."""
    checks = configuration()

    try:
        client = get_client()
    except NotAuthenticated:
        # Point at the smaller command when the credentials are already
        # there: `config setup` re-prompts for five of them before it
        # reaches the OAuth step that is actually missing.
        settings = load_settings()
        remedy = (
            "run 'upwork config login'"
            if settings.client_id and settings.client_secret
            else "run 'upwork config setup'"
        )
        checks.append(Check("Authentication", FAILED, f"no OAuth token — {remedy}"))
        return checks

    checks.extend(upwork_api(client))
    if with_ai and load_settings().anthropic_api_key:
        checks.extend(ai())
    return checks
