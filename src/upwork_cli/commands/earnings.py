"""Commands for viewing Upwork earnings, contracts, and time tracking."""

import csv
from io import StringIO

import click
from rich.panel import Panel
from rich.table import Table

from upwork_cli import earnings as earnings_api
from upwork_cli import output
from upwork_cli.client import NotAuthenticated, UpworkClient, get_client
from upwork_cli.models import Contract, EarningRow
from upwork_cli.output import console


def _get_client() -> UpworkClient:
    """Return an authenticated client, reporting the failure to the terminal."""
    try:
        return get_client()
    except NotAuthenticated:
        output.fail("Not authenticated. Run 'upwork config setup' first.")


def _safe_float(value, default: float = 0.0) -> float:
    """Safely convert a value to float."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# Earnings command group
# ---------------------------------------------------------------------------


@click.group("earnings", invoke_without_command=True)
@click.pass_context
def earnings(ctx: click.Context) -> None:
    """View Upwork earnings, reports, and export data."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(summary)


@earnings.command("summary")
def summary() -> None:
    """Show earnings overview with totals for all-time, this month, and this week."""
    client = _get_client()
    try:
        rows, _ = earnings_api.fetch(client)
    except earnings_api.EarningsError as exc:
        output.fail(exc)

    if not rows:
        console.print(
            Panel(
                "[yellow]No earnings data available yet.[/yellow]\n\n"
                "Start working on contracts to see your earnings here.",
                title="Earnings Summary",
                border_style="yellow",
            )
        )
        return

    totals = earnings_api.summarise(rows)
    console.print(
        Panel(
            f"[bold green]Total Earned:[/bold green]   "
            f"{output.money(totals.total)}\n"
            f"[bold cyan]This Month:[/bold cyan]     "
            f"{output.money(totals.this_month)}\n"
            f"[bold blue]This Week:[/bold blue]      "
            f"{output.money(totals.this_week)}",
            title="Earnings Summary",
            border_style="green",
        )
    )


@earnings.command("report")
@click.option(
    "--from", "from_date", type=str, default=None, help="Start date (YYYY-MM-DD)."
)
@click.option("--to", "to_date", type=str, default=None, help="End date (YYYY-MM-DD).")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "csv"], case_sensitive=False),
    default="table",
    help="Output format.",
)
def report(from_date: str | None, to_date: str | None, output_format: str) -> None:
    """Show a detailed earnings report, optionally filtered by date range."""
    client = _get_client()
    try:
        rows, payload = earnings_api.fetch(client, from_date, to_date)
    except earnings_api.EarningsError as exc:
        output.fail(exc)

    if not rows:
        output.empty("No earnings found for the specified period.")
        return

    col_names = earnings_api.column_names(payload)
    cells = [row.as_cells() for row in rows]

    if output_format == "csv":
        buf = StringIO()
        writer = csv.writer(buf)
        writer.writerow(col_names)
        writer.writerows(cells)
        click.echo(buf.getvalue())
        return

    table = Table(title="Earnings Report", show_lines=True)
    for name in col_names:
        table.add_column(str(name))
    for row in cells:
        table.add_row(*[str(c) for c in row[: len(col_names)]])
    console.print(table)
    console.print(f"\n[dim]{len(rows)} record(s).[/dim]")


@earnings.command("export")
@click.option(
    "--output",
    "output_file",
    type=str,
    default="earnings_export.csv",
    help="Output file path.",
)
def export(output_file: str) -> None:
    """Export all earnings records to a CSV file."""
    client = _get_client()
    try:
        rows, _ = earnings_api.fetch(client)
    except earnings_api.EarningsError as exc:
        output.fail(exc)

    if not rows:
        output.empty("No earnings data to export.")
        return

    try:
        with open(output_file, "w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(list(EarningRow.COLUMNS))
            writer.writerows(row.as_cells() for row in rows)
    except OSError as exc:
        console.print(f"[red]Failed to write file: {exc}[/red]")
        raise SystemExit(1) from exc

    console.print(f"[green]Exported {len(rows)} records to {output_file}[/green]")


# ---------------------------------------------------------------------------
# Contracts command group
# ---------------------------------------------------------------------------


@click.group("contracts", invoke_without_command=True)
@click.pass_context
def contracts(ctx: click.Context) -> None:
    """Manage Upwork contracts and engagements."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(contracts_list)


@contracts.command("list")
def contracts_list() -> None:
    """List active contracts."""
    client = _get_client()

    try:
        data = client.get_engagements()
    except Exception as exc:
        console.print(f"[red]Failed to fetch contracts: {exc}[/red]")
        raise SystemExit(1)

    engagements = (
        data.get("engagements", {}).get("engagement", [])
        or data.get("engagement", [])
        or data.get("engagements", [])
        or []
    )
    # Normalise to a list when API returns a single dict.
    if isinstance(engagements, dict):
        engagements = [engagements]

    if not engagements:
        output.empty("No active contracts found.")
        return

    rich_table = Table(title="Contracts", show_lines=True)
    rich_table.add_column("Title", style="bold")
    rich_table.add_column("Client")
    rich_table.add_column("Status")
    rich_table.add_column("Rate", justify="right")
    rich_table.add_column("Hours", justify="right")
    rich_table.add_column("Total", justify="right")

    for eng in engagements:
        contract = Contract.from_api(eng)

        status_str = contract.status or "unknown"
        status_lower = status_str.lower()
        if status_lower == "active":
            status_display = f"[green]{status_str}[/green]"
        elif status_lower in ("paused", "suspended"):
            status_display = f"[yellow]{status_str}[/yellow]"
        elif status_lower in ("ended", "closed"):
            status_display = f"[red]{status_str}[/red]"
        else:
            status_display = status_str

        rate = (
            output.money(contract.hourly_rate)
            if contract.hourly_rate is not None
            else "-"
        )
        hours = (
            f"{contract.total_hours:.1f}" if contract.total_hours is not None else "-"
        )
        total = (
            output.money(contract.total_charge)
            if contract.total_charge is not None
            else "-"
        )

        rich_table.add_row(
            contract.title,
            contract.client_name,
            status_display,
            rate,
            hours,
            total,
        )

    console.print(rich_table)


@contracts.command("detail")
@click.argument("reference")
def contracts_detail(reference: str) -> None:
    """Show detailed information for a specific contract."""
    client = _get_client()

    try:
        data = client.get_engagement(reference)
    except Exception as exc:
        console.print(f"[red]Failed to fetch contract detail: {exc}[/red]")
        raise SystemExit(1)

    eng = data.get("engagement", data)
    contract = Contract.from_api(eng)

    status_lower = (contract.status or "").lower()
    if status_lower == "active":
        status_display = f"[green]{contract.status}[/green]"
    elif status_lower in ("paused", "suspended"):
        status_display = f"[yellow]{contract.status}[/yellow]"
    elif status_lower in ("ended", "closed"):
        status_display = f"[red]{contract.status}[/red]"
    else:
        status_display = contract.status

    lines = [
        f"[bold]Title:[/bold]       {contract.title}",
        f"[bold]Reference:[/bold]   {contract.id}",
        f"[bold]Client:[/bold]      {contract.client_name}",
        f"[bold]Status:[/bold]      {status_display}",
        f"[bold]Created:[/bold]     {contract.created_at}",
    ]
    if contract.hourly_rate is not None:
        lines.append(f"[bold]Hourly Rate:[/bold] {output.money(contract.hourly_rate)}")
    if contract.total_hours is not None:
        lines.append(f"[bold]Total Hours:[/bold] {contract.total_hours:.1f}")
    if contract.total_charge is not None:
        lines.append(
            f"[bold]Total Earned:[/bold] {output.money(contract.total_charge)}"
        )

    # Milestones (if available in the response).
    milestones = eng.get("milestones", eng.get("fixed_price_milestones", []))
    if isinstance(milestones, dict):
        milestones = milestones.get("milestone", [])
    if isinstance(milestones, dict):
        milestones = [milestones]

    if milestones:
        lines.append("")
        lines.append("[bold underline]Milestones[/bold underline]")
        for ms in milestones:
            ms_desc = ms.get("description", ms.get("title", "Untitled"))
            ms_amount = _safe_float(ms.get("amount", 0))
            ms_status = ms.get("status", ms.get("state", ""))
            lines.append(f"  - {ms_desc}: {output.money(ms_amount)} [{ms_status}]")

    console.print(
        Panel(
            "\n".join(lines),
            title=f"Contract: {contract.title}",
            border_style="blue",
        )
    )


@contracts.command("submit")
@click.argument("reference")
@click.option("--message", type=str, default="", help="Submission message.")
def contracts_submit(reference: str, message: str) -> None:
    """Submit work for a milestone on a contract."""
    client = _get_client()

    # Fetch the contract first so the user can confirm.
    try:
        data = client.get_engagement(reference)
    except Exception as exc:
        console.print(f"[red]Failed to fetch contract: {exc}[/red]")
        raise SystemExit(1)

    eng = data.get("engagement", data)
    contract = Contract.from_api(eng)

    console.print(
        Panel(
            f"[bold]Contract:[/bold] {contract.title}\n"
            f"[bold]Client:[/bold]   {contract.client_name}\n"
            f"[bold]Reference:[/bold] {reference}",
            title="Submit Work",
            border_style="yellow",
        )
    )

    if not click.confirm("Are you sure you want to submit work for this contract?"):
        output.warn("Submission cancelled.")
        return

    params: dict = {"engagement__reference": reference}
    if message:
        params["comments"] = message

    try:
        client.submit_work(params)
        console.print("[green]Work submitted successfully![/green]")
    except Exception as exc:
        console.print(f"[red]Failed to submit work: {exc}[/red]")
        raise SystemExit(1)
