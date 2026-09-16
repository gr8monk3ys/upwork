"""Tests for configuration dataclasses and persistence in upwork_cli.config."""

from upwork_cli.config import (
    AuthToken,
    Profile,
    Settings,
    _get_secret,
    load_auth,
    load_profile,
    load_settings,
    save_auth,
    save_profile,
    save_settings,
    secret_source,
    set_secret,
)


class TestAuthToken:
    def test_roundtrip(self):
        token = AuthToken(
            access_token="acc",
            refresh_token="ref",
            token_type="Bearer",
            expires_at=1700000000.0,
        )
        d = token.to_dict()
        restored = AuthToken.from_dict(d)
        assert restored.access_token == "acc"
        assert restored.refresh_token == "ref"
        assert restored.expires_at == 1700000000.0

    def test_save_and_load(self, isolated_config):
        token = AuthToken(access_token="a", refresh_token="r", expires_at=99.0)
        save_auth(token)
        loaded = load_auth()
        assert loaded is not None
        assert loaded.access_token == "a"
        assert loaded.refresh_token == "r"

    def test_load_missing_returns_none(self, isolated_config):
        assert load_auth() is None

    def test_load_corrupt_file_returns_none(self, isolated_config):
        from upwork_cli.config import AUTH_FILE

        AUTH_FILE.write_text("NOT JSON")
        assert load_auth() is None


class TestSettings:
    def test_roundtrip(self):
        s = Settings(
            client_id="cid", redirect_uri="http://localhost", watch_interval_minutes=10
        )
        d = s.to_dict()
        restored = Settings.from_dict(d)
        assert restored.client_id == "cid"
        assert restored.watch_interval_minutes == 10

    def test_save_and_load(self, isolated_config):
        s = Settings(client_id="test-id")
        save_settings(s)
        loaded = load_settings()
        assert loaded.client_id == "test-id"

    def test_load_missing_returns_defaults(self, isolated_config):
        s = load_settings()
        assert s.client_id == ""

    def test_corrupt_yaml_returns_defaults(self, isolated_config):
        from upwork_cli.config import SETTINGS_FILE

        SETTINGS_FILE.write_text(": bad: yaml: [")
        s = load_settings()
        assert s.client_id == ""

    def test_save_settings_keeps_existing_secret_when_none(
        self, isolated_config, mock_keyring
    ):
        set_secret("anthropic_api_key", "sk-existing")
        save_settings(Settings(client_id="test-id"), anthropic_api_key=None)
        assert _get_secret("anthropic_api_key") == "sk-existing"

    def test_save_settings_clears_secret_with_empty_string(
        self, isolated_config, mock_keyring
    ):
        set_secret("anthropic_api_key", "sk-existing")
        save_settings(Settings(client_id="test-id"), anthropic_api_key="")
        assert _get_secret("anthropic_api_key") == ""


class TestProfile:
    def test_roundtrip(self):
        p = Profile(title="Dev", skills=["Python"], experience_years=5)
        d = p.to_dict()
        restored = Profile.from_dict(d)
        assert restored.title == "Dev"
        assert restored.skills == ["Python"]
        assert restored.experience_years == 5

    def test_save_and_load(self, isolated_config):
        p = Profile(title="Test Dev", overview="I build stuff.", skills=["Go"])
        save_profile(p)
        loaded = load_profile()
        assert loaded.title == "Test Dev"
        assert loaded.skills == ["Go"]

    def test_summary_output(self):
        p = Profile(
            title="Dev", overview="Overview.", skills=["A", "B"], hourly_rate="$50"
        )
        s = p.summary()
        assert "Title: Dev" in s
        assert "Skills: A, B" in s


class TestKeyringSecretIsolation:
    def test_set_and_get_secret(self, mock_keyring):
        set_secret("anthropic_api_key", "sk-test-123")
        assert _get_secret("anthropic_api_key") == "sk-test-123"

    def test_env_var_precedence(self, monkeypatch, mock_keyring):
        set_secret("anthropic_api_key", "from-keyring")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "from-env")
        assert _get_secret("anthropic_api_key") == "from-env"

    def test_get_secret_source_keyring(self, mock_keyring):
        set_secret("anthropic_api_key", "from-keyring")
        assert secret_source("anthropic_api_key") == "keyring"

    def test_get_secret_source_env(self, monkeypatch, mock_keyring):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "from-env")
        assert secret_source("anthropic_api_key") == "env:ANTHROPIC_API_KEY"
