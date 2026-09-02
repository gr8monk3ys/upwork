"""CLI commands for setting up and managing Upwork CLI configuration."""

import re
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

import click
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from upwork_cli.client import UpworkClient
from upwork_cli.config import (
    AUTH_FILE,
    DB_FILE,
    PROFILE_FILE,
    SECRET_ENV_MAP,
    SETTINGS_FILE,
    Profile,
    _get_secret_source,
    _set_secret,
    ensure_config_dir,
    load_auth,
    load_profile,
    load_settings,
    save_profile,
    save_settings,
)
from upwork_cli.db import init_db

console = Console()

SECRET_LABELS = {
    "client_secret": "Client Secret",
    "anthropic_api_key": "Anthropic API Key",
    "discord_webhook_url": "Discord Webhook URL",
}

SECRET_CLI_NAMES = {
    "client-secret": "client_secret",
    "anthropic-api-key": "anthropic_api_key",
    "discord-webhook": "discord_webhook_url",
}


# ---------------------------------------------------------------------------
# Markdown profile parser
# ---------------------------------------------------------------------------


def _parse_markdown_profile(text: str) -> dict:
    """Parse a markdown file with ## headings into profile fields.

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
                                "description": "\n".join(current_desc_lines).strip(),
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
        years_match = re.search(r"(\d+)\+?\s*years?\b", overview_text, re.IGNORECASE)
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
                            end_year = current_year if end == "Present" else int(end)
                            total = max(total, end_year - int(start))
                        if total > 0:
                            profile_data["experience_years"] = total
                    break

    return profile_data


def _describe_secret_source(secret_key: str) -> str:
    """Return a human-readable description of the active secret source."""
    source = _get_secret_source(secret_key)
    if source.startswith("env:"):
        env_name = source.split(":", 1)[1]
        return f"environment variable ({env_name})"
    if source == "keyring":
        return "system keychain"
    return "not set"


def _prompt_secret_value(secret_key: str, hide_input: bool = True) -> str | None:
    """Prompt for a secret without echoing the current value back to the user."""
    label = SECRET_LABELS[secret_key]
    source_label = _describe_secret_source(secret_key)
    console.print(
        f"[dim]{label}: currently {source_label}. "
        "Press Enter to keep it, or type 'clear' to remove the keychain value.[/dim]"
    )
    value = click.prompt(
        label, default="", show_default=False, hide_input=hide_input
    ).strip()
    if not value:
        return None
    if value.lower() == "clear":
        return ""
    return value


# ---------------------------------------------------------------------------
# Click command group
# ---------------------------------------------------------------------------


@click.group()
def config():
    """Set up and manage the Upwork CLI configuration."""


# ---------------------------------------------------------------------------
# setup
# ---------------------------------------------------------------------------


@config.command()
def setup():
    """Interactive setup wizard for Upwork CLI."""
    console.print(Panel("[bold]Upwork CLI Setup Wizard[/bold]", style="blue"))

    ensure_config_dir()
    init_db()

    settings = load_settings()

    # --- Upwork API credentials ---
    console.print("\n[bold cyan]Upwork API Credentials[/bold cyan]")
    settings.client_id = click.prompt("Client ID", default=settings.client_id or "")
    client_secret = _prompt_secret_value("client_secret", hide_input=True)
    settings.redirect_uri = click.prompt(
        "Redirect URI",
        default=settings.redirect_uri or "https://localhost:8080/callback",
    )

    # --- Optional integrations ---
    console.print("\n[bold cyan]Optional Integrations[/bold cyan]")
    anthropic_key = _prompt_secret_value("anthropic_api_key", hide_input=True)
    discord_url = _prompt_secret_value("discord_webhook_url", hide_input=False)

    save_settings(
        settings,
        client_secret=client_secret,
        anthropic_api_key=anthropic_key,
        discord_webhook_url=discord_url,
    )
    console.print(
        "\n[green]Settings saved (secrets stored in system keychain).[/green]"
    )

    # --- OAuth2 flow ---
    console.print("\n[bold cyan]Upwork OAuth2 Authorization[/bold cyan]")
    try:
        client = UpworkClient(settings=settings)
        auth_url = client.get_authorization_url()

        console.print(
            f"\nOpening authorization URL in your browser...\n[link={auth_url}]{auth_url}[/link]"
        )
        webbrowser.open(auth_url)

        callback_url = click.prompt(
            "\nAfter authorizing, paste the full callback URL here"
        )
        client.complete_auth(callback_url)

        console.print("\n[green bold]Authentication successful![/green bold]")

        try:
            user_info = client.get_user_info()
            user = (
                user_info.get("user", user_info)
                if isinstance(user_info, dict)
                else user_info
            )
            name = (
                user.get("first_name", "") + " " + user.get("last_name", "")
                if isinstance(user, dict)
                else str(user)
            )
            console.print(f"Logged in as: [bold]{name.strip()}[/bold]")
        except Exception:
            console.print("Authenticated (could not fetch user details).")

    except Exception as exc:
        console.print(f"\n[red]OAuth error: {exc}[/red]")
        console.print("You can retry with [bold]upwork config setup[/bold] later.")
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


@config.command()
def status():
    """Show current configuration status."""
    settings = load_settings()
    auth = load_auth()
    profile = load_profile()

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="bold")
    table.add_column("Value")

    # Auth status
    if auth:
        table.add_row("Auth status", "[green]Authenticated[/green]")
        if auth.expires_at:
            # Epoch seconds from the OAuth server; convert via UTC, then
            # render in the local zone for display.
            expiry = datetime.fromtimestamp(
                auth.expires_at, tz=timezone.utc
            ).astimezone()
            if expiry > datetime.now(timezone.utc):
                table.add_row("Token expiry", expiry.strftime("%Y-%m-%d %H:%M:%S"))
            else:
                table.add_row(
                    "Token expiry",
                    f"[red]Expired ({expiry.strftime('%Y-%m-%d %H:%M:%S')})[/red]",
                )
        else:
            table.add_row("Token expiry", "Unknown")
    else:
        table.add_row("Auth status", "[red]Not authenticated[/red]")
        table.add_row("Token expiry", "-")

    # Client ID (masked)
    if settings.client_id:
        masked = (
            settings.client_id[:4] + "..." + settings.client_id[-4:]
            if len(settings.client_id) > 8
            else "****"
        )
        table.add_row("Client ID", masked)
    else:
        table.add_row("Client ID", "[red]Not set[/red]")

    # Anthropic key
    if settings.anthropic_api_key:
        table.add_row("Anthropic API key", "[green]Set[/green]")
    else:
        table.add_row("Anthropic API key", "[yellow]Not set[/yellow]")

    # Discord webhook
    if settings.discord_webhook_url:
        table.add_row("Discord webhook", "[green]Set[/green]")
    else:
        table.add_row("Discord webhook", "[yellow]Not set[/yellow]")

    # Profile
    if profile.title:
        table.add_row("Profile", "[green]Loaded[/green]")
    else:
        table.add_row("Profile", "[yellow]Not loaded[/yellow]")

    table.add_row("Saved searches", str(len(settings.default_search_terms or [])))

    console.print(
        Panel(table, title="[bold]Configuration Status[/bold]", border_style="blue")
    )

    # If authenticated, try to show user info
    if auth:
        try:
            client = UpworkClient(settings=settings, token=auth)
            user_info = client.get_user_info()
            user = (
                user_info.get("user", user_info)
                if isinstance(user_info, dict)
                else user_info
            )
            if isinstance(user, dict):
                name = (
                    user.get("first_name", "") + " " + user.get("last_name", "")
                ).strip()
                email = user.get("email", "")
                info_parts = []
                if name:
                    info_parts.append(f"Name: [bold]{name}[/bold]")
                if email:
                    info_parts.append(f"Email: {email}")
                if info_parts:
                    console.print(
                        Panel(
                            "\n".join(info_parts),
                            title="[bold]User Info[/bold]",
                            border_style="green",
                        )
                    )
        except Exception:
            console.print("[dim](could not fetch user details)[/dim]")


@config.group("secrets", invoke_without_command=True)
@click.pass_context
def secrets(ctx: click.Context) -> None:
    """Inspect or clear secrets stored outside settings.yaml."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(secret_status)


@secrets.command("status")
def secret_status() -> None:
    """Show whether each secret comes from env, keyring, or nowhere."""
    table = Table(title="Secret Status", show_lines=True)
    table.add_column("Secret", style="bold cyan")
    table.add_column("Status")
    table.add_column("Source", style="magenta")

    for secret_key, label in SECRET_LABELS.items():
        source = _get_secret_source(secret_key)
        env_name = SECRET_ENV_MAP.get(secret_key, "")
        if source.startswith("env:"):
            status = "[green]Set[/green]"
            source_label = env_name
        elif source == "keyring":
            status = "[green]Set[/green]"
            source_label = "keyring"
        else:
            status = "[yellow]Not set[/yellow]"
            source_label = "-"
        table.add_row(label, status, source_label)

    console.print(table)


@secrets.command("clear")
@click.argument(
    "name", type=click.Choice(list(SECRET_CLI_NAMES.keys()), case_sensitive=False)
)
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt.")
def clear_secret(name: str, yes: bool) -> None:
    """Clear a single keyring-backed secret."""
    secret_key = SECRET_CLI_NAMES[name.lower()]
    label = SECRET_LABELS[secret_key]
    source = _get_secret_source(secret_key)
    env_name = SECRET_ENV_MAP.get(secret_key, "")

    if not yes and not click.confirm(f"Clear {label} from the system keychain?"):
        console.print("[yellow]Aborted.[/yellow]")
        return

    _set_secret(secret_key, "")

    if source.startswith("env:"):
        console.print(
            f"[yellow]{label} is still provided by {env_name}. "
            "Unset the environment variable if you want it fully removed.[/yellow]"
        )
    elif source == "keyring":
        console.print(f"[green]Cleared {label} from the system keychain.[/green]")
    else:
        console.print(f"[yellow]{label} was not set in the system keychain.[/yellow]")


# ---------------------------------------------------------------------------
# profile
# ---------------------------------------------------------------------------


@config.command()
@click.option(
    "--file",
    "file_path",
    type=click.Path(exists=True),
    default=None,
    help="Path to a YAML or Markdown profile file.",
)
def profile(file_path: str | None):
    """Import your freelancer profile."""
    if file_path:
        path = Path(file_path)
        ext = path.suffix.lower()

        if ext == ".md":
            console.print(f"Parsing Markdown profile from [bold]{path}[/bold]...")
            text = path.read_text(encoding="utf-8")
            data = _parse_markdown_profile(text)
            if not data:
                console.print(
                    "[red]Could not extract profile fields from the Markdown file.[/red]"
                )
                raise SystemExit(1)
            prof = Profile(
                title=data.get("title", ""),
                overview=data.get("overview", ""),
                skills=data.get("skills", []),
                portfolio=data.get("portfolio", []),
                hourly_rate=data.get("hourly_rate", ""),
                experience_years=data.get("experience_years", 0),
            )
        elif ext in (".yaml", ".yml"):
            console.print(f"Loading YAML profile from [bold]{path}[/bold]...")
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                console.print(
                    "[red]YAML file must contain a mapping at the top level.[/red]"
                )
                raise SystemExit(1)
            prof = Profile.from_dict(raw)
        else:
            console.print(
                f"[red]Unsupported file type: {ext}. Use .md or .yaml/.yml[/red]"
            )
            raise SystemExit(1)
    else:
        # Interactive prompts
        console.print(Panel("[bold]Profile Setup[/bold]", style="blue"))
        title = click.prompt("Professional title")
        overview = click.prompt("Professional overview")
        skills_raw = click.prompt("Skills (comma-separated)")
        hourly_rate = click.prompt("Hourly rate (e.g. $50/hr)")
        skills = [s.strip() for s in skills_raw.split(",") if s.strip()]
        prof = Profile(
            title=title,
            overview=overview,
            skills=skills,
            hourly_rate=hourly_rate,
        )

    save_profile(prof)
    console.print("\n[green]Profile saved![/green]\n")
    console.print(
        Panel(prof.summary(), title="[bold]Profile Summary[/bold]", border_style="blue")
    )


# ---------------------------------------------------------------------------
# reset
# ---------------------------------------------------------------------------


@config.command()
def reset():
    """Reset all configuration (auth, settings, profile)."""
    if not click.confirm("This will delete all configuration files. Continue?"):
        console.print("Aborted.")
        return

    deleted: list[str] = []
    style_guide_file = ensure_config_dir() / "style_guide.txt"
    for filepath in (AUTH_FILE, SETTINGS_FILE, PROFILE_FILE, DB_FILE, style_guide_file):
        if filepath.exists():
            filepath.unlink()
            deleted.append(filepath.name)

    # Clear secrets from keychain
    for key in ("client_secret", "anthropic_api_key", "discord_webhook_url"):
        _set_secret(key, "")

    if deleted:
        console.print(f"[green]Deleted: {', '.join(deleted)}[/green]")
    else:
        console.print("[yellow]No configuration files found to delete.[/yellow]")

    console.print(
        "[green]Configuration reset complete (keychain secrets cleared).[/green]"
    )


# ---------------------------------------------------------------------------
# audit
# ---------------------------------------------------------------------------


def _build_audit_summary(profile: Profile) -> str:
    """Build a detailed audit input string from a Profile."""
    parts = []
    if profile.title:
        parts.append(f"Title ({len(profile.title)} chars): {profile.title}")
    else:
        parts.append("Title: NOT SET")

    if profile.overview:
        parts.append(f"Overview ({len(profile.overview)} chars): {profile.overview}")
    else:
        parts.append("Overview: NOT SET")

    if profile.skills:
        parts.append(
            f"Skills ({len(profile.skills)} listed): {', '.join(profile.skills)}"
        )
    else:
        parts.append("Skills: NONE")

    if profile.portfolio:
        parts.append(f"Portfolio ({len(profile.portfolio)} items):")
        for p in profile.portfolio:
            name = p.get("name", "Untitled")
            desc = p.get("description", "")
            parts.append(f"  - {name}: {desc[:100]}")
    else:
        parts.append("Portfolio: NONE")

    if profile.hourly_rate:
        parts.append(f"Hourly Rate: {profile.hourly_rate}")
    else:
        parts.append("Hourly Rate: NOT SET")

    parts.append(f"Experience Years: {profile.experience_years or 'NOT SET'}")
    return "\n".join(parts)


@config.command()
def audit():
    """AI-powered profile completeness audit (scored 0-100)."""
    settings = load_settings()
    profile = load_profile()

    if not settings.anthropic_api_key:
        console.print(
            "[red]Anthropic API key not configured.[/red] "
            "Run [bold]upwork config setup[/bold] first."
        )
        raise SystemExit(1)

    if not profile.title and not profile.overview:
        console.print(
            "[yellow]Profile is empty.[/yellow] "
            "Run [bold]upwork config profile --file <path>[/bold] to import your profile first."
        )
        raise SystemExit(1)

    profile_text = _build_audit_summary(profile)

    from upwork_cli.ai.auditor import audit_profile

    with console.status("[bold green]Auditing your profile..."):
        try:
            result = audit_profile(
                profile_text, settings.anthropic_api_key, model=settings.ai_model
            )
        except RuntimeError as exc:
            console.print(f"[red]Profile audit failed:[/red] {exc}")
            raise SystemExit(1)

    total = result.get("total_score", 0)

    # Color coding
    if total >= 80:
        score_style = "bold green"
    elif total >= 60:
        score_style = "bold yellow"
    else:
        score_style = "bold red"

    console.print(f"\n[{score_style}]Profile Score: {total}/100[/{score_style}]\n")

    # Breakdown table
    table = Table(title="Score Breakdown", show_lines=True)
    table.add_column("Area", style="bold cyan")
    table.add_column("Score", justify="center", width=8)
    table.add_column("Feedback", max_width=60)

    for item in result.get("breakdown", []):
        area = item.get("area", "?")
        score = item.get("score", 0)
        feedback = item.get("feedback", "")
        if score >= 16:
            color = "green"
        elif score >= 12:
            color = "yellow"
        else:
            color = "red"
        table.add_row(area, f"[{color}]{score}/20[/{color}]", feedback)

    console.print(table)

    # Top improvements
    improvements = result.get("top_3_improvements", [])
    if improvements:
        console.print("\n[bold]Top Improvements:[/bold]")
        for i, tip in enumerate(improvements, 1):
            console.print(f"  {i}. {tip}")
