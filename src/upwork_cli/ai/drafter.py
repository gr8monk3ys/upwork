"""Generate tailored Upwork proposals using the Anthropic Claude API."""

from __future__ import annotations

import anthropic

from upwork_cli.config import load_profile, load_settings

MODEL = "claude-sonnet-4-5-20250929"

VALID_TONES = ("professional", "casual", "technical", "enthusiastic")
VALID_LENGTHS = ("short", "medium", "long")

LENGTH_GUIDANCE = {
    "short": "approximately 100 words",
    "medium": "approximately 200 words",
    "long": "approximately 350 words",
}

TONE_GUIDANCE = {
    "professional": (
        "Use a confident, polished, and professional tone. "
        "Be direct and results-oriented."
    ),
    "casual": (
        "Use a friendly, conversational tone. "
        "Write as if speaking to a colleague over coffee, while still being competent."
    ),
    "technical": (
        "Use a precise, technical tone. "
        "Lead with specific technologies, methodologies, and measurable outcomes."
    ),
    "enthusiastic": (
        "Use an energetic, enthusiastic tone. "
        "Show genuine excitement about the project while remaining credible."
    ),
}


def _build_system_prompt(tone: str, length: str, style_guide: str = "") -> str:
    """Build the system prompt for proposal generation."""
    prompt = (
        "You are an expert Upwork freelancer who writes winning proposals. "
        "You craft each proposal specifically for the job at hand.\n\n"
        "Rules:\n"
        "- Open with a hook that directly addresses the client's specific problem or goal. "
        "NEVER open with generic greetings like 'Dear Hiring Manager'.\n"
        "- Highlight 2-3 of the most relevant skills or past projects from the freelancer's profile "
        "that directly relate to what the client needs.\n"
        "- Demonstrate understanding of the client's problem by briefly restating it or "
        "identifying an aspect they may not have considered.\n"
        "- End with a clear, specific call to action (e.g., suggest a quick call, "
        "offer to share a relevant sample, propose a first step).\n"
        "- NEVER use Upwork cliches: no 'Dear Hiring Manager', no 'I am a top-rated freelancer', "
        "no 'I have read your job posting with great interest', no 'I am the perfect fit'.\n"
        "- Write in first person. Be human and specific, not templated.\n"
        "- Do NOT include a subject line or salutation. Jump straight into the proposal body.\n\n"
        f"Tone: {TONE_GUIDANCE[tone]}\n"
        f"Length: Keep the proposal to {LENGTH_GUIDANCE[length]}."
    )
    if style_guide:
        prompt += f"\n\nFollow these patterns from past winning proposals:\n{style_guide}"
    return prompt


def draft_proposal(
    job_summary: str,
    profile_summary: str,
    api_key: str,
    tone: str = "professional",
    length: str = "medium",
    style_guide: str = "",
) -> str:
    """Generate a tailored Upwork proposal for a specific job.

    Args:
        job_summary: Description of the job posting (title, requirements, skills, budget, etc.).
        profile_summary: The freelancer's profile summary (skills, experience, portfolio).
        api_key: Anthropic API key.
        tone: One of "professional", "casual", "technical", "enthusiastic".
        length: One of "short" (~100 words), "medium" (~200 words), "long" (~350 words).

    Returns:
        The generated proposal text.

    Raises:
        ValueError: If tone or length is not a valid option.
        anthropic.APIError: If the API call fails after handling.
    """
    if tone not in VALID_TONES:
        raise ValueError(f"Invalid tone '{tone}'. Must be one of: {', '.join(VALID_TONES)}")
    if length not in VALID_LENGTHS:
        raise ValueError(f"Invalid length '{length}'. Must be one of: {', '.join(VALID_LENGTHS)}")

    client = anthropic.Anthropic(api_key=api_key)

    user_message = (
        f"Write a proposal for this Upwork job.\n\n"
        f"--- JOB DETAILS ---\n{job_summary}\n\n"
        f"--- MY PROFILE ---\n{profile_summary}"
    )

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=_build_system_prompt(tone, length, style_guide),
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text
    except anthropic.AuthenticationError:
        raise RuntimeError(
            "Invalid Anthropic API key. Check your key in settings."
        )
    except anthropic.RateLimitError:
        raise RuntimeError(
            "Anthropic rate limit reached. Please wait a moment and try again."
        )
    except anthropic.APIError as exc:
        raise RuntimeError(f"Anthropic API error: {exc}") from exc


def refine_proposal(
    current_draft: str,
    feedback: str,
    api_key: str,
) -> str:
    """Refine an existing proposal based on user feedback.

    Args:
        current_draft: The current proposal text to refine.
        feedback: User instructions on what to change (e.g., "make it shorter",
                  "emphasize Python experience", "add a question about their timeline").
        api_key: Anthropic API key.

    Returns:
        The refined proposal text.
    """
    client = anthropic.Anthropic(api_key=api_key)

    system_prompt = (
        "You are an expert Upwork freelancer refining a proposal draft. "
        "Apply the user's feedback while preserving the overall structure and strengths "
        "of the original. Return ONLY the revised proposal text, no commentary."
    )

    user_message = (
        f"Here is my current proposal draft:\n\n"
        f"--- DRAFT ---\n{current_draft}\n\n"
        f"--- FEEDBACK ---\n{feedback}\n\n"
        f"Please revise the proposal based on the feedback above."
    )

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text
    except anthropic.AuthenticationError:
        raise RuntimeError(
            "Invalid Anthropic API key. Check your key in settings."
        )
    except anthropic.RateLimitError:
        raise RuntimeError(
            "Anthropic rate limit reached. Please wait a moment and try again."
        )
    except anthropic.APIError as exc:
        raise RuntimeError(f"Anthropic API error: {exc}") from exc
