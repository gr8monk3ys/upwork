"""Extract winning patterns from past proposals to build a style guide."""

from upwork_cli.ai.utils import complete

LEARNER_PROMPT = """\
You are an expert Upwork proposal analyst. Analyze these winning proposals and \
extract a reusable style guide (~300 words).

**Winning Proposals:**
{proposals_text}

Extract patterns covering:
1. **Opening Patterns** — How do successful proposals start?
2. **Proof Points** — What types of evidence are used?
3. **Calls to Action** — How do they close?
4. **Tone & Style** — What voice works best?
5. **Key Phrases** — Effective language patterns

Return ONLY the style guide text, no preamble. Write it as instructions for \
generating future proposals (use imperative voice).
"""


def extract_winning_patterns(
    proposals: list[dict], api_key: str | None = None, model: str | None = None
) -> str:
    """Analyze winning proposals and extract a style guide.

    Args:
        proposals: List of proposal dicts with 'content', 'job_title', 'tone' keys.
        api_key: Anthropic API key; resolved from settings when omitted.
        model: Claude model ID; defaults to the configured/default model.

    Returns:
        Style guide string (~300 words).

    Raises:
        RuntimeError: If there are no proposals to analyze.
        AIError: If the API call fails.
    """
    if not proposals:
        raise RuntimeError("No winning proposals to analyze.")

    parts = []
    for i, proposal in enumerate(proposals, 1):
        parts.append(
            f"--- Proposal {i} (Job: {proposal.title}, Tone: {proposal.tone}) ---"
            f"\n{proposal.content}"
        )

    proposals_text = "\n\n".join(parts)

    return complete(
        LEARNER_PROMPT.format(proposals_text=proposals_text),
        api_key,
        model=model,
        max_tokens=2048,
    )
