"""Scoring runs: judge cached jobs against the freelancer's profile.

Composes the AI scorer with local persistence, so the rule that a failed
attempt is never saved lives in exactly one place. ``ai/`` stays free of
database access; this module is where the two meet.
"""

from upwork_cli.ai.scorer import score_jobs_batch
from upwork_cli.db import save_score
from upwork_cli.models import JobPosting, ScoreResult


def score_jobs(
    jobs: list[JobPosting],
    profile_summary: str,
    api_key: str | None = None,
    model: str | None = None,
) -> list[ScoreResult]:
    """Score *jobs*, persist the successes, and return every attempt.

    A failed attempt comes back with ``score`` of None and is deliberately
    not persisted: caching a transient API failure would bury the job at the
    bottom of every future ranking with no way to retry it.

    Results are ordered highest score first, failures last.
    """
    if not jobs:
        return []

    by_id = {job.id: job for job in jobs}
    batch = [
        {"id": job.id, "title": job.title, "summary": job.summary_for_ai()}
        for job in jobs
    ]
    scored = score_jobs_batch(batch, profile_summary, api_key, model=model)

    results: list[ScoreResult] = []
    for item in scored:
        job = by_id.get(item.get("id", ""))
        if job is None:
            continue
        result = ScoreResult(
            job=job,
            score=item.get("score"),
            reasoning=item.get("reasoning") or "",
            error=item.get("error") or "",
        )
        if result.score is not None:
            save_score(job.id, result.score, result.reasoning)
        results.append(result)
    return results
