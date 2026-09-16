"""Shared utilities for AI modules.

Callers may pass an API key and model explicitly, but do not have to: both
are resolved from settings when omitted, so the command layer stops relaying
configuration it never looks at.
"""

import json
import re
from typing import Any

import anthropic
from anthropic import Anthropic

from upwork_cli.config import DEFAULT_MODEL, load_settings


class AIError(RuntimeError):
    """Raised when a Claude API call fails or returns unusable output."""


class MissingAPIKey(AIError):
    """Raised when no Anthropic API key is configured."""

    def __init__(self) -> None:
        super().__init__(
            "Anthropic API key not configured. Run 'upwork config setup' to set it."
        )


def _resolve(api_key: str | None, model: str | None) -> tuple[str, str]:
    """Fill in the key and model from settings when not given."""
    if api_key and model:
        return api_key, model
    settings = load_settings()
    key = api_key or settings.anthropic_api_key
    if not key:
        raise MissingAPIKey()
    return key, model or settings.ai_model or DEFAULT_MODEL


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


def require_api_key() -> None:
    """Fail now if no API key is configured.

    Commands that cannot do anything useful without AI call this first, so
    the user is told about the missing key rather than about whatever they
    happened to run into on the way to the API call.
    """
    _resolve(None, None)


class AnthropicCompleter:
    """The adapter at the AI seam: the only place the vendor SDK appears.

    Translating Anthropic's exceptions into :class:`AIError` happens here, so
    an SDK upgrade touches one class and no test has to construct an
    ``anthropic.AuthenticationError`` to exercise the failure path.
    """

    def __init__(self, api_key: str) -> None:
        self._client = Anthropic(api_key=api_key)

    def __call__(
        self,
        *,
        prompt: str,
        model: str,
        system: str | None = None,
        max_tokens: int = 2048,
    ) -> str:
        request: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            request["system"] = system

        try:
            response = self._client.messages.create(**request)
        except anthropic.AuthenticationError as exc:
            raise AIError(
                "Invalid Anthropic API key. Check your key in settings."
            ) from exc
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

        return extract_text(response)


def get_completer(api_key: str) -> AnthropicCompleter:
    """The single construction site for the AI seam.

    Mirrors ``client.get_client``: one place builds the real adapter, so a
    test substitutes a fake here rather than patching the vendor's class
    name and hand-building its response objects.
    """
    return AnthropicCompleter(api_key)


def complete(
    prompt: str,
    api_key: str | None = None,
    *,
    model: str | None = None,
    system: str | None = None,
    max_tokens: int = 2048,
) -> str:
    """Run a single-turn completion and return the response text.

    Raises:
        MissingAPIKey: when no key is given and none is configured.
        AIError: on any API failure or if the response has no text content.
    """
    api_key, model = _resolve(api_key, model)
    text = get_completer(api_key)(
        prompt=prompt, model=model, system=system, max_tokens=max_tokens
    )
    if not text:
        raise AIError("Model response contained no text content.")
    return text


def complete_json(
    prompt: str,
    api_key: str | None = None,
    *,
    model: str | None = None,
    system: str | None = None,
    max_tokens: int = 2048,
    what: str = "response",
) -> Any:
    """Run a completion and parse its JSON body.

    One failure policy for every caller: unusable output raises AIError.
    Modules used to each decide separately -- two raised, one silently
    substituted a canned answer, which left the caller unable to tell a
    real analysis from a parse failure.
    """
    raw = complete(prompt, api_key, model=model, system=system, max_tokens=max_tokens)
    try:
        return json.loads(strip_json_fences(raw.strip()))
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise AIError(f"Could not parse {what}: {exc}") from exc
