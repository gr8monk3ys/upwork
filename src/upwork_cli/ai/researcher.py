"""AI-powered client research for Upwork jobs."""

import json
from typing import Any, Optional

from upwork_cli.ai.utils import complete, strip_json_fences

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

VALID_RISK_LEVELS = {"low", "medium", "high"}
VALID_SPENDING_TIERS = {"new", "small", "medium", "large", "enterprise"}

FALLBACK: dict[str, Any] = {
    "risk_level": "unknown",
    "spending_tier": "unknown",
    "brief": "Could not parse client analysis.",
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
    model: Optional[str] = None,
) -> dict[str, Any]:
    """Research a client based on available data.

    Returns dict with risk_level, spending_tier, brief, proposal_tips.
    Unknown or malformed model output is normalized; API failures raise AIError.

    Raises:
        AIError: If the API call fails.
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

    client_data = "\n".join(client_data_parts)

    raw = complete(
        RESEARCH_PROMPT.format(client_data=client_data, job_summary=job_summary),
        api_key,
        model=model,
        max_tokens=2048,
    )

    try:
        result = json.loads(strip_json_fences(raw.strip()))
    except json.JSONDecodeError:
        return dict(FALLBACK)
    if not isinstance(result, dict):
        return dict(FALLBACK)

    risk = str(result.get("risk_level", "")).lower()
    tier = str(result.get("spending_tier", "")).lower()
    return {
        "risk_level": risk if risk in VALID_RISK_LEVELS else "unknown",
        "spending_tier": tier if tier in VALID_SPENDING_TIERS else "unknown",
        "brief": str(result.get("brief", "")),
        "proposal_tips": str(result.get("proposal_tips", "")),
    }
