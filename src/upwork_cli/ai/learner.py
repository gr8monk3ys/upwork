"""Extract winning patterns from past proposals to build a style guide."""

from anthropic import Anthropic

from upwork_cli.ai.utils import DEFAULT_MODEL

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


def extract_winning_patterns(proposals: list[dict], api_key: str) -> str:
    """Analyze winning proposals and extract a style guide.

    Args:
        proposals: List of proposal dicts with 'content', 'job_title', 'tone' keys.
        api_key: Anthropic API key.

    Returns:
        Style guide string (~300 words).

    Raises:
        RuntimeError on failure.
    """
    if not proposals:
        raise RuntimeError("No winning proposals to analyze.")

    parts = []
    for i, p in enumerate(proposals, 1):
        title = p.get("job_title", "Untitled")
        content = p.get("content", "")
        tone = p.get("tone", "unknown")
        parts.append(f"--- Proposal {i} (Job: {title}, Tone: {tone}) ---\n{content}")

    proposals_text = "\n\n".join(parts)

    try:
        client = Anthropic(api_key=api_key)
        message = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": LEARNER_PROMPT.format(proposals_text=proposals_text),
            }],
        )
        return message.content[0].text

    except Exception as exc:
        raise RuntimeError(f"Pattern extraction failed: {exc}") from exc
