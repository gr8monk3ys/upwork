"""AI-powered proposal / cover letter generation for Upwork jobs."""

import hashlib
import os
import shlex
import subprocess
import tempfile
from pathlib import Path

import click
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from upwork_cli import output
from upwork_cli.ai.drafter import draft_proposal, refine_proposal
from upwork_cli.ai.utils import require_api_key
from upwork_cli.client import UpworkClient
from upwork_cli.config import CONFIG_DIR, load_profile, load_settings
from upwork_cli.db import (
    get_job,
    get_latest_proposal,
    get_proposal,
    get_proposals,
    get_winning_proposals,
    init_db,
    mark_proposal_outcome,
    save_proposal,
    set_pipeline_stage,
    upsert_job,
)
from upwork_cli.models import JobPosting
from upwork_cli.output import console


def _open_in_editor(text: str) -> str:
    """Write *text* to a temp file, open ``$EDITOR``, and return the edited content."""
    editor = shlex.split(os.environ.get("EDITOR", "vi") or "vi")
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as tmp:
        tmp.write(text)
        tmp_path = tmp.name

    try:
        subprocess.call(editor + [tmp_path])
        with open(tmp_path, "r") as fh:
            return fh.read()
    finally:
        os.unlink(tmp_path)


CLIPBOARD_COMMANDS = (
    ["pbcopy"],  # macOS
    ["wl-copy"],  # Wayland
    ["xclip", "-selection", "clipboard"],  # X11
    ["xsel", "--clipboard", "--input"],  # X11
)


def _copy_to_clipboard(text: str) -> bool:
    """Copy *text* to the system clipboard, trying platform tools in order.

    Returns True on success, False otherwise.
    """
    for command in CLIPBOARD_COMMANDS:
        try:
            proc = subprocess.Popen(
                command, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL
            )
            proc.communicate(input=text.encode("utf-8"))
            if proc.returncode == 0:
                return True
        except FileNotFoundError:
            continue
    return False


def _job_from_description(
    text: str, title: str | None, job_id: str | None
) -> JobPosting:
    """Build and cache a job row from a pasted/filed job description.

    This is the API-free path: the description is the source of truth, so
    drafting works even without Upwork API access.
    """
    text = text.strip()
    if not text:
        raise click.UsageError("Job description file is empty.")

    if not title:
        first_line = next(
            (line.strip() for line in text.splitlines() if line.strip()), "Untitled"
        )
        title = first_line.lstrip("#").strip()[:80] or "Untitled"

    if not job_id:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
        job_id = f"manual-{digest}"

    posting = JobPosting(id=job_id, title=title, description=text)
    upsert_job(posting)
    return posting


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
@click.argument("job_id", required=False)
@click.option(
    "--from-file",
    "from_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help=(
        "Draft from a job description in a local file (paste the posting text). "
        "Works without any Upwork API access."
    ),
)
@click.option(
    "--title",
    type=str,
    default=None,
    help="Job title when using --from-file (defaults to the file's first line).",
)
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
@click.option(
    "--research/--no-research",
    default=True,
    show_default=True,
    help="Run AI client research before drafting.",
)
def generate(
    job_id: str | None,
    from_file: Path | None,
    title: str | None,
    tone: str,
    length: str,
    open_editor: bool,
    research: bool,
):
    """Generate a tailored cover letter for JOB_ID or a --from-file description."""

    if job_id is None and from_file is None:
        raise click.UsageError("Provide a JOB_ID or --from-file <path>.")

    require_api_key()
    settings = load_settings()
    profile = load_profile()

    if not profile.title:
        output.warn(
            "Warning: Profile is empty. "
            "Run [bold]upwork profile[/bold] to set up your profile for better proposals."
        )

    # 1. Load job ----------------------------------------------------------
    if from_file is not None:
        job = _job_from_description(
            from_file.read_text(encoding="utf-8"), title, job_id
        )
        job_id = job.id
    else:
        job = get_job(job_id)
    if job is None:
        console.print(
            f"[dim]Job {job_id} not in local cache. Fetching from API...[/dim]"
        )
        try:
            client = UpworkClient(settings=settings)
            job_data = client.get_job_detail(job_id)
            # Persist to DB for future use
            posting = JobPosting.from_rest(job_data)
            upsert_job(posting)
            job = get_job(job_id)
        except Exception as exc:
            console.print(
                "[dim]Tip: save the job posting text to a file and run "
                "[bold]propose generate --from-file <path>[/bold] — "
                "no API access needed.[/dim]"
            )
            output.fail(f"Failed to fetch job {job_id}: {exc}")

    if job is None:
        output.fail(f"Job {job_id} could not be loaded.")

    job_title = job.title or "Untitled"

    # 2. Build summaries for the AI ----------------------------------------
    job_summary = job.summary_for_ai()

    profile_summary = profile.summary() if profile.title else ""

    # 2a. Client research (optional) ---------------------------------------
    has_client_data = any(
        (
            job.client_total_spent,
            job.client_total_hires,
            job.client_feedback,
            job.client_country,
            job.client_verified,
        )
    )
    if research and not has_client_data:
        research = False
        console.print(
            "[dim]No client data available for this job — skipping client research.[/dim]"
        )
    if research:
        from upwork_cli.ai.researcher import research_client

        client_research = {}
        with console.status("[bold green]Researching client..."):
            try:
                client_research = research_client(
                    job_summary=job_summary,
                    total_spent=job.client_total_spent,
                    total_hires=job.client_total_hires,
                    feedback=job.client_feedback,
                    country=job.client_country,
                    verified=job.client_verified,
                )
            except RuntimeError as exc:
                console.print(
                    f"[yellow]Client research failed ({exc}) — drafting without it."
                )

        if client_research.get("brief"):
            console.print(
                Panel(
                    f"[bold]Risk:[/bold] {client_research.get('risk_level', '?')}\n"
                    f"[bold]Tier:[/bold] {client_research.get('spending_tier', '?')}\n\n"
                    f"{client_research.get('brief', '')}",
                    title="Client Research",
                    border_style="cyan",
                )
            )
            tips = client_research.get("proposal_tips", "")
            if tips:
                job_summary += f"\n\nClient Research Tips: {tips}"

    # 2b. Load cached style guide ------------------------------------------
    style_guide = ""
    style_guide_path = CONFIG_DIR / "style_guide.txt"
    if style_guide_path.exists():
        style_guide = style_guide_path.read_text(encoding="utf-8").strip()

    # 2c. Draft proposal ---------------------------------------------------
    with console.status("[bold green]Generating proposal..."):
        try:
            content = draft_proposal(
                job_summary=job_summary,
                profile_summary=profile_summary,
                tone=tone,
                length=length,
                style_guide=style_guide,
            )
        except RuntimeError as exc:
            output.fail(f"Proposal generation failed: {exc}")

    # 3. Optional editor pass ----------------------------------------------
    if open_editor:
        content = _open_in_editor(content)

    # 4. Save to DB and update pipeline ------------------------------------
    proposal_id = save_proposal(
        job_id=job_id,
        job_title=job_title,
        content=content,
        tone=tone,
    )
    # A draft is not an application — win-rate stats only count jobs you
    # actually submitted. Move to "applied" once the proposal is really sent.
    set_pipeline_stage(job_id, "drafted")

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
    console.print(
        f"[dim]After you submit it on Upwork, run "
        f"[bold]upwork pipeline move {job_id} applied[/bold] "
        f"so your win-rate stats stay honest.[/dim]"
    )


# ---------------------------------------------------------------------------
# propose refine
# ---------------------------------------------------------------------------


@propose.command()
@click.argument("proposal_id", type=int, required=False)
@click.option(
    "--feedback",
    type=str,
    default=None,
    help="Describe what to change (e.g. 'make it shorter', 'emphasize Python skills').",
)
def refine(proposal_id: int | None, feedback: str | None):
    """Refine PROPOSAL_ID (default: the most recent proposal) based on feedback."""

    require_api_key()

    if proposal_id is not None:
        proposal = get_proposal(proposal_id)
        if proposal is None:
            output.fail(f"Proposal #{proposal_id} not found.")
    else:
        proposal = get_latest_proposal()
        if proposal is None:
            output.fail(
                "No proposals found. Generate one first with "
                "[bold]propose generate[/bold]."
            )

    original_content = proposal["content"]
    job_id = proposal["job_id"]
    job_title = proposal.get("job_title", "Untitled")
    tone = proposal.get("tone", "professional")

    if feedback is None:
        feedback = click.prompt("What would you like to change?")

    # Refine
    with console.status("[bold green]Refining proposal..."):
        try:
            refined_content = refine_proposal(
                current_draft=original_content,
                feedback=feedback,
            )
        except RuntimeError as exc:
            output.fail(f"Refinement failed: {exc}")

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

    proposal = get_proposal(proposal_id)

    if proposal is None:
        output.fail(f"Proposal #{proposal_id} not found.")

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
            output.warn(
                "Failed to copy to clipboard "
                "(no clipboard tool found — install pbcopy, wl-copy, xclip, or xsel)."
            )


# ---------------------------------------------------------------------------
# propose prep
# ---------------------------------------------------------------------------


@propose.command()
@click.argument("job_id")
def prep(job_id: str):
    """Generate interview preparation notes for JOB_ID."""
    require_api_key()
    profile = load_profile()

    job = get_job(job_id)
    if job is None:
        output.fail(f"Job {job_id} not found in local cache.")

    job_summary = job.summary_for_ai()
    profile_summary = profile.summary() if profile.title else ""

    from upwork_cli.ai.interview_prep import generate_interview_prep

    with console.status("[bold green]Generating interview prep..."):
        try:
            prep_text = generate_interview_prep(
                job_summary=job_summary,
                profile_summary=profile_summary,
            )
        except RuntimeError as exc:
            output.fail(exc)

    console.print()
    console.print(
        Panel(
            Markdown(prep_text),
            title=f"Interview Prep — {job.title or 'Untitled'}",
            border_style="green",
        )
    )


# ---------------------------------------------------------------------------
# propose mark
# ---------------------------------------------------------------------------


@propose.command()
@click.argument("proposal_id", type=int)
@click.argument("outcome", type=click.Choice(["won", "lost", "no_response"]))
def mark(proposal_id: int, outcome: str):
    """Mark a proposal's outcome (won/lost/no_response)."""
    proposal = get_proposal(proposal_id)
    if proposal is None:
        output.fail(f"Proposal #{proposal_id} not found.")

    mark_proposal_outcome(proposal_id, outcome)

    # If won, also move pipeline stage
    if outcome == "won" and proposal.get("job_id"):
        set_pipeline_stage(proposal["job_id"], "won")
    elif outcome == "lost" and proposal.get("job_id"):
        set_pipeline_stage(proposal["job_id"], "lost")

    colors = {"won": "green", "lost": "red", "no_response": "yellow"}
    color = colors.get(outcome, "white")
    console.print(f"Proposal #{proposal_id} marked as [{color}]{outcome}[/{color}].")


# ---------------------------------------------------------------------------
# propose learn
# ---------------------------------------------------------------------------


@propose.command()
def learn():
    """Extract winning patterns from past proposals into a style guide."""
    require_api_key()

    winners = get_winning_proposals()
    if not winners:
        console.print(
            "[yellow]No winning proposals found.[/yellow] "
            "Mark proposals with [bold]propose mark <id> won[/bold] first."
        )
        return

    from upwork_cli.ai.learner import extract_winning_patterns

    with console.status("[bold green]Analyzing winning proposals..."):
        try:
            style_guide = extract_winning_patterns(winners)
        except RuntimeError as exc:
            output.fail(exc)

    # Cache to disk
    style_guide_path = CONFIG_DIR / "style_guide.txt"
    style_guide_path.write_text(style_guide, encoding="utf-8")

    console.print()
    console.print(
        Panel(
            Markdown(style_guide),
            title="Winning Proposal Style Guide",
            border_style="green",
        )
    )
    console.print(f"\n[dim]Style guide saved to {style_guide_path}[/dim]")
    console.print("[dim]Future proposals will automatically use this guide.[/dim]")
