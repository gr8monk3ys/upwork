"""AI-powered interview preparation for Upwork jobs."""

from upwork_cli.ai.utils import complete

PREP_PROMPT = """\
You are an expert Upwork freelancer coach. Generate interview preparation notes \
for this freelancer and job.

**Job Details:**
{job_summary}

**Freelancer Profile:**
{profile_summary}

{client_research_section}

Provide markdown-formatted prep notes covering:
1. **Likely Interview Questions** — 5 questions the client may ask
2. **Strengths to Highlight** — 3 profile strengths most relevant to this job
3. **Questions to Ask the Client** — 3 smart questions to demonstrate expertise
4. **Red Flags to Watch For** — anything concerning about this engagement
5. **Rate Discussion** — how to approach rate negotiation for this job

Return ONLY the markdown content, no preamble.
"""


def generate_interview_prep(
    job_summary: str,
    profile_summary: str,
    api_key: str | None = None,
    client_research: str = "",
    model: str | None = None,
) -> str:
    """Generate interview prep notes for a job.

    Returns markdown-formatted prep notes.

    Raises:
        AIError: If the API call fails.
    """
    research_section = (
        f"**Client Research:**\n{client_research}" if client_research else ""
    )

    return complete(
        PREP_PROMPT.format(
            job_summary=job_summary,
            profile_summary=profile_summary,
            client_research_section=research_section,
        ),
        api_key,
        model=model,
        max_tokens=3000,
    )
