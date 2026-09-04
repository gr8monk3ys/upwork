"""Tests for the shared AI utility functions."""

from unittest.mock import MagicMock, patch

import anthropic
import pytest

from tests.conftest import mock_anthropic_response
from upwork_cli.ai.utils import (
    AIError,
    MissingAPIKey,
    complete,
    complete_json,
    extract_text,
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


class TestComplete:
    def test_returns_text(self):
        resp = mock_anthropic_response("output text")
        with patch("upwork_cli.ai.utils.Anthropic") as M:
            M.return_value.messages.create.return_value = resp
            assert complete("prompt", "key") == "output text"

    def test_passes_model_override(self):
        resp = mock_anthropic_response("ok")
        with patch("upwork_cli.ai.utils.Anthropic") as M:
            M.return_value.messages.create.return_value = resp
            complete("prompt", "key", model="claude-haiku-4-5")
            kwargs = M.return_value.messages.create.call_args.kwargs
            assert kwargs["model"] == "claude-haiku-4-5"

    def test_defaults_model(self):
        resp = mock_anthropic_response("ok")
        with patch("upwork_cli.ai.utils.Anthropic") as M:
            M.return_value.messages.create.return_value = resp
            complete("prompt", "key")
            kwargs = M.return_value.messages.create.call_args.kwargs
            assert kwargs["model"] == DEFAULT_MODEL

    def test_authentication_error(self):
        with patch("upwork_cli.ai.utils.Anthropic") as M:
            M.return_value.messages.create.side_effect = anthropic.AuthenticationError(
                message="bad key",
                response=MagicMock(status_code=401),
                body={"error": {"message": "bad key"}},
            )
            with pytest.raises(AIError, match="Invalid Anthropic API key"):
                complete("prompt", "bad-key")

    def test_rate_limit_error(self):
        with patch("upwork_cli.ai.utils.Anthropic") as M:
            M.return_value.messages.create.side_effect = anthropic.RateLimitError(
                message="slow down",
                response=MagicMock(status_code=429),
                body={"error": {"message": "slow down"}},
            )
            with pytest.raises(AIError, match="rate limit"):
                complete("prompt", "key")

    def test_generic_error_wrapped(self):
        with patch("upwork_cli.ai.utils.Anthropic") as M:
            M.return_value.messages.create.side_effect = Exception("boom")
            with pytest.raises(AIError, match="Anthropic call failed"):
                complete("prompt", "key")

    def test_no_text_content_raises(self):
        resp = MagicMock()
        resp.content = []
        with patch("upwork_cli.ai.utils.Anthropic") as M:
            M.return_value.messages.create.return_value = resp
            with pytest.raises(AIError, match="no text content"):
                complete("prompt", "key")

    def test_ai_error_is_runtime_error(self):
        assert issubclass(AIError, RuntimeError)


class TestConfigResolution:
    """api_key and model are resolved from settings when not passed."""

    def test_key_comes_from_settings(self, isolated_config, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "from-settings")
        resp = mock_anthropic_response("hi")
        with patch("upwork_cli.ai.utils.Anthropic") as M:
            M.return_value.messages.create.return_value = resp
            complete("prompt")
        assert M.call_args.kwargs["api_key"] == "from-settings"

    def test_an_explicit_key_wins(self, isolated_config, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "from-settings")
        resp = mock_anthropic_response("hi")
        with patch("upwork_cli.ai.utils.Anthropic") as M:
            M.return_value.messages.create.return_value = resp
            complete("prompt", "explicit", model="m")
        assert M.call_args.kwargs["api_key"] == "explicit"

    def test_model_defaults_when_settings_are_empty(self, isolated_config, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
        resp = mock_anthropic_response("hi")
        with patch("upwork_cli.ai.utils.Anthropic") as M:
            M.return_value.messages.create.return_value = resp
            complete("prompt")
        assert M.return_value.messages.create.call_args.kwargs["model"] == DEFAULT_MODEL

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
        require_api_key()  # does not raise


class TestCompleteJson:
    def test_parses_a_fenced_object(self, isolated_config):
        resp = mock_anthropic_response('```json\n{"a": 1}\n```')
        with patch("upwork_cli.ai.utils.Anthropic") as M:
            M.return_value.messages.create.return_value = resp
            assert complete_json("prompt", "key") == {"a": 1}

    def test_unusable_output_raises_for_every_caller(self, isolated_config):
        """One policy: modules used to variously raise or substitute a
        canned answer."""
        resp = mock_anthropic_response("not json at all")
        with patch("upwork_cli.ai.utils.Anthropic") as M:
            M.return_value.messages.create.return_value = resp
            with pytest.raises(AIError, match="Could not parse audit response"):
                complete_json("prompt", "key", what="audit response")
