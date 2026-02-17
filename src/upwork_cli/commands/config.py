"""CLI commands for setting up and managing Upwork CLI configuration."""

import re
import webbrowser
from datetime import datetime
from pathlib import Path

import click
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from upwork_cli.client import UpworkClient
from upwork_cli.config import (
    AUTH_FILE,
    PROFILE_FILE,
    SETTINGS_FILE,
    Profile,
    Settings,
    ensure_config_dir,
    load_auth,
    load_profile,
    load_settings,
    save_profile,
    save_settings,
)
from upwork_cli.db import init_db

console = Console()


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
        ## Portfolio
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

    # Title
    for key in ("professional title", "title"):
        if key in sections:
            profile_data["title"] = sections[key]
            break

    # Overview
    for key in ("professional overview", "overview"):
        if key in sections:
            profile_data["overview"] = sections[key]
            break

    # Skills — expect bullet list or comma-separated
    for key in ("skills to add", "skills"):
        if key in sections:
            raw = sections[key]
            skills: list[str] = []
            for sline in raw.splitlines():
                sline = sline.strip()
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

    # Hourly rate
    for key in ("hourly rate suggestion", "hourly rate"):
        if key in sections:
            profile_data["hourly_rate"] = sections[key]
            break

    # Portfolio
    for key in ("portfolio",):
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
                            {"name": current_name, "description": "\n".join(current_desc_lines).strip()}
                        )
                    current_name = sub_match.group(1).strip()
                    current_desc_lines = []
                elif pline_stripped:
                    cleaned = re.sub(r"^[-*]\s*", "", pline_stripped)
                    current_desc_lines.append(cleaned)

            if current_name is not None:
                portfolio.append(
                    {"name": current_name, "description": "\n".join(current_desc_lines).strip()}
                )

            if portfolio:
                profile_data["portfolio"] = portfolio
            break

    return profile_data


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
    settings.client_secret = click.prompt(
        "Client Secret", default=settings.client_secret or "", hide_input=True
    )
    settings.redirect_uri = click.prompt(
        "Redirect URI", default=settings.redirect_uri or "https://localhost:8080/callback"
    )

    # --- Optional integrations ---
    console.print("\n[bold cyan]Optional Integrations[/bold cyan]")
    anthropic_key = click.prompt(
        "Anthropic API Key (for AI features)",
        default=settings.anthropic_api_key or "",
        hide_input=True,
    )
    settings.anthropic_api_key = anthropic_key

    discord_url = click.prompt(
        "Discord Webhook URL (for notifications)",
        default=settings.discord_webhook_url or "",
    )
    settings.discord_webhook_url = discord_url

    save_settings(settings)
    console.print("\n[green]Settings saved.[/green]")

    # --- OAuth2 flow ---
    console.print("\n[bold cyan]Upwork OAuth2 Authorization[/bold cyan]")
    try:
        client = UpworkClient(settings=settings)
        auth_url = client.get_authorization_url()

        console.print(f"\nOpening authorization URL in your browser...\n[link={auth_url}]{auth_url}[/link]")
        webbrowser.open(auth_url)

        callback_url = click.prompt(
            "\nAfter authorizing, paste the full callback URL here"
        )
        token = client.complete_auth(callback_url)

        console.print("\n[green bold]Authentication successful![/green bold]")

        try:
            user_info = client.get_user_info()
            user = user_info.get("user", user_info) if isinstance(user_info, dict) else user_info
            name = user.get("first_name", "") + " " + user.get("last_name", "") if isinstance(user, dict) else str(user)
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
            expiry = datetime.fromtimestamp(auth.expires_at)
            if expiry > datetime.now():
                table.add_row("Token expiry", expiry.strftime("%Y-%m-%d %H:%M:%S"))
            else:
                table.add_row("Token expiry", f"[red]Expired ({expiry.strftime('%Y-%m-%d %H:%M:%S')})[/red]")
        else:
            table.add_row("Token expiry", "Unknown")
    else:
        table.add_row("Auth status", "[red]Not authenticated[/red]")
        table.add_row("Token expiry", "-")

    # Client ID (masked)
    if settings.client_id:
        masked = settings.client_id[:4] + "..." + settings.client_id[-4:] if len(settings.client_id) > 8 else "****"
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

    console.print(Panel(table, title="[bold]Configuration Status[/bold]", border_style="blue"))

    # If authenticated, try to show user info
    if auth:
        try:
            client = UpworkClient(settings=settings, token=auth)
            user_info = client.get_user_info()
            user = user_info.get("user", user_info) if isinstance(user_info, dict) else user_info
            if isinstance(user, dict):
                name = (user.get("first_name", "") + " " + user.get("last_name", "")).strip()
                email = user.get("email", "")
                info_parts = []
                if name:
                    info_parts.append(f"Name: [bold]{name}[/bold]")
                if email:
                    info_parts.append(f"Email: {email}")
                if info_parts:
                    console.print(Panel("\n".join(info_parts), title="[bold]User Info[/bold]", border_style="green"))
        except Exception:
            pass


# ---------------------------------------------------------------------------
# profile
# ---------------------------------------------------------------------------


@config.command()
@click.option("--file", "file_path", type=click.Path(exists=True), default=None, help="Path to a YAML or Markdown profile file.")
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
                console.print("[red]Could not extract profile fields from the Markdown file.[/red]")
                raise SystemExit(1)
            prof = Profile(
                title=data.get("title", ""),
                overview=data.get("overview", ""),
                skills=data.get("skills", []),
                portfolio=data.get("portfolio", []),
                hourly_rate=data.get("hourly_rate", ""),
            )
        elif ext in (".yaml", ".yml"):
            console.print(f"Loading YAML profile from [bold]{path}[/bold]...")
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                console.print("[red]YAML file must contain a mapping at the top level.[/red]")
                raise SystemExit(1)
            prof = Profile.from_dict(raw)
        else:
            console.print(f"[red]Unsupported file type: {ext}. Use .md or .yaml/.yml[/red]")
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
    console.print(Panel(prof.summary(), title="[bold]Profile Summary[/bold]", border_style="blue"))


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
    for filepath in (AUTH_FILE, SETTINGS_FILE, PROFILE_FILE):
        if filepath.exists():
            filepath.unlink()
            deleted.append(filepath.name)

    if deleted:
        console.print(f"[green]Deleted: {', '.join(deleted)}[/green]")
    else:
        console.print("[yellow]No configuration files found to delete.[/yellow]")

    console.print("[green]Configuration reset complete.[/green]")
