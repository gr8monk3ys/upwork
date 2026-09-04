"""Tests for the shared AI utility functions."""

from unittest.mock import MagicMock, patch

import anthropic
import pytest

from tests.conftest import mock_anthropic_response
from tests.fakes import FakeCompleter
from upwork_cli.ai.utils import (
    AIError,
    AnthropicCompleter,
    MissingAPIKey,
    complete,
    complete_json,
    extract_text,
    get_completer,
    require_api_key,
    strip_json_fences,
)
from upwork_cli.config import DEFAULT_MODEL


class TestStripJsonFences:
    def test_no_fences(self):
        text = '{"score": 8, "reasoning": "Good match"}'
        assert strip_json_fences(text) == text

    def test_json_fences(self):
        text = '```json\n{"score": 8}\n```'
        assert strip_json_fences(text) == '{"score": 8}'

    def test_plain_fences(self):
        text = '```\n{"key": "value"}\n```'
        assert strip_json_fences(text) == '{"key": "value"}'

    def test_nested_content(self):
        text = '```json\n{"code": "```inner```"}\n```'
        result = strip_json_fences(text)
        assert '"code"' in result

    def test_whitespace_handling(self):
        text = '```json\n  {"score": 5}  \n```'
        result = strip_json_fences(text)
        assert '{"score": 5}' in result

    def test_not_starting_with_fences(self):
        text = 'Some text ```json\n{"a":1}\n```'
        assert strip_json_fences(text) == text


class TestDefaultModel:
    def test_model_is_string(self):
        assert isinstance(DEFAULT_MODEL, str)

    def test_model_contains_claude(self):
        assert "claude" in DEFAULT_MODEL


class TestExtractText:
    def test_text_only(self):
        resp = mock_anthropic_response("hello")
        assert extract_text(resp) == "hello"

    def test_skips_thinking_blocks(self):
        resp = mock_anthropic_response("the answer", include_thinking=True)
        assert extract_text(resp) == "the answer"

    def test_empty_content(self):
        resp = MagicMock()
        resp.content = []
        assert extract_text(resp) == ""


class TestAnthropicCompleter:
    """The real adapter at the AI seam.

    This is the one place the vendor SDK belongs in a test: translating
    Anthropic's exceptions into AIError is exactly what this class is for.
    Every other AI test substitutes a FakeCompleter instead.
    """

    def test_returns_the_response_text(self):
        with patch("upwork_cli.ai.utils.Anthropic") as M:
            M.return_value.messages.create.return_value = mock_anthropic_response("out")
            assert AnthropicCompleter("key")(prompt="p", model="m") == "out"

    def test_thinking_blocks_are_skipped(self):
        with patch("upwork_cli.ai.utils.Anthropic") as M:
            M.return_value.messages.create.return_value = mock_anthropic_response(
                "body", include_thinking=True
            )
            assert AnthropicCompleter("key")(prompt="p", model="m") == "body"

    def test_the_request_carries_prompt_model_and_system(self):
        with patch("upwork_cli.ai.utils.Anthropic") as M:
            M.return_value.messages.create.return_value = mock_anthropic_response("ok")
            AnthropicCompleter("key")(
                prompt="p", model="claude-haiku-4-5", system="be brief", max_tokens=64
            )
            kwargs = M.return_value.messages.create.call_args.kwargs
            assert kwargs["model"] == "claude-haiku-4-5"
            assert kwargs["system"] == "be brief"
            assert kwargs["max_tokens"] == 64
            assert kwargs["messages"] == [{"role": "user", "content": "p"}]

    def test_no_system_key_when_none_is_given(self):
        with patch("upwork_cli.ai.utils.Anthropic") as M:
            M.return_value.messages.create.return_value = mock_anthropic_response("ok")
            AnthropicCompleter("key")(prompt="p", model="m")
            assert "system" not in M.return_value.messages.create.call_args.kwargs

    def test_authentication_error(self):
        with patch("upwork_cli.ai.utils.Anthropic") as M:
            M.return_value.messages.create.side_effect = anthropic.AuthenticationError(
                message="bad key",
                response=MagicMock(status_code=401),
                body={"error": {"message": "bad key"}},
            )
            with pytest.raises(AIError, match="Invalid Anthropic API key"):
                AnthropicCompleter("bad-key")(prompt="p", model="m")

    def test_rate_limit_error(self):
        with patch("upwork_cli.ai.utils.Anthropic") as M:
            M.return_value.messages.create.side_effect = anthropic.RateLimitError(
                message="slow down",
                response=MagicMock(status_code=429),
                body={"error": {"message": "slow down"}},
            )
            with pytest.raises(AIError, match="rate limit"):
                AnthropicCompleter("key")(prompt="p", model="m")

    def test_generic_error_wrapped(self):
        with patch("upwork_cli.ai.utils.Anthropic") as M:
            M.return_value.messages.create.side_effect = Exception("boom")
            with pytest.raises(AIError, match="Anthropic call failed"):
                AnthropicCompleter("key")(prompt="p", model="m")

    def test_get_completer_builds_one_with_the_key(self):
        with patch("upwork_cli.ai.utils.Anthropic") as M:
            get_completer("the-key")
            assert M.call_args.kwargs["api_key"] == "the-key"


class TestComplete:
    def test_returns_text(self, use_completer):
        use_completer(FakeCompleter("output text"))
        assert complete("prompt", "key") == "output text"

    def test_passes_model_override(self, use_completer):
        fake = use_completer(FakeCompleter("ok"))
        complete("prompt", "key", model="claude-haiku-4-5")
        assert fake.calls[-1]["model"] == "claude-haiku-4-5"

    def test_defaults_model(self, use_completer):
        fake = use_completer(FakeCompleter("ok"))
        complete("prompt", "key")
        assert fake.calls[-1]["model"] == DEFAULT_MODEL

    def test_no_text_content_raises(self, use_completer):
        use_completer(FakeCompleter(""))
        with pytest.raises(AIError, match="no text content"):
            complete("prompt", "key")

    def test_an_adapter_failure_reaches_the_caller(self, use_completer):
        use_completer(FakeCompleter(error=AIError("Anthropic call failed: boom")))
        with pytest.raises(AIError, match="Anthropic call failed"):
            complete("prompt", "key")

    def test_ai_error_is_runtime_error(self):
        assert issubclass(AIError, RuntimeError)


def _record_key(monkeypatch) -> dict:
    """Capture the api_key the seam is built with."""
    seen: dict = {}

    def build(key: str) -> FakeCompleter:
        seen["key"] = key
        return FakeCompleter("hi")

    monkeypatch.setattr("upwork_cli.ai.utils.get_completer", build)
    return seen


class TestConfigResolution:
    """api_key and model are resolved from settings when not passed."""

    def test_key_comes_from_settings(self, isolated_config, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "from-settings")
        seen = _record_key(monkeypatch)
        complete("prompt")
        assert seen["key"] == "from-settings"

    def test_an_explicit_key_wins(self, isolated_config, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "from-settings")
        seen = _record_key(monkeypatch)
        complete("prompt", "explicit", model="m")
        assert seen["key"] == "explicit"

    def test_model_defaults_when_settings_are_empty(
        self, isolated_config, monkeypatch, use_completer
    ):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
        fake = use_completer(FakeCompleter("hi"))
        complete("prompt")
        assert fake.calls[-1]["model"] == DEFAULT_MODEL

    def test_no_key_anywhere_raises(self, isolated_config, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(MissingAPIKey, match="not configured"):
            complete("prompt")

    def test_require_api_key_raises_early(self, isolated_config, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(MissingAPIKey):
            require_api_key()

    def test_require_api_key_passes_when_configured(self, isolated_config, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
        assert require_api_key() is None  # returns, rather than raising


class TestCompleteJson:
    def test_parses_a_fenced_object(self, isolated_config, use_completer):
        use_completer(FakeCompleter('```json\n{"a": 1}\n```'))
        assert complete_json("prompt", "key") == {"a": 1}

    def test_unusable_output_raises_for_every_caller(
        self, isolated_config, use_completer
    ):
        """One policy: modules used to variously raise or substitute a
        canned answer."""
        use_completer(FakeCompleter("not json at all"))
        with pytest.raises(AIError, match="Could not parse audit response"):
            complete_json("prompt", "key", what="audit response")
