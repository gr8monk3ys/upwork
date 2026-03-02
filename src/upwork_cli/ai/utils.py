"""Shared utilities for AI modules."""

import re

DEFAULT_MODEL = "claude-sonnet-4-5-20250929"


def strip_json_fences(text: str) -> str:
    """Remove markdown code fences that LLMs sometimes wrap around JSON.

    Handles ````` ```json ... ``` ````` and plain ````` ``` ... ``` `````.
    """
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text
