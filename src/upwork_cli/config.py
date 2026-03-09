"""Configuration and token storage for the Upwork CLI."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import keyring
import yaml

CONFIG_DIR = Path.home() / ".config" / "upwork-cli"
AUTH_FILE = CONFIG_DIR / "auth.json"
PROFILE_FILE = CONFIG_DIR / "profile.yaml"
SETTINGS_FILE = CONFIG_DIR / "settings.yaml"
DB_FILE = CONFIG_DIR / "upwork.db"

KEYRING_SERVICE = "upwork-cli"
SECRET_ENV_MAP = {
    "client_secret": "UPWORK_CLIENT_SECRET",
    "anthropic_api_key": "ANTHROPIC_API_KEY",
    "discord_webhook_url": "DISCORD_WEBHOOK_URL",
}


def _get_secret(key: str) -> str:
    """Retrieve a secret: env var first, then keyring."""
    env_val = os.environ.get(SECRET_ENV_MAP.get(key, ""), "")
    if env_val:
        return env_val
    return keyring.get_password(KEYRING_SERVICE, key) or ""


def _get_secret_source(key: str) -> str:
    """Describe where a secret currently resolves from."""
    env_name = SECRET_ENV_MAP.get(key, "")
    if env_name and os.environ.get(env_name):
        return f"env:{env_name}"
    if keyring.get_password(KEYRING_SERVICE, key):
        return "keyring"
    return ""


def _set_secret(key: str, value: str) -> None:
    """Store a secret in the system keychain."""
    if value:
        keyring.set_password(KEYRING_SERVICE, key, value)
    else:
        try:
            keyring.delete_password(KEYRING_SERVICE, key)
        except keyring.errors.PasswordDeleteError:
            pass


def ensure_config_dir() -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR


@dataclass
class AuthToken:
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": self.token_type,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuthToken":
        return cls(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            token_type=data.get("token_type", "Bearer"),
            expires_at=data.get("expires_at", 0.0),
        )


@dataclass
class Settings:
    client_id: str = ""
    redirect_uri: str = "https://localhost:8080/callback"
    default_search_terms: list[str] = field(default_factory=list)
    watch_interval_minutes: int = 5
    min_score_threshold: int = 7

    @property
    def client_secret(self) -> str:
        return _get_secret("client_secret")

    @property
    def anthropic_api_key(self) -> str:
        return _get_secret("anthropic_api_key")

    @property
    def discord_webhook_url(self) -> str:
        return _get_secret("discord_webhook_url")

    def to_dict(self) -> dict[str, Any]:
        """Non-secret settings only — for writing to YAML."""
        return {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "default_search_terms": self.default_search_terms,
            "watch_interval_minutes": self.watch_interval_minutes,
            "min_score_threshold": self.min_score_threshold,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Settings":
        safe_keys = {k for k in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in safe_keys})


@dataclass
class Profile:
    title: str = ""
    overview: str = ""
    skills: list[str] = field(default_factory=list)
    portfolio: list[dict[str, str]] = field(default_factory=list)
    hourly_rate: str = ""
    experience_years: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "overview": self.overview,
            "skills": self.skills,
            "portfolio": self.portfolio,
            "hourly_rate": self.hourly_rate,
            "experience_years": self.experience_years,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Profile":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def summary(self) -> str:
        parts = []
        if self.title:
            parts.append(f"Title: {self.title}")
        if self.overview:
            parts.append(f"Overview: {self.overview}")
        if self.skills:
            parts.append(f"Skills: {', '.join(self.skills)}")
        if self.hourly_rate:
            parts.append(f"Rate: {self.hourly_rate}")
        if self.portfolio:
            items = [
                f"  - {p.get('name', 'Untitled')}: {p.get('description', '')}"
                for p in self.portfolio
            ]
            parts.append("Portfolio:\n" + "\n".join(items))
        return "\n".join(parts)


def save_auth(token: AuthToken) -> None:
    ensure_config_dir()
    AUTH_FILE.write_text(json.dumps(token.to_dict(), indent=2))
    AUTH_FILE.chmod(0o600)


def load_auth() -> Optional[AuthToken]:
    if not AUTH_FILE.exists():
        return None
    try:
        data = json.loads(AUTH_FILE.read_text())
        return AuthToken.from_dict(data)
    except (json.JSONDecodeError, KeyError):
        return None


def save_settings(
    settings: Settings,
    client_secret: Optional[str] = None,
    anthropic_api_key: Optional[str] = None,
    discord_webhook_url: Optional[str] = None,
) -> None:
    """Save settings to YAML and secrets to keyring."""
    ensure_config_dir()
    SETTINGS_FILE.write_text(yaml.dump(settings.to_dict(), default_flow_style=False))
    SETTINGS_FILE.chmod(0o600)
    if client_secret is not None:
        _set_secret("client_secret", client_secret)
    if anthropic_api_key is not None:
        _set_secret("anthropic_api_key", anthropic_api_key)
    if discord_webhook_url is not None:
        _set_secret("discord_webhook_url", discord_webhook_url)


def load_settings() -> Settings:
    if not SETTINGS_FILE.exists():
        return Settings()
    try:
        data = yaml.safe_load(SETTINGS_FILE.read_text()) or {}
    except yaml.YAMLError:
        return Settings()

    # Migrate legacy secrets from YAML into keyring
    migrated = False
    for secret_key in ("client_secret", "anthropic_api_key", "discord_webhook_url"):
        if data.get(secret_key) and data[secret_key] not in ("", "''"):
            _set_secret(secret_key, data[secret_key])
            del data[secret_key]
            migrated = True

    settings = Settings.from_dict(data)

    if migrated:
        SETTINGS_FILE.write_text(
            yaml.dump(settings.to_dict(), default_flow_style=False)
        )
        SETTINGS_FILE.chmod(0o600)

    return settings


def save_profile(profile: Profile) -> None:
    ensure_config_dir()
    PROFILE_FILE.write_text(yaml.dump(profile.to_dict(), default_flow_style=False))


def load_profile() -> Profile:
    if not PROFILE_FILE.exists():
        return Profile()
    try:
        data = yaml.safe_load(PROFILE_FILE.read_text())
        return Profile.from_dict(data or {})
    except yaml.YAMLError:
        return Profile()
