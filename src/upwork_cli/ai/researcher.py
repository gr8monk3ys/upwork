"""AI-powered client research for Upwork jobs."""

import json
from typing import Any

from anthropic import Anthropic

from upwork_cli.ai.utils import DEFAULT_MODEL, strip_json_fences

RESEARCH_PROMPT = """\
You are an expert Upwork freelancer advisor. Analyze this client and provide \
a risk assessment and proposal strategy.

**Client Data:**
{client_data}

**Job Summary:**
{job_summary}

Respond with ONLY valid JSON (no markdown fencing):
{{
  "risk_level": "<low|medium|high>",
  "spending_tier": "<new|small|medium|large|enterprise>",
  "brief": "<2-3 sentence client assessment>",
  "proposal_tips": "<2-3 actionable tips for tailoring the proposal to this client>"
}}
"""

FALLBACK: dict[str, Any] = {
    "risk_level": "unknown",
    "spending_tier": "unknown",
    "brief": "Could not analyze client.",
    "proposal_tips": "",
}


def research_client(
    job_summary: str,
    total_spent: float | None,
    total_hires: int | None,
    feedback: float | None,
    country: str,
    verified: bool,
    api_key: str,
) -> dict[str, Any]:
    """Research a client based on available data.

    Returns dict with risk_level, spending_tier, brief, proposal_tips.
    Returns fallback dict on failure.
    """
    client_data_parts = []
    if total_spent is not None:
        client_data_parts.append(f"Total Spent: ${total_spent:,.0f}")
    if total_hires is not None:
        client_data_parts.append(f"Total Hires: {total_hires}")
    if feedback is not None:
        client_data_parts.append(f"Feedback Score: {feedback}")
    if country:
        client_data_parts.append(f"Country: {country}")
    client_data_parts.append(f"Payment Verified: {'Yes' if verified else 'No'}")

    client_data = "\n".join(client_data_parts) if client_data_parts else "No client data available."

    try:
        client = Anthropic(api_key=api_key)
        message = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": RESEARCH_PROMPT.format(
                    client_data=client_data,
                    job_summary=job_summary,
                ),
            }],
        )

        raw = strip_json_fences(message.content[0].text.strip())
        return json.loads(raw)

    except Exception:
        return dict(FALLBACK)
