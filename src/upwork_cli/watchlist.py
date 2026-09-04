"""Saved searches, and the alert cycle that runs across them.

The Job search cycle -- read the saved terms, search, keep what is new, score
it, decide what is worth interrupting the freelancer for -- used to be nine
private functions inside ``commands/jobs.py``, reachable only through Click.
Nothing tested the compositions, and a call inside one of them had been
passing the wrong arguments since #31.

Composes ``jobs`` with ``scoring`` and the saved terms in ``Settings``, the
way ``jobs`` composes the client with ``db``. Failures are raised, not
printed: :func:`run_cycle` returns a :class:`CycleReport` and the command
decides what the user sees.
"""

import json
import urllib.request
from dataclasses import dataclass, field

from upwork_cli import jobs as jobs_api
from upwork_cli.client import UpworkClient
from upwork_cli.config import save_settings
from upwork_cli.models import JobPosting, ScoreResult
from upwork_cli.scoring import score_jobs


class WatchlistError(RuntimeError):
    """Raised when a saved search cannot be added, or an alert cannot be sent."""


class AlreadySaved(WatchlistError):
    """Raised when adding a term the watchlist already holds.

    Separate from :class:`WatchlistError` because it is not a failure: the
    watchlist already says what the caller asked it to say. Commands report
    it and carry on, where a blank term stops them.
    """


class NotSaved(WatchlistError):
    """Raised when removing a term the watchlist does not hold. Also not a failure."""


def normalize(query: str) -> str:
    """A trimmed, whitespace-normalized search term."""
    return " ".join(query.split())


def terms(settings) -> list[str]:
    """The saved search terms, normalized and deduplicated, in order."""
    seen: set[str] = set()
    found: list[str] = []
    for item in settings.default_search_terms or []:
        term = normalize(str(item))
        if term and term not in seen:
            seen.add(term)
            found.append(term)
    return found


def _save(settings, updated: list[str]) -> None:
    """Persist search terms without disturbing anything else in settings."""
    settings.default_search_terms = updated
    save_settings(settings)


def add(settings, query: str) -> str:
    """Save a search term and return it as stored.

    Raises:
        WatchlistError: when the term is blank.
        AlreadySaved: when the watchlist already holds it.
    """
    term = normalize(query)
    if not term:
        raise WatchlistError("Search term cannot be empty.")
    saved = terms(settings)
    if term in saved:
        raise AlreadySaved(f"Saved search already exists: {term}")
    _save(settings, [*saved, term])
    return term


def remove(settings, query: str) -> str:
    """Drop a search term and return it as it was stored.

    Raises:
        NotSaved: when the watchlist does not hold it.
    """
    term = normalize(query)
    saved = terms(settings)
    if term not in saved:
        raise NotSaved(f"Saved search not found: {term}")
    _save(settings, [item for item in saved if item != term])
    return term


@dataclass
class CycleReport:
    """What one pass over one search term found.

    ``alerts`` is what is worth interrupting the freelancer for. When scoring
    is unavailable every new Job alerts unscored, because a Job nobody could
    judge is still a Job the freelancer has not seen -- which is why this is
    a list of ScoreResults and not of Scores.
    """

    term: str
    new_jobs: list[JobPosting] = field(default_factory=list)
    alerts: list[ScoreResult] = field(default_factory=list)
    scored: bool = False

    @property
    def new_count(self) -> int:
        return len(self.new_jobs)

    @property
    def alert_count(self) -> int:
        return len(self.alerts)


def run_cycle(
    client: UpworkClient,
    term: str,
    *,
    limit: int = 20,
    min_score: int = 7,
    profile_summary: str = "",
    scored: bool = False,
) -> CycleReport:
    """Search for *term*, keep what is new, and decide what is alert-worthy.

    Raises:
        JobsError: when the search itself fails. An empty result and a failed
            search are different answers and must not arrive as the same one.
    """
    found = jobs_api.search(client, term, limit)
    new_jobs = jobs_api.collect_new(found, term)
    if not new_jobs:
        return CycleReport(term=term, scored=scored)

    if not scored:
        alerts = [ScoreResult(job=job) for job in new_jobs]
    else:
        results = score_jobs(new_jobs, profile_summary)
        alerts = [r for r in results if r.score is not None and r.score >= min_score]

    return CycleReport(term=term, new_jobs=new_jobs, alerts=alerts, scored=scored)


def alert_text(result: ScoreResult) -> str:
    """One alert as a single line: score, then title."""
    score = result.score if result.score is not None else "?"
    return f"[Score {score}] {result.job.title or 'Untitled'}"


def send_discord(webhook_url: str, message: str) -> None:
    """Post one alert to a Discord webhook.

    Raises:
        WatchlistError: when the URL is unusable or the POST fails. A watch
            loop is expected to carry on past this; that is the caller's
            decision to make, not this module's.
    """
    if not webhook_url.startswith("https://"):
        raise WatchlistError("Discord webhook URL must use https://")
    request = urllib.request.Request(
        webhook_url,
        data=json.dumps({"content": message}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
        urllib.request.urlopen(request)
    except Exception as exc:
        raise WatchlistError(f"Discord notification failed: {exc}") from exc
