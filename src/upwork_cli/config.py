"""Configuration and token storage for the Upwork CLI."""

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import keyring
import yaml

#: Claude model used when settings do not name one.
DEFAULT_MODEL = "claude-opus-5"

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


def secret_source(key: str) -> str:
    """Describe where a secret currently resolves from.

    Part of the secret store's interface, alongside :func:`set_secret` and
    :func:`clear_secret`. Reading a secret's *value* is not: that happens
    through the matching ``Settings`` property, so no caller has to know
    which of env or keyring answered.
    """
    env_name = SECRET_ENV_MAP.get(key, "")
    if env_name and os.environ.get(env_name):
        return f"env:{env_name}"
    if keyring.get_password(KEYRING_SERVICE, key):
        return "keyring"
    return ""


def set_secret(key: str, value: str) -> None:
    """Store a secret in the system keychain. An empty value clears it."""
    if value:
        keyring.set_password(KEYRING_SERVICE, key, value)
    else:
        clear_secret(key)


def clear_secret(key: str) -> None:
    """Remove a secret from the system keychain, if it is there."""
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
    ai_model: str = DEFAULT_MODEL

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
            "ai_model": self.ai_model,
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

    @classmethod
    def from_markdown(cls, text: str) -> "Profile":
        """Build a Profile from a Markdown file with ## headings.

        Fields absent from the file keep their defaults, so a file holding
        only a title yields a Profile with only a title set.

        Supported headings (case-insensitive):
            ## Professional Title
            ## Professional Overview
            ## Skills to Add
            ## Hourly Rate Suggestion
            ## Portfolio / ## Portfolio Entries
            ## Employment History / ## Experience (for experience_years)
        """
        sections: dict[str, str] = {}
        current_heading: str | None = None
        lines_buffer: list[str] = []

        for line in text.splitlines():
            heading_match = re.match(r"^##\s+(.+)$", line)
            if heading_match:
                # Store the previous section
                if current_heading is not None:
                    sections[current_heading] = "\n".join(lines_buffer).strip()
                current_heading = heading_match.group(1).strip().lower()
                lines_buffer = []
            else:
                lines_buffer.append(line)

        # Store the last section
        if current_heading is not None:
            sections[current_heading] = "\n".join(lines_buffer).strip()

        profile_data: dict = {}

        # Title — strip markdown bold and surrounding whitespace/rules
        for key in ("professional title", "title"):
            if key in sections:
                title = sections[key].strip()
                title = re.sub(r"^---+\s*", "", title).strip()
                title = re.sub(r"\s*---+$", "", title).strip()
                title = title.strip("*")  # Remove bold markers
                profile_data["title"] = title
                break

        # Overview — strip trailing horizontal rules
        for key in ("professional overview", "overview"):
            if key in sections:
                overview = sections[key].strip()
                overview = re.sub(r"\s*---+\s*$", "", overview).strip()
                profile_data["overview"] = overview
                break

        # Skills — expect bullet list or comma-separated
        for key in ("skills to add", "skills"):
            if key in sections:
                raw = sections[key]
                skills: list[str] = []
                for sline in raw.splitlines():
                    sline = sline.strip()
                    # Skip sub-headings (### Category Name) and horizontal rules
                    if re.match(r"^#{1,6}\s+", sline) or sline.startswith("---"):
                        continue
                    # Strip leading bullet markers
                    sline = re.sub(r"^[-*]\s*", "", sline)
                    sline = sline.strip()
                    if not sline:
                        continue
                    # If line contains commas, split on them
                    if "," in sline:
                        skills.extend(s.strip() for s in sline.split(",") if s.strip())
                    else:
                        skills.append(sline)
                profile_data["skills"] = skills
                break

        # Hourly rate — extract the dollar range
        for key in ("hourly rate suggestion", "hourly rate"):
            if key in sections:
                rate_text = sections[key].strip()
                # Try to extract $XX-$XX/hr pattern
                rate_match = re.search(r"\$[\d,]+\s*[-–]\s*\$[\d,]+/hr", rate_text)
                if rate_match:
                    profile_data["hourly_rate"] = rate_match.group(0)
                else:
                    profile_data["hourly_rate"] = re.sub(
                        r"\s*---+\s*$", "", rate_text
                    ).strip()
                break

        # Portfolio
        for key in ("portfolio entries", "portfolio"):
            if key in sections:
                raw = sections[key]
                portfolio: list[dict[str, str]] = []
                current_name: str | None = None
                current_desc_lines: list[str] = []

                for pline in raw.splitlines():
                    pline_stripped = pline.strip()
                    # Sub-heading (### or bold **name**)
                    sub_match = re.match(r"^###\s+(.+)$", pline_stripped) or re.match(
                        r"^\*\*(.+?)\*\*$", pline_stripped
                    )
                    if sub_match:
                        if current_name is not None:
                            portfolio.append(
                                {
                                    "name": current_name,
                                    "description": "\n".join(
                                        current_desc_lines
                                    ).strip(),
                                }
                            )
                        current_name = sub_match.group(1).strip()
                        current_desc_lines = []
                    elif pline_stripped:
                        cleaned = re.sub(r"^[-*]\s*", "", pline_stripped)
                        current_desc_lines.append(cleaned)

                if current_name is not None:
                    portfolio.append(
                        {
                            "name": current_name,
                            "description": "\n".join(current_desc_lines).strip(),
                        }
                    )

                if portfolio:
                    profile_data["portfolio"] = portfolio
                break

        # Experience years — extract from overview ("X+ years") or employment history date ranges
        if "experience_years" not in profile_data:
            overview_text = profile_data.get("overview", "")
            years_match = re.search(
                r"(\d+)\+?\s*years?\b", overview_text, re.IGNORECASE
            )
            if years_match:
                profile_data["experience_years"] = int(years_match.group(1))
            else:
                # Fall back to employment history / experience sections
                for key in ("employment history", "experience"):
                    if key in sections:
                        # Look for year ranges like "2017 - Present" or "2019 - 2022"
                        year_ranges = re.findall(
                            r"(\d{4})\s*[-–]\s*(Present|\d{4})", sections[key]
                        )
                        if year_ranges:
                            current_year = datetime.now(timezone.utc).year
                            total = 0
                            for start, end in year_ranges:
                                end_year = (
                                    current_year if end == "Present" else int(end)
                                )
                                total = max(total, end_year - int(start))
                            if total > 0:
                                profile_data["experience_years"] = total
                        break

        return cls(**profile_data)

    @property
    def is_empty(self) -> bool:
        """True when no field has been filled in at all.

        Distinct from "not usable for scoring", which asks only about title
        and skills: a Profile carrying just an overview is thin but is still
        something the user wrote, so importing one is not an error.
        """
        return not any(
            (
                self.title,
                self.overview,
                self.skills,
                self.portfolio,
                self.hourly_rate,
                self.experience_years,
            )
        )

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


def load_auth() -> AuthToken | None:
    if not AUTH_FILE.exists():
        return None
    try:
        data = json.loads(AUTH_FILE.read_text())
        return AuthToken.from_dict(data)
    except (json.JSONDecodeError, KeyError):
        return None


def save_settings(
    settings: Settings,
    client_secret: str | None = None,
    anthropic_api_key: str | None = None,
    discord_webhook_url: str | None = None,
) -> None:
    """Save settings to YAML and secrets to keyring."""
    ensure_config_dir()
    SETTINGS_FILE.write_text(yaml.dump(settings.to_dict(), default_flow_style=False))
    SETTINGS_FILE.chmod(0o600)
    if client_secret is not None:
        set_secret("client_secret", client_secret)
    if anthropic_api_key is not None:
        set_secret("anthropic_api_key", anthropic_api_key)
    if discord_webhook_url is not None:
        set_secret("discord_webhook_url", discord_webhook_url)


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
            set_secret(secret_key, data[secret_key])
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
