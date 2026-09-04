"""`upwork doctor` — prove every external path actually works.

The suite runs against fakes. This runs against Upwork and Anthropic.
"""

import click
from rich.table import Table

from upwork_cli import diagnostics, output
from upwork_cli.output import console

STATUS_STYLE = {
    diagnostics.OK: ("[green]ok[/green]", "green"),
    diagnostics.FAILED: ("[red]FAILED[/red]", "red"),
    diagnostics.SKIPPED: ("[dim]skipped[/dim]", "dim"),
}


@click.command()
@click.option(
    "--no-ai",
    is_flag=True,
    help="Skip the Anthropic check, which spends a few tokens.",
)
def doctor(no_ai: bool) -> None:
    """Check every external path this tool depends on.

    Read-only: nothing is submitted, sent or changed.
    """
    console.print("[bold]Checking every external path...[/bold]\n")
    checks = diagnostics.run_all(with_ai=not no_ai)

    table = Table(show_lines=False)
    table.add_column("Check", style="bold")
    table.add_column("Result", justify="center", width=10)
    table.add_column("Detail", style="dim", max_width=60)

    for check in checks:
        label, _ = STATUS_STYLE.get(check.status, (check.status, "white"))
        table.add_row(check.name, label, check.detail)

    console.print(table)

    failures = [c for c in checks if c.failed]
    if failures:
        output.fail(
            f"{len(failures)} of {len(checks)} checks failed: "
            + ", ".join(c.name for c in failures)
        )
    console.print(f"\n[green]All {len(checks)} checks passed.[/green]")
