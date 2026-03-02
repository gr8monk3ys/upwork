"""AI-powered interview preparation for Upwork jobs."""

from anthropic import Anthropic

MODEL = "claude-sonnet-4-5-20250929"

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
    api_key: str,
    client_research: str = "",
) -> str:
    """Generate interview prep notes for a job.

    Returns markdown-formatted prep notes.
    Raises RuntimeError on failure.
    """
    research_section = (
        f"**Client Research:**\n{client_research}" if client_research else ""
    )

    try:
        client = Anthropic(api_key=api_key)
        message = client.messages.create(
            model=MODEL,
            max_tokens=1500,
            messages=[{
                "role": "user",
                "content": PREP_PROMPT.format(
                    job_summary=job_summary,
                    profile_summary=profile_summary,
                    client_research_section=research_section,
                ),
            }],
        )
        return message.content[0].text

    except Exception as exc:
        raise RuntimeError(f"Interview prep failed: {exc}") from exc
