"""AI-powered profile completeness audit using Claude."""

from typing import Any

from upwork_cli.ai.utils import AIError, complete_json

AUDIT_PROMPT = """\
You are an expert Upwork profile consultant. Evaluate the following freelancer \
profile for completeness and effectiveness.

Score each area on a 0-20 scale (total 0-100):
1. **Title** (0-20) — Is it specific, keyword-rich, and compelling?
2. **Overview** (0-20) — Does it demonstrate value, include measurable results, and have a clear CTA?
3. **Skills** (0-20) — Are there enough relevant skills (10-15 ideal)? Do they match the title/overview?
4. **Portfolio** (0-20) — Are there enough portfolio items (3+ ideal) with descriptions?
5. **Rate & Experience** (0-20) — Is the rate set and competitive? Is experience documented?

---

**Profile to Audit:**
{profile_text}

---

Respond with ONLY valid JSON in this exact format (no markdown fencing):
{{
  "total_score": <integer 0-100>,
  "breakdown": [
    {{"area": "Title", "score": <0-20>, "feedback": "<1-2 sentences>"}},
    {{"area": "Overview", "score": <0-20>, "feedback": "<1-2 sentences>"}},
    {{"area": "Skills", "score": <0-20>, "feedback": "<1-2 sentences>"}},
    {{"area": "Portfolio", "score": <0-20>, "feedback": "<1-2 sentences>"}},
    {{"area": "Rate & Experience", "score": <0-20>, "feedback": "<1-2 sentences>"}}
  ],
  "top_3_improvements": [
    "<actionable improvement 1>",
    "<actionable improvement 2>",
    "<actionable improvement 3>"
  ]
}}
"""


def audit_profile(
    profile_text: str, api_key: str | None = None, model: str | None = None
) -> dict[str, Any]:
    """Audit a freelancer profile for completeness and effectiveness.

    Args:
        profile_text: Detailed profile text (title, overview, skills, portfolio, etc.).
        api_key: Anthropic API key; resolved from settings when omitted.
        model: Claude model ID; defaults to the configured/default model.

    Returns:
        Dict with ``total_score``, ``breakdown`` (per-area), and ``top_3_improvements``.

    Raises:
        AIError: If the API call fails or the response cannot be parsed.
    """
    result = complete_json(
        AUDIT_PROMPT.format(profile_text=profile_text),
        api_key,
        model=model,
        max_tokens=2048,
        what="audit response",
    )

    try:
        result["total_score"] = max(0, min(100, int(result.get("total_score", 0))))
    except (AttributeError, TypeError, ValueError) as exc:
        raise AIError(f"Could not parse audit response: {exc}") from exc
    if not isinstance(result.get("breakdown"), list):
        raise AIError("Audit response missing 'breakdown' list.")

    return result
