"""Job pipeline dashboard — track jobs through your application funnel."""

from datetime import datetime, timedelta, timezone

import click
from rich.table import Table

from upwork_cli import output
from upwork_cli.db import (
    PIPELINE_STAGES,
    get_pipeline_history,
    get_pipeline_jobs,
    get_pipeline_stats,
    init_db,
    set_pipeline_stage,
)
from upwork_cli.output import console


def _parse_history_timestamp(value: str) -> datetime | None:
    """Parse SQLite and ISO timestamps into a timezone-aware datetime."""
    if not value:
        return None

    candidates = [value]
    if value.endswith("Z"):
        candidates.append(value[:-1] + "+00:00")
    if " " in value and "T" not in value:
        candidates.append(value.replace(" ", "T", 1))

    for candidate in candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def _filter_recent_history(
    history: list[dict],
    days: int,
    now: datetime | None = None,
) -> list[dict]:
    """Return only transitions newer than the given day window."""
    current_time = now or datetime.now(timezone.utc)
    cutoff = current_time - timedelta(days=days)
    recent = []
    for item in history:
        moved_at = _parse_history_timestamp(item.get("moved_at", ""))
        if moved_at is not None and moved_at >= cutoff:
            recent.append(item)
    return recent


@click.group()
def pipeline():
    """Job pipeline dashboard — track jobs through your funnel."""
    init_db()


@pipeline.command()
@click.option(
    "--stage",
    type=click.Choice(PIPELINE_STAGES),
    default=None,
    help="Filter to a specific pipeline stage.",
)
def view(stage):
    """View jobs in the pipeline, optionally filtered by stage."""
    if stage:
        jobs = get_pipeline_jobs(stage=stage)
        title = f"Pipeline: {stage.title()}"
    else:
        jobs = get_pipeline_jobs()
        title = "Job Pipeline"

    if not jobs:
        suffix = f' at stage "{stage}"' if stage else ""
        output.empty(f"No jobs in the pipeline{suffix}.")
        return

    table = Table(title=title, show_lines=True)
    table.add_column("Job ID", style="dim", max_width=15)
    table.add_column("Title", style="bold cyan", max_width=40)
    table.add_column("Stage", justify="center")
    table.add_column("Budget", justify="right")
    table.add_column("Score", justify="center", width=6)
    table.add_column("Moved At", max_width=20)

    for j in jobs:
        st = j.get("stage", "?")
        stage_colors = {
            "found": "dim",
            "drafted": "cyan",
            "applied": "blue",
            "interviewing": "yellow",
            "won": "green",
            "lost": "red",
        }
        color = stage_colors.get(st, "white")
        score_str = str(j["score"]) if j.get("score") is not None else "-"

        table.add_row(
            j.get("job_id", ""),
            output.truncate(j.get("title", "") or "N/A", 40),
            f"[{color}]{st}[/{color}]",
            output.money(j.get("budget_amount"), j.get("budget_currency", "USD")),
            score_str,
            j.get("moved_at", ""),
        )

    console.print(table)
    console.print(f"\n[dim]{len(jobs)} job(s) shown.[/dim]")


@pipeline.command()
@click.argument("job_id")
@click.argument("stage", type=click.Choice(PIPELINE_STAGES))
@click.option(
    "--notes", type=str, default="", help="Optional notes for this stage change."
)
def move(job_id, stage, notes):
    """Move a job to a new pipeline stage."""
    set_pipeline_stage(job_id, stage, notes)
    console.print(f"[green]Job {job_id} moved to [bold]{stage}[/bold].[/green]")
    if notes:
        console.print(f"[dim]Notes: {notes}[/dim]")


@pipeline.command()
def stats():
    """Show pipeline statistics: win rate, stage counts, top categories."""
    data = get_pipeline_stats()

    if data["total"] == 0:
        output.empty("No jobs in the pipeline yet.")
        return

    # Stage counts
    table = Table(title="Pipeline Summary", show_lines=True)
    table.add_column("Stage", style="bold")
    table.add_column("Count", justify="right")

    for st in PIPELINE_STAGES:
        count = data["stage_counts"].get(st, 0)
        table.add_row(st.title(), str(count))
    table.add_row("[bold]Total[/bold]", f"[bold]{data['total']}[/bold]")

    console.print(table)

    # Win rate
    console.print(f"\n[bold]Win Rate:[/bold] {data['win_rate']}%")

    # Top categories
    cats = data.get("top_categories", [])
    if cats:
        console.print("\n[bold]Top Categories:[/bold]")
        for c in cats:
            console.print(f"  {c['category']}: {c['count']}")


@pipeline.command()
@click.option(
    "--days",
    type=int,
    default=7,
    show_default=True,
    help="Number of days to look back.",
)
def digest(days):
    """Show recent pipeline activity."""
    history = get_pipeline_history()

    if not history:
        output.empty("No pipeline activity yet.")
        return

    recent = _filter_recent_history(history, days)

    if not recent:
        output.empty(f"No pipeline activity in the last {days} day(s).")
        return

    table = Table(title=f"Pipeline Activity (last {days} days)", show_lines=True)
    table.add_column("Job", style="cyan", max_width=35)
    table.add_column("From", justify="center")
    table.add_column("To", justify="center")
    table.add_column("When", max_width=20)

    for h in recent:
        from_st = h.get("from_stage") or "-"
        to_st = h.get("to_stage", "?")
        table.add_row(
            output.truncate(h.get("title", "") or h.get("job_id", ""), 35),
            from_st,
            to_st,
            h.get("moved_at", ""),
        )

    console.print(table)
    console.print(f"\n[dim]{len(recent)} transition(s).[/dim]")
