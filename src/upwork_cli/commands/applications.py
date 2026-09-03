"""Commands for managing proposal applications and incoming offers."""

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from upwork_cli import applications as applications_api
from upwork_cli.client import NotAuthenticated, UpworkClient, get_client
from upwork_cli.models import Offer, OfferTerms

console = Console()

AUTH_ERROR_MESSAGE = (
    "Not authenticated. Run [bold]upwork config setup[/bold] to configure "
    "your API credentials."
)

APPLICATION_STATUSES = {
    "accepted": "Accepted",
    "activated": "Activated",
    "archived": "Archived",
    "declined": "Declined",
    "hired": "Hired",
    "offered": "Offered",
    "pending": "Pending",
    "withdrawn": "Withdrawn",
}

APPLICATION_SORT_FIELDS = {
    "created": "CreatedDateTime",
    "modified": "ModifiedDateTime",
    "status": "StatusChangedDateTime",
}

OFFER_STATES = {
    "pending": "Pending",
    "active": "Active",
    "paused": "Paused",
    "ended": "Ended",
}

WITHDRAW_REASONS = {
    "another-freelancer-hired": "AnotherFreelancerHired",
    "client-no-longer-hiring": "ClientNoLongerHiring",
    "job-post-modified": "JobPostModified",
    "no-response": "NoResponse",
    "other": "Other",
    "sent-by-accident": "SentByAccident",
    "terms-differ-significantly": "TermsDifferSignificantly",
    "too-old": "TooOld",
    "violates-upwork-tos": "ViolatesUpworkTOS",
}


def _get_client() -> UpworkClient:
    """Return an authenticated client, reporting the failure to the terminal."""
    try:
        return get_client()
    except NotAuthenticated:
        console.print(f"\n[red]{AUTH_ERROR_MESSAGE}[/red]\n")
        raise SystemExit(1) from None


def _fail(exc: Exception) -> None:
    console.print(f"[red]{exc}[/red]")
    raise SystemExit(1)


def _format_amount(amount: float | None, currency: str = "USD") -> str:
    """Format a money amount for display."""
    if amount is None:
        return "N/A"
    return f"${amount:,.2f} {currency}"


def _format_terms(terms: OfferTerms) -> str:
    """Render offer terms into a short summary."""
    if terms.amount is None:
        return "N/A"
    money = f"${terms.amount:,.2f} {terms.currency}"
    if not terms.is_fixed and terms.weekly_hours_limit is not None:
        return f"{money} / {terms.weekly_hours_limit} hrs"
    return money


def _render_related_offers(offers_found: list[Offer]) -> None:
    """Render offers linked to an application."""
    if not offers_found:
        return

    table = Table(title="Related Offers", show_lines=True)
    table.add_column("Offer ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="bold")
    table.add_column("State", style="green", no_wrap=True)
    table.add_column("Client", style="magenta")
    table.add_column("Terms", justify="right")

    for offer in offers_found:
        table.add_row(
            offer.id,
            offer.title,
            offer.state or "Unknown",
            offer.client_name or "N/A",
            _format_terms(offer.terms),
        )

    console.print(table)


@click.group("applications", invoke_without_command=True)
@click.pass_context
def applications(ctx: click.Context) -> None:
    """View proposal applications tracked through Upwork GraphQL."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(list_applications)


@applications.command("list")
@click.option(
    "--status",
    type=click.Choice(["all", *APPLICATION_STATUSES.keys()], case_sensitive=False),
    default="accepted",
    show_default=True,
    help="Application status filter.",
)
@click.option(
    "--sort",
    "sort_name",
    type=click.Choice(list(APPLICATION_SORT_FIELDS.keys()), case_sensitive=False),
    default="modified",
    show_default=True,
    help="Sort field.",
)
@click.option(
    "--limit",
    default=20,
    show_default=True,
    type=int,
    help="Maximum applications to display.",
)
def list_applications(status: str, sort_name: str, limit: int) -> None:
    """List your recent proposal applications."""
    client = _get_client()
    normalized_status = status.lower()
    statuses = (
        list(APPLICATION_STATUSES.values())
        if normalized_status == "all"
        else [APPLICATION_STATUSES[normalized_status]]
    )
    sort_field = APPLICATION_SORT_FIELDS[sort_name.lower()]

    try:
        found = applications_api.list_applications(
            client, statuses=statuses, limit=limit, sort_field=sort_field
        )
    except applications_api.ApplicationsError as exc:
        _fail(exc)

    if not found:
        console.print("[yellow]No applications found for the selected filter.[/yellow]")
        return

    table = Table(title="Applications", show_lines=True)
    table.add_column("Application ID", style="cyan", no_wrap=True)
    table.add_column("Job", style="bold")
    table.add_column("Status", style="green", no_wrap=True)
    table.add_column("Submitted", style="magenta", no_wrap=True)
    table.add_column("Updated", style="magenta", no_wrap=True)

    for application in found:
        table.add_row(
            application.id,
            application.job_title or "Untitled",
            application.status or "Unknown",
            application.created_at,
            application.modified_at,
        )

    console.print(table)


@applications.command("show")
@click.argument("application_id")
def show_application(application_id: str) -> None:
    """Show detailed information for a specific application."""
    client = _get_client()

    try:
        application = applications_api.get_application(client, application_id)
        related_offers = applications_api.offers_for_application(
            client, application_id, limit=10
        )
    except applications_api.ApplicationsError as exc:
        _fail(exc)

    if application is None:
        console.print(f"[yellow]Application {application_id} was not found.[/yellow]")
        raise SystemExit(1)

    job = application.job
    summary = [
        f"[bold]Application ID:[/bold] {application.id}",
        f"[bold]Status:[/bold] {application.status or 'Unknown'}",
        f"[bold]Job:[/bold] {application.job_title or 'Untitled'}",
        f"[bold]Budget:[/bold] {_format_amount(job.budget_amount if job else None, job.budget_currency if job else 'USD')}",
        f"[bold]Engagement:[/bold] {(job.engagement if job else '') or 'N/A'}",
        f"[bold]Duration:[/bold] {(job.duration_label if job else '') or 'N/A'}",
        f"[bold]Submitted:[/bold] {application.created_at}",
        f"[bold]Updated:[/bold] {application.modified_at}",
        f"[bold]Client Country:[/bold] {(job.client_country if job else '') or 'N/A'}",
        f"[bold]Client Verified:[/bold] {'VERIFIED' if job and job.client_verified else 'UNKNOWN'}",
        f"[bold]Client Spend:[/bold] {_format_amount(job.client_total_spent if job else None)}",
        f"[bold]Client Hires:[/bold] {(job.client_total_hires if job else None) if job and job.client_total_hires is not None else 'N/A'}",
    ]

    console.print(
        Panel("\n".join(summary), title="Application Details", border_style="cyan")
    )

    description = (job.description if job else "").strip()
    if description:
        console.print(
            Panel(description, title="Job Description", border_style="magenta")
        )

    console.print(
        Panel(
            application.cover_letter or "(empty)",
            title="Cover Letter",
            border_style="green",
        )
    )
    _render_related_offers(related_offers)


@click.group("offers", invoke_without_command=True)
@click.pass_context
def offers(ctx: click.Context) -> None:
    """View and manage incoming offers."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(list_offers)


@offers.command("list")
@click.option(
    "--state",
    type=click.Choice(list(OFFER_STATES.keys()), case_sensitive=False),
    default=None,
    help="Filter by contract offer state.",
)
@click.option(
    "--limit",
    default=20,
    show_default=True,
    type=int,
    help="Maximum offers to display.",
)
def list_offers(state: str | None, limit: int) -> None:
    """List current offers visible to the authenticated freelancer."""
    client = _get_client()
    gql_state = OFFER_STATES[state.lower()] if state else None

    try:
        found = applications_api.list_offers(client, state=gql_state, limit=limit)
    except applications_api.ApplicationsError as exc:
        _fail(exc)

    if not found:
        console.print("[yellow]No offers found for the selected filter.[/yellow]")
        return

    table = Table(title="Offers", show_lines=True)
    table.add_column("Offer ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="bold")
    table.add_column("State", style="green", no_wrap=True)
    table.add_column("Type", style="yellow", no_wrap=True)
    table.add_column("Client", style="magenta")
    table.add_column("Updated", style="magenta", no_wrap=True)

    for offer in found:
        table.add_row(
            offer.id,
            offer.title,
            offer.state or "Unknown",
            offer.kind or "Unknown",
            offer.client_name or "N/A",
            offer.updated_at,
        )

    console.print(table)


@offers.command("show")
@click.argument("offer_id")
def show_offer(offer_id: str) -> None:
    """Show detailed information for a specific offer."""
    client = _get_client()

    try:
        offer = applications_api.get_offer(client, offer_id)
    except applications_api.ApplicationsError as exc:
        _fail(exc)

    if offer is None:
        console.print(f"[yellow]Offer {offer_id} was not found.[/yellow]")
        raise SystemExit(1)

    lines = [
        f"[bold]Offer ID:[/bold] {offer.id}",
        f"[bold]State:[/bold] {offer.state or 'Unknown'}",
        f"[bold]Type:[/bold] {offer.kind or 'Unknown'}",
        f"[bold]Client:[/bold] {offer.client_name or 'N/A'}",
        f"[bold]Job:[/bold] {offer.job_title or 'N/A'}",
        f"[bold]Application ID:[/bold] {offer.application_id or 'N/A'}",
        f"[bold]Application Status:[/bold] {offer.application_status or 'N/A'}",
        f"[bold]Terms:[/bold] {_format_terms(offer.terms)}",
        f"[bold]Start Date:[/bold] {offer.terms.start_date or 'N/A'}",
        f"[bold]End Date:[/bold] {offer.terms.end_date or 'N/A'}",
        f"[bold]Close Job On Accept:[/bold] {offer.close_job_on_accept}",
    ]

    console.print(
        Panel(
            "\n".join(lines),
            title=offer.title or "Offer Details",
            border_style="cyan",
        )
    )

    if offer.description.strip():
        console.print(
            Panel(
                offer.description.strip(),
                title="Offer Description",
                border_style="magenta",
            )
        )

    if offer.message_to_contractor.strip():
        console.print(
            Panel(
                offer.message_to_contractor.strip(),
                title="Client Message",
                border_style="green",
            )
        )


@offers.command("withdraw")
@click.argument("offer_id")
@click.option(
    "--reason",
    type=click.Choice(list(WITHDRAW_REASONS.keys()), case_sensitive=False),
    default="other",
    show_default=True,
    help="Withdrawal reason to send to Upwork.",
)
@click.option("--message", default="", help="Optional message to the client.")
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt.")
def withdraw_offer(offer_id: str, reason: str, message: str, yes: bool) -> None:
    """Withdraw an existing offer."""
    client = _get_client()
    gql_reason = WITHDRAW_REASONS[reason.lower()]

    console.print(f"[bold]Offer:[/bold] {offer_id}")
    console.print(f"[bold]Reason:[/bold] {gql_reason}")
    if message:
        console.print(f"[bold]Message:[/bold] {message}")
    console.print()

    if not yes and not click.confirm("Withdraw this offer?"):
        console.print("[yellow]Offer not withdrawn.[/yellow]")
        return

    try:
        applications_api.withdraw_offer(client, offer_id, gql_reason, message)
    except applications_api.ApplicationsError as exc:
        _fail(exc)

    console.print("[green]Offer withdrawn successfully.[/green]")
