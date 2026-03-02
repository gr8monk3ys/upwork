"""AI-powered profile completeness audit using Claude."""

import json
import re
from typing import Any

from anthropic import Anthropic

MODEL = "claude-sonnet-4-5-20250929"

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

FALLBACK_RESULT: dict[str, Any] = {
    "total_score": 0,
    "breakdown": [
        {"area": "Title", "score": 0, "feedback": "Could not analyze."},
        {"area": "Overview", "score": 0, "feedback": "Could not analyze."},
        {"area": "Skills", "score": 0, "feedback": "Could not analyze."},
        {"area": "Portfolio", "score": 0, "feedback": "Could not analyze."},
        {"area": "Rate & Experience", "score": 0, "feedback": "Could not analyze."},
    ],
    "top_3_improvements": [
        "Complete your profile to enable audit.",
    ],
}


def audit_profile(profile_text: str, api_key: str) -> dict[str, Any]:
    """Audit a freelancer profile for completeness and effectiveness.

    Args:
        profile_text: Detailed profile text (title, overview, skills, portfolio, etc.).
        api_key: Anthropic API key.

    Returns:
        Dict with ``total_score``, ``breakdown`` (per-area), and ``top_3_improvements``.
        Returns a fallback dict on failure.
    """
    try:
        client = Anthropic(api_key=api_key)
        message = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": AUDIT_PROMPT.format(profile_text=profile_text),
                }
            ],
        )

        raw = message.content[0].text.strip()
        # Strip markdown code fencing if present
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

        result = json.loads(raw)

        # Validate and clamp total_score
        result["total_score"] = max(0, min(100, int(result.get("total_score", 0))))

        return result

    except Exception:
        return dict(FALLBACK_RESULT)
