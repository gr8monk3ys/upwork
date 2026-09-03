"""Searching Upwork for jobs, and caching what comes back.

Sits between the commands and ``UpworkClient``: the client returns GraphQL
payloads, and this module turns them into JobPostings and records them
locally. Composes the client with ``db``, the way ``scoring`` composes the
AI layer with ``db``.

Failures are raised, not printed.
"""

from typing import Any

from upwork_cli.client import UpworkClient
from upwork_cli.db import (
    is_seen,
    mark_seen,
    set_pipeline_stage_if_not_exists,
    upsert_job,
)
from upwork_cli.models import JobPosting


class JobsError(RuntimeError):
    """Raised when the Upwork API cannot answer a job search request."""


def _postings(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    """The job nodes inside a marketplace search payload."""
    data = (payload or {}).get("data") or {}
    postings = data.get("marketplaceJobPostings") or {}
    edges = postings.get("edges") or []
    return [
        edge.get("node") or {}
        for edge in edges
        if isinstance(edge, dict) and edge.get("node")
    ]


def search(client: UpworkClient, query: str, limit: int = 20) -> list[JobPosting]:
    """Search the marketplace and return the postings found."""
    try:
        payload = client.search_jobs_graphql(search_term=query, limit=limit)
    except Exception as exc:
        raise JobsError(f"API search failed: {exc}") from exc
    return [JobPosting.from_graphql(node) for node in _postings(payload)]


def get_detail(client: UpworkClient, job_id: str) -> JobPosting | None:
    """One posting fetched fresh from the API, or None if it is unknown."""
    try:
        data = client.get_job_detail(job_id)
    except Exception as exc:
        raise JobsError(f"API lookup failed ({exc})") from exc
    return JobPosting.from_rest(data) if data else None


def cache(jobs: list[JobPosting]) -> None:
    """Record postings locally and place them at the start of the pipeline."""
    for job in jobs:
        upsert_job(job)
        set_pipeline_stage_if_not_exists(job.id, "found")


def collect_new(jobs: list[JobPosting], search_term: str) -> list[JobPosting]:
    """Cache and return only the postings not already seen for this term.

    Seen-ness is per job, not per term: a job already surfaced by another
    saved search is not new again here.
    """
    new_jobs = []
    for job in jobs:
        if is_seen(job.id):
            continue
        new_jobs.append(job)
        mark_seen(job.id, search_term)
        upsert_job(job)
        set_pipeline_stage_if_not_exists(job.id, "found")
    return new_jobs
