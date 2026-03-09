"""Score Upwork job postings against a freelancer profile using Claude."""

import json

from anthropic import Anthropic
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from upwork_cli.ai.utils import DEFAULT_MODEL, strip_json_fences

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


def score_job(job_summary: str, profile_summary: str, api_key: str) -> tuple[int, str]:
    """Score a single job posting against a freelancer profile.

    Args:
        job_summary: Text summary of the job posting.
        profile_summary: Text summary of the freelancer's profile.
        api_key: Anthropic API key.

    Returns:
        Tuple of (score 1-10, reasoning string). Returns (0, error_message) on failure.
    """
    try:
        client = Anthropic(api_key=api_key)
        message = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=256,
            messages=[
                {
                    "role": "user",
                    "content": SCORING_PROMPT.format(
                        profile=profile_summary,
                        job=job_summary,
                    ),
                }
            ],
        )

        raw = strip_json_fences(message.content[0].text.strip())
        result = json.loads(raw)
        score = max(1, min(10, int(result["score"])))
        reasoning = str(result["reasoning"])
        return score, reasoning

    except Exception as exc:
        return 0, f"Scoring failed: {exc}"


def score_jobs_batch(
    jobs: list[dict],
    profile_summary: str,
    api_key: str,
) -> list[dict]:
    """Score multiple job postings against a freelancer profile.

    Each job dict should contain at minimum a 'summary' key with the text to
    score. Any other keys are passed through to the result unchanged.

    Args:
        jobs: List of job dicts, each with at least a 'summary' key.
        profile_summary: Text summary of the freelancer's profile.
        api_key: Anthropic API key.

    Returns:
        The same list of dicts, each augmented with 'score' and 'reasoning' keys,
        sorted by score descending.
    """
    results = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Scoring jobs...", total=len(jobs))

        for job in jobs:
            summary = job.get("summary", "")
            title = job.get("title", "Untitled")
            progress.update(task, description=f"Scoring: {title[:60]}")

            score, reasoning = score_job(summary, profile_summary, api_key)

            scored = {**job, "score": score, "reasoning": reasoning}
            results.append(scored)
            progress.advance(task)

    results.sort(key=lambda j: j["score"], reverse=True)
    return results
