"""Commands for viewing Upwork earnings, contracts, and time tracking."""

import csv
import sys
from datetime import datetime, timedelta
from io import StringIO

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from upwork_cli.client import UpworkClient
from upwork_cli.config import load_settings
from upwork_cli.models import Contract

console = Console()


def _get_client() -> UpworkClient:
    """Create and return an authenticated UpworkClient."""
    settings = load_settings()
    client = UpworkClient(settings=settings)
    if not client.is_authenticated:
        console.print("[red]Not authenticated. Run 'upwork config setup' first.[/red]")
        raise SystemExit(1)
    return client


def _get_freelancer_ref(client: UpworkClient) -> str:
    """Retrieve the freelancer reference from user info."""
    try:
        user_info = client.get_user_info()
        ref = user_info.get("info", {}).get("ref", "")
        if not ref:
            ref = user_info.get("ref", user_info.get("id", ""))
        return ref
    except Exception as exc:
        console.print(f"[red]Failed to get user info: {exc}[/red]")
        raise SystemExit(1)


def _safe_float(value, default: float = 0.0) -> float:
    """Safely convert a value to float."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _format_currency(amount: float) -> str:
    """Format a number as USD currency."""
    return f"${amount:,.2f}"


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
    freelancer_ref = _get_freelancer_ref(client)

    try:
        data = client.get_earnings(freelancer_ref)
    except Exception as exc:
        console.print(f"[red]Failed to fetch earnings: {exc}[/red]")
        raise SystemExit(1)

    # The API may return data under various keys; try common structures.
    table_data = (
        data.get("table", {}).get("rows", [])
        or data.get("rows", [])
        or data.get("earnings", [])
        or []
    )

    if not table_data:
        console.print(
            Panel(
                "[yellow]No earnings data available yet.[/yellow]\n\n"
                "Start working on contracts to see your earnings here.",
                title="Earnings Summary",
                border_style="yellow",
            )
        )
        return

    total_earned: float = 0.0
    this_month: float = 0.0
    this_week: float = 0.0

    now = datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=now.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

    for row in table_data:
        # Handle both dict-style rows and list-style cell arrays.
        if isinstance(row, dict):
            amount = _safe_float(
                row.get("amount")
                or row.get("charge_amount")
                or row.get("total_charge")
            )
            date_str = row.get("date", row.get("worked_on", row.get("date_created", "")))
        elif isinstance(row, list):
            # Assume last cell is amount, first is date.
            amount = _safe_float(row[-1]) if row else 0.0
            date_str = str(row[0]) if row else ""
        else:
            continue

        total_earned += amount

        # Try to parse the date for period bucketing.
        row_date = None
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y", "%Y%m%d"):
            try:
                row_date = datetime.strptime(date_str[:10], fmt)
                break
            except (ValueError, TypeError):
                continue

        if row_date:
            if row_date >= month_start:
                this_month += amount
            if row_date >= week_start:
                this_week += amount

    summary_text = (
        f"[bold green]Total Earned:[/bold green]   {_format_currency(total_earned)}\n"
        f"[bold cyan]This Month:[/bold cyan]     {_format_currency(this_month)}\n"
        f"[bold blue]This Week:[/bold blue]      {_format_currency(this_week)}"
    )

    console.print(
        Panel(
            summary_text,
            title="Earnings Summary",
            border_style="green",
        )
    )


@earnings.command("report")
@click.option("--from", "from_date", type=str, default=None, help="Start date (YYYY-MM-DD).")
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
    freelancer_ref = _get_freelancer_ref(client)

    params: dict = {}
    if from_date:
        params["tq"] = params.get("tq", "") + f" AND date >= '{from_date}'"
    if to_date:
        tq = params.get("tq", "")
        clause = f"date <= '{to_date}'"
        params["tq"] = f"{tq} AND {clause}" if tq else clause

    # Clean up leading " AND ".
    if "tq" in params and params["tq"].startswith(" AND "):
        params["tq"] = params["tq"][5:]

    try:
        data = client.get_earnings(freelancer_ref, params if params else None)
    except Exception as exc:
        console.print(f"[red]Failed to fetch earnings report: {exc}[/red]")
        raise SystemExit(1)

    table_data = (
        data.get("table", {}).get("rows", [])
        or data.get("rows", [])
        or data.get("earnings", [])
        or []
    )

    if not table_data:
        console.print("[yellow]No earnings found for the specified period.[/yellow]")
        return

    # Extract column headers from the response, fall back to defaults.
    columns = (
        data.get("table", {}).get("cols", [])
        or data.get("cols", [])
        or []
    )
    col_names = [c.get("label", c.get("name", f"Col {i}")) for i, c in enumerate(columns)]
    if not col_names:
        col_names = ["Date", "Client", "Contract", "Amount", "Type"]

    # Normalise each row into a list of string values.
    rows: list[list[str]] = []
    for row in table_data:
        if isinstance(row, dict):
            cells = row.get("c", [])
            if cells and isinstance(cells, list):
                rows.append([str((c or {}).get("v", "")) if isinstance(c, dict) else str(c) for c in cells])
            else:
                # Flat dict: pull values matching column order where possible.
                rows.append([
                    str(row.get("date", row.get("worked_on", ""))),
                    str(row.get("client", row.get("buyer_company_name", ""))),
                    str(row.get("contract", row.get("engagement_title", ""))),
                    str(row.get("amount", row.get("charge_amount", row.get("total_charge", "")))),
                    str(row.get("type", row.get("subtype", ""))),
                ])
        elif isinstance(row, list):
            rows.append([str(v) for v in row])

    if output_format == "csv":
        buf = StringIO()
        writer = csv.writer(buf)
        writer.writerow(col_names)
        writer.writerows(rows)
        click.echo(buf.getvalue())
        return

    # Rich table output.
    rich_table = Table(title="Earnings Report", show_lines=True)
    for name in col_names:
        rich_table.add_column(name, style="cyan")

    for row in rows:
        # Pad row to match column count.
        padded = row + [""] * (len(col_names) - len(row))
        rich_table.add_row(*padded[: len(col_names)])

    console.print(rich_table)


@earnings.command("export")
@click.option("--output", "output_file", type=str, default="earnings_export.csv", help="Output file path.")
def export(output_file: str) -> None:
    """Export earnings data to a CSV file."""
    client = _get_client()
    freelancer_ref = _get_freelancer_ref(client)

    try:
        data = client.get_earnings(freelancer_ref)
    except Exception as exc:
        console.print(f"[red]Failed to fetch earnings: {exc}[/red]")
        raise SystemExit(1)

    table_data = (
        data.get("table", {}).get("rows", [])
        or data.get("rows", [])
        or data.get("earnings", [])
        or []
    )

    if not table_data:
        console.print("[yellow]No earnings data to export.[/yellow]")
        return

    fieldnames = ["Date", "Client", "Contract", "Amount", "Type"]

    rows: list[dict[str, str]] = []
    for row in table_data:
        if isinstance(row, dict):
            cells = row.get("c", [])
            if cells and isinstance(cells, list):
                values = [(c or {}).get("v", "") if isinstance(c, dict) else c for c in cells]
                entry = {}
                for idx, name in enumerate(fieldnames):
                    entry[name] = str(values[idx]) if idx < len(values) else ""
                rows.append(entry)
            else:
                rows.append({
                    "Date": str(row.get("date", row.get("worked_on", ""))),
                    "Client": str(row.get("client", row.get("buyer_company_name", ""))),
                    "Contract": str(row.get("contract", row.get("engagement_title", ""))),
                    "Amount": str(row.get("amount", row.get("charge_amount", row.get("total_charge", "")))),
                    "Type": str(row.get("type", row.get("subtype", ""))),
                })
        elif isinstance(row, list):
            entry = {}
            for idx, name in enumerate(fieldnames):
                entry[name] = str(row[idx]) if idx < len(row) else ""
            rows.append(entry)

    try:
        with open(output_file, "w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        console.print(f"[green]Exported {len(rows)} records to {output_file}[/green]")
    except OSError as exc:
        console.print(f"[red]Failed to write file: {exc}[/red]")
        raise SystemExit(1)


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
        console.print("[yellow]No active contracts found.[/yellow]")
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

        rate = _format_currency(contract.hourly_rate) if contract.hourly_rate is not None else "-"
        hours = f"{contract.total_hours:.1f}" if contract.total_hours is not None else "-"
        total = _format_currency(contract.total_charge) if contract.total_charge is not None else "-"

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
        lines.append(f"[bold]Hourly Rate:[/bold] {_format_currency(contract.hourly_rate)}")
    if contract.total_hours is not None:
        lines.append(f"[bold]Total Hours:[/bold] {contract.total_hours:.1f}")
    if contract.total_charge is not None:
        lines.append(f"[bold]Total Earned:[/bold] {_format_currency(contract.total_charge)}")

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
            lines.append(
                f"  - {ms_desc}: {_format_currency(ms_amount)} [{ms_status}]"
            )

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
        console.print("[yellow]Submission cancelled.[/yellow]")
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
