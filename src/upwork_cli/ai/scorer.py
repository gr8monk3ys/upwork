"""Score Upwork job postings against a freelancer profile using Claude."""

from concurrent.futures import ThreadPoolExecutor, as_completed

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from upwork_cli.ai.utils import AIError, complete_json

SCORING_PROMPT = """\
You are an expert Upwork freelancer advisor. Score how well this job posting \
matches the freelancer's profile.

Evaluate these factors:
1. **Skill Match** - How well do the freelancer's skills align with the job requirements?
2. **Budget Appropriateness** - Is the budget reasonable for the scope and the freelancer's rate?
3. **Client Quality** - Consider the client's spending history, payment verification, \
feedback score, and hire count. New clients with no history are neutral, not negative.
4. **Project Scope Fit** - Does the project duration and engagement level suit the freelancer?
5. **Competition Level** - Any hints about proposal count, urgency, or invite-only status.

---

**Freelancer Profile:**
{profile}

---

**Job Posting:**
{job}

---

Respond with ONLY valid JSON in this exact format (no markdown fencing):
{{"score": <integer 1-10>, "reasoning": "<2-3 sentence explanation>"}}
"""

console = Console()


def score_job(
    job_summary: str,
    profile_summary: str,
    api_key: str | None = None,
    model: str | None = None,
) -> tuple[int, str]:
    """Score a single job posting against a freelancer profile.

    Args:
        job_summary: Text summary of the job posting.
        profile_summary: Text summary of the freelancer's profile.
        api_key: Anthropic API key; resolved from settings when omitted.
        model: Claude model ID; defaults to the configured/default model.

    Returns:
        Tuple of (score 1-10, reasoning string).

    Raises:
        AIError: If the API call fails or the response cannot be parsed.
    """
    result = complete_json(
        SCORING_PROMPT.format(profile=profile_summary, job=job_summary),
        api_key,
        model=model,
        max_tokens=2048,
        what="scoring response",
    )

    try:
        score = max(1, min(10, int(result["score"])))
        reasoning = str(result["reasoning"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AIError(f"Could not parse scoring response: {exc}") from exc

    return score, reasoning


def score_jobs_batch(
    jobs: list[dict],
    profile_summary: str,
    api_key: str | None = None,
    model: str | None = None,
    max_workers: int = 4,
) -> list[dict]:
    """Score multiple job postings against a freelancer profile.

    Each job dict should contain at minimum a 'summary' key with the text to
    score. Any other keys are passed through to the result unchanged.

    Jobs that fail to score come back with ``score`` set to ``None`` and an
    ``error`` key describing the failure — callers must NOT persist those as
    real scores, or a transient API failure permanently buries a job.

    Args:
        jobs: List of job dicts, each with at least a 'summary' key.
        profile_summary: Text summary of the freelancer's profile.
        api_key: Anthropic API key; resolved from settings when omitted.
        model: Claude model ID; defaults to the configured/default model.
        max_workers: Concurrent API calls (set to 1 for sequential scoring).

    Returns:
        The same list of dicts, each augmented with 'score' and 'reasoning'
        keys (or 'score': None and 'error' on failure), sorted by score
        descending with failures last.
    """
    results = []
    failures: list[str] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Scoring jobs...", total=len(jobs))

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(
                    score_job, job.get("summary", ""), profile_summary, api_key, model
                ): job
                for job in jobs
            }
            for future in as_completed(futures):
                job = futures[future]
                title = job.get("title", "Untitled")
                progress.update(task, description=f"Scored: {title[:60]}")
                try:
                    score, reasoning = future.result()
                    results.append({**job, "score": score, "reasoning": reasoning})
                except AIError as exc:
                    failures.append(f"{title}: {exc}")
                    results.append(
                        {**job, "score": None, "reasoning": "", "error": str(exc)}
                    )
                progress.advance(task)

    if failures:
        console.print(
            f"[red]{len(failures)} job(s) failed to score "
            f"(first error: {failures[0]}). Failed scores are NOT saved.[/red]"
        )

    results.sort(key=lambda j: (j["score"] is None, -(j["score"] or 0)))
    return results
