"""Shared utilities for AI modules."""

import re
from typing import Any, Optional

import anthropic
from anthropic import Anthropic

DEFAULT_MODEL = "claude-opus-5"


class AIError(RuntimeError):
    """Raised when a Claude API call fails or returns unusable output."""


def strip_json_fences(text: str) -> str:
    """Remove markdown code fences that LLMs sometimes wrap around JSON.

    Handles ````` ```json ... ``` ````` and plain ````` ``` ... ``` `````.
    """
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text


def extract_text(response: Any) -> str:
    """Join the text blocks of a Messages API response.

    Current models emit thinking blocks alongside text, so indexing
    ``response.content[0]`` is not safe.
    """
    parts = [
        block.text for block in response.content if getattr(block, "type", "") == "text"
    ]
    return "\n".join(parts).strip()


def complete(
    prompt: str,
    api_key: str,
    *,
    model: Optional[str] = None,
    system: Optional[str] = None,
    max_tokens: int = 2048,
) -> str:
    """Run a single-turn completion and return the response text.

    Raises:
        AIError: on any API failure or if the response has no text content.
    """
    client = Anthropic(api_key=api_key)
    request: dict[str, Any] = {
        "model": model or DEFAULT_MODEL,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        request["system"] = system

    try:
        response = client.messages.create(**request)
    except anthropic.AuthenticationError as exc:
        raise AIError("Invalid Anthropic API key. Check your key in settings.") from exc
    except anthropic.RateLimitError as exc:
        raise AIError(
            "Anthropic rate limit reached. Please wait a moment and try again."
        ) from exc
    except anthropic.APIStatusError as exc:
        raise AIError(
            f"Anthropic API error ({exc.status_code}): {exc.message}"
        ) from exc
    except anthropic.APIError as exc:
        raise AIError(f"Anthropic API error: {exc}") from exc
    except Exception as exc:
        raise AIError(f"Anthropic call failed: {exc}") from exc

    text = extract_text(response)
    if not text:
        raise AIError("Model response contained no text content.")
    return text
