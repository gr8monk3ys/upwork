"""Job pipeline dashboard — track jobs through your application funnel."""

import click
from rich.table import Table

from upwork_cli import output
from upwork_cli import pipeline as pipeline_api
from upwork_cli.db import init_db
from upwork_cli.output import console

#: Presentation only: what each Stage looks like in a terminal.
STAGE_COLOURS = {
    "found": "dim",
    "drafted": "cyan",
    "applied": "blue",
    "interviewing": "yellow",
    "won": "green",
    "lost": "red",
}


def _stage_display(stage: str) -> str:
    colour = STAGE_COLOURS.get(stage, "white")
    return f"[{colour}]{stage}[/{colour}]"


@click.group()
def pipeline():
    """Job pipeline dashboard — track jobs through your funnel."""
    init_db()


@pipeline.command()
@click.option(
    "--stage",
    type=click.Choice(pipeline_api.STAGES),
    default=None,
    help="Filter to a specific pipeline stage.",
)
def view(stage):
    """View jobs in the pipeline, optionally filtered by stage."""
    entries = pipeline_api.entries(stage)
    title = f"Pipeline: {stage.title()}" if stage else "Job Pipeline"

    if not entries:
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

    for entry in entries:
        table.add_row(
            entry.job_id,
            output.truncate(entry.title or "N/A", 40),
            _stage_display(entry.stage),
            output.money(entry.budget_amount, entry.budget_currency),
            str(entry.score) if entry.score is not None else "-",
            entry.moved_at,
        )

    console.print(table)
    console.print(f"\n[dim]{len(entries)} job(s) shown.[/dim]")


@pipeline.command()
@click.argument("job_id")
@click.argument("stage", type=click.Choice(pipeline_api.STAGES))
@click.option(
    "--notes", type=str, default="", help="Optional notes for this stage change."
)
def move(job_id, stage, notes):
    """Move a job to a new pipeline stage."""
    try:
        pipeline_api.move(job_id, stage, notes)
    except pipeline_api.PipelineError as exc:
        output.fail(exc)
    console.print(f"[green]Job {job_id} moved to [bold]{stage}[/bold].[/green]")
    if notes:
        console.print(f"[dim]Notes: {notes}[/dim]")


@pipeline.command()
def stats():
    """Show pipeline statistics: win rate, stage counts, top categories."""
    data = pipeline_api.stats()

    if data.total == 0:
        output.empty("No jobs in the pipeline yet.")
        return

    # Stage counts
    table = Table(title="Pipeline Summary", show_lines=True)
    table.add_column("Stage", style="bold")
    table.add_column("Count", justify="right")

    for stage in pipeline_api.STAGES:
        table.add_row(stage.title(), str(data.count(stage)))
    table.add_row("[bold]Total[/bold]", f"[bold]{data.total}[/bold]")

    console.print(table)
    console.print(f"\n[bold]Win Rate:[/bold] {data.win_rate}%")

    if data.top_categories:
        console.print("\n[bold]Top Categories:[/bold]")
        for entry in data.top_categories:
            console.print(f"  {entry.category}: {entry.count}")


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
    if not pipeline_api.history():
        output.empty("No pipeline activity yet.")
        return

    recent = pipeline_api.recent(days)

    if not recent:
        output.empty(f"No pipeline activity in the last {days} day(s).")
        return

    table = Table(title=f"Pipeline Activity (last {days} days)", show_lines=True)
    table.add_column("Job", style="cyan", max_width=35)
    table.add_column("From", justify="center")
    table.add_column("To", justify="center")
    table.add_column("When", max_width=20)

    for transition in recent:
        table.add_row(
            output.truncate(transition.label, 35),
            transition.from_stage or "-",
            transition.to_stage,
            transition.moved_at,
        )

    console.print(table)
    console.print(f"\n[dim]{len(recent)} transition(s).[/dim]")
