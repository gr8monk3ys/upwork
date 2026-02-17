"""AI-powered proposal / cover letter generation for Upwork jobs."""

import os
import subprocess
import tempfile

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from upwork_cli.client import UpworkClient
from upwork_cli.config import load_settings, load_profile
from upwork_cli.db import (
    init_db,
    get_connection,
    save_proposal,
    get_proposals,
    get_jobs_with_scores,
)
from upwork_cli.ai.drafter import draft_proposal, refine_proposal

console = Console()


def _get_job_from_db(job_id: str) -> dict | None:
    """Look up a job from the local database by ID."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None


def _get_proposal_by_id(proposal_id: int) -> dict | None:
    """Load a single proposal by its integer ID."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM proposals WHERE id = ?", (proposal_id,)
        ).fetchone()
        return dict(row) if row else None


def _get_latest_proposal() -> dict | None:
    """Return the most recently created proposal."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM proposals ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def _open_in_editor(text: str) -> str:
    """Write *text* to a temp file, open ``$EDITOR``, and return the edited content."""
    editor = os.environ.get("EDITOR", "vi")
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as tmp:
        tmp.write(text)
        tmp_path = tmp.name

    try:
        subprocess.call([editor, tmp_path])
        with open(tmp_path, "r") as fh:
            return fh.read()
    finally:
        os.unlink(tmp_path)


def _copy_to_clipboard(text: str) -> bool:
    """Copy *text* to the system clipboard via pbcopy (macOS).

    Returns True on success, False otherwise.
    """
    try:
        proc = subprocess.Popen(
            ["pbcopy"], stdin=subprocess.PIPE, stderr=subprocess.DEVNULL
        )
        proc.communicate(input=text.encode("utf-8"))
        return proc.returncode == 0
    except FileNotFoundError:
        return False


# ---------------------------------------------------------------------------
# Click command group
# ---------------------------------------------------------------------------


@click.group()
def propose():
    """AI-powered proposal and cover letter tools."""
    init_db()


# ---------------------------------------------------------------------------
# propose generate
# ---------------------------------------------------------------------------


@propose.command()
@click.argument("job_id")
@click.option(
    "--tone",
    type=click.Choice(["professional", "casual", "technical", "enthusiastic"]),
    default="professional",
    show_default=True,
    help="Tone for the generated cover letter.",
)
@click.option(
    "--length",
    type=click.Choice(["short", "medium", "long"]),
    default="medium",
    show_default=True,
    help="Desired length of the proposal.",
)
@click.option(
    "--edit",
    "open_editor",
    is_flag=True,
    default=False,
    help="Open the generated proposal in $EDITOR for manual tweaking.",
)
def generate(job_id: str, tone: str, length: str, open_editor: bool):
    """Generate a tailored cover letter for JOB_ID."""

    settings = load_settings()
    profile = load_profile()

    if not settings.anthropic_api_key:
        console.print(
            "[red]Anthropic API key not configured.[/red] "
            "Run [bold]upwork configure[/bold] first."
        )
        raise SystemExit(1)

    if not profile.title:
        console.print(
            "[yellow]Warning:[/yellow] Profile is empty. "
            "Run [bold]upwork profile[/bold] to set up your profile for better proposals."
        )

    # 1. Load job ----------------------------------------------------------
    job = _get_job_from_db(job_id)
    if job is None:
        console.print(f"[dim]Job {job_id} not in local cache. Fetching from API...[/dim]")
        try:
            client = UpworkClient(settings=settings)
            job_data = client.get_job_detail(job_id)
            # Persist to DB for future use
            from upwork_cli.db import upsert_job
            from upwork_cli.models import JobPosting

            posting = JobPosting.from_rest(job_data)
            upsert_job(posting.to_db_dict())
            job = _get_job_from_db(job_id)
        except Exception as exc:
            console.print(f"[red]Failed to fetch job {job_id}:[/red] {exc}")
            raise SystemExit(1)

    if job is None:
        console.print(f"[red]Job {job_id} could not be loaded.[/red]")
        raise SystemExit(1)

    job_title = job.get("title", "Untitled")

    # 2. Build summaries for the AI ----------------------------------------
    job_parts = [f"Title: {job.get('title', '')}"]
    if job.get("description"):
        job_parts.append(f"Description: {job['description'][:1000]}")
    if job.get("skills"):
        skills = job["skills"]
        if isinstance(skills, str):
            job_parts.append(f"Skills: {skills}")
        else:
            job_parts.append(f"Skills: {', '.join(skills)}")
    if job.get("budget_amount"):
        job_parts.append(f"Budget: ${job['budget_amount']:,.0f}")
    if job.get("duration"):
        job_parts.append(f"Duration: {job['duration']}")
    if job.get("engagement"):
        job_parts.append(f"Engagement: {job['engagement']}")
    job_summary = "\n".join(job_parts)

    profile_summary = profile.summary() if profile.title else ""

    # 2b. Draft proposal ---------------------------------------------------
    with console.status("[bold green]Generating proposal..."):
        content = draft_proposal(
            job_summary=job_summary,
            profile_summary=profile_summary,
            api_key=settings.anthropic_api_key,
            tone=tone,
            length=length,
        )

    # 3. Optional editor pass ----------------------------------------------
    if open_editor:
        content = _open_in_editor(content)

    # 4. Save to DB --------------------------------------------------------
    proposal_id = save_proposal(
        job_id=job_id,
        job_title=job_title,
        content=content,
        tone=tone,
    )

    # 5. Display -----------------------------------------------------------
    console.print()
    console.print(
        Panel(
            Markdown(content),
            title=f"Proposal #{proposal_id} — {job_title}",
            subtitle=f"tone={tone}  length={length}",
            border_style="green",
        )
    )
    console.print(
        f"\n[dim]Saved as proposal [bold]#{proposal_id}[/bold]. "
        f"Use [bold]propose show {proposal_id}[/bold] to view again.[/dim]"
    )


# ---------------------------------------------------------------------------
# propose refine
# ---------------------------------------------------------------------------


@propose.command()
@click.option(
    "--feedback",
    type=str,
    default=None,
    help="Describe what to change (e.g. 'make it shorter', 'emphasize Python skills').",
)
def refine(feedback: str | None):
    """Refine the most recent proposal based on feedback."""

    settings = load_settings()

    if not settings.anthropic_api_key:
        console.print(
            "[red]Anthropic API key not configured.[/red] "
            "Run [bold]upwork configure[/bold] first."
        )
        raise SystemExit(1)

    # Load most recent proposal
    proposal = _get_latest_proposal()
    if proposal is None:
        console.print("[red]No proposals found.[/red] Generate one first with [bold]propose generate[/bold].")
        raise SystemExit(1)

    original_content = proposal["content"]
    job_id = proposal["job_id"]
    job_title = proposal.get("job_title", "Untitled")
    tone = proposal.get("tone", "professional")

    if feedback is None:
        feedback = click.prompt("What would you like to change?")

    # Refine
    with console.status("[bold green]Refining proposal..."):
        refined_content = refine_proposal(
            current_draft=original_content,
            feedback=feedback,
            api_key=settings.anthropic_api_key,
        )

    # Save refined version as a new proposal
    new_id = save_proposal(
        job_id=job_id,
        job_title=job_title,
        content=refined_content,
        tone=tone,
    )

    # Show before / after
    console.print()
    console.print(
        Panel(
            Markdown(original_content),
            title=f"BEFORE — Proposal #{proposal['id']}",
            border_style="red",
        )
    )
    console.print()
    console.print(
        Panel(
            Markdown(refined_content),
            title=f"AFTER — Proposal #{new_id}",
            border_style="green",
        )
    )
    console.print(f"\n[dim]Refined proposal saved as [bold]#{new_id}[/bold].[/dim]")


# ---------------------------------------------------------------------------
# propose history
# ---------------------------------------------------------------------------


@propose.command()
@click.option(
    "--limit",
    type=int,
    default=20,
    show_default=True,
    help="Maximum number of proposals to list.",
)
def history(limit: int):
    """List past proposals."""

    proposals = get_proposals(limit=limit)

    if not proposals:
        console.print("[dim]No proposals yet.[/dim]")
        return

    table = Table(title="Proposal History", show_lines=True)
    table.add_column("ID", style="bold cyan", justify="right")
    table.add_column("Job Title", style="white", max_width=40)
    table.add_column("Tone", style="magenta")
    table.add_column("Date", style="green")
    table.add_column("Preview", style="dim", max_width=80)

    for p in proposals:
        preview = (p.get("content") or "")[:80].replace("\n", " ")
        if len(p.get("content", "")) > 80:
            preview += "..."
        table.add_row(
            str(p["id"]),
            p.get("job_title", "—"),
            p.get("tone", "—"),
            p.get("created_at", "—"),
            preview,
        )

    console.print(table)


# ---------------------------------------------------------------------------
# propose show
# ---------------------------------------------------------------------------


@propose.command()
@click.argument("proposal_id", type=int)
@click.option(
    "--copy",
    "copy_to_clip",
    is_flag=True,
    default=False,
    help="Copy the proposal text to the clipboard (macOS pbcopy).",
)
def show(proposal_id: int, copy_to_clip: bool):
    """Show the full text of PROPOSAL_ID."""

    proposal = _get_proposal_by_id(proposal_id)

    if proposal is None:
        console.print(f"[red]Proposal #{proposal_id} not found.[/red]")
        raise SystemExit(1)

    content = proposal["content"]
    job_title = proposal.get("job_title", "Untitled")
    tone = proposal.get("tone", "")
    created = proposal.get("created_at", "")

    console.print()
    console.print(
        Panel(
            Markdown(content),
            title=f"Proposal #{proposal_id} — {job_title}",
            subtitle=f"tone={tone}  created={created}",
            border_style="blue",
        )
    )

    if copy_to_clip:
        if _copy_to_clipboard(content):
            console.print("\n[green]Copied to clipboard.[/green]")
        else:
            console.print(
                "\n[red]Failed to copy to clipboard.[/red] "
                "[dim](pbcopy not available — macOS only)[/dim]"
            )
