"""Commands for managing proposal applications and incoming offers."""

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from upwork_cli.client import NotAuthenticated, UpworkClient, get_client

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


def _format_money(money: dict | None) -> str:
    """Format a GraphQL Money object."""
    money = money or {}
    amount = money.get("amount")
    currency = money.get("currencyCode", "USD")
    if amount in (None, ""):
        return "N/A"
    try:
        return f"${float(amount):,.2f} {currency}"
    except (TypeError, ValueError):
        return f"{amount} {currency}".strip()


def _application_timestamp(application: dict, preferred: str = "modified") -> str:
    """Return the preferred audit timestamp for sorting and display."""
    audit = application.get("auditDetails") or {}
    if preferred == "created":
        return audit.get("createdDateTime", "")
    if preferred == "status":
        return audit.get("statusChangedDateTime", audit.get("modifiedDateTime", ""))
    return audit.get("modifiedDateTime") or audit.get("createdDateTime", "")


def _offer_identifier(offer_result: dict) -> str:
    """Return the actual offer id when the connection wraps it."""
    offer = offer_result.get("offer") or {}
    return str(offer.get("id") or offer_result.get("id", ""))


def _offer_client_name(offer_data: dict) -> str:
    """Extract a readable client/company name from offer payloads."""
    company = offer_data.get("company") or {}
    client = offer_data.get("client") or {}
    if company.get("name"):
        return str(company["name"])
    if client.get("name"):
        return str(client["name"])
    return "N/A"


def _format_offer_terms(terms: dict | None) -> str:
    """Render fixed-price or hourly offer terms into a short summary."""
    terms = terms or {}
    fixed_price = terms.get("fixedPriceTerm") or {}
    hourly = terms.get("hourlyTerms") or {}

    if fixed_price.get("budget"):
        return _format_money(fixed_price.get("budget"))

    rate = hourly.get("rate") or {}
    if rate.get("amount") not in (None, ""):
        weekly_limit = hourly.get("weeklyHoursLimit")
        detail = _format_money(rate)
        if weekly_limit not in (None, ""):
            detail += f" / {weekly_limit} hrs"
        return detail

    return "N/A"


def _collect_applications(
    client: UpworkClient,
    statuses: list[str],
    limit: int,
    sort_field: str,
) -> list[dict]:
    """Fetch applications across one or more statuses and return unique nodes."""
    applications: dict[str, dict] = {}

    for status in statuses:
        result = client.get_applications(
            {
                "status": status,
                "limit": limit,
                "sort_field": sort_field,
                "sort_order": "DESC",
            }
        )
        for edge in result.get("edges", []):
            node = edge.get("node") or {}
            app_id = str(node.get("id", ""))
            if app_id and app_id not in applications:
                applications[app_id] = node

    preferred = "created" if sort_field == "CreatedDateTime" else "modified"
    sorted_items = sorted(
        applications.values(),
        key=lambda item: _application_timestamp(item, preferred=preferred),
        reverse=True,
    )
    return sorted_items[:limit]


def _render_related_offers(offers: list[dict]) -> None:
    """Render offers linked to an application."""
    if not offers:
        return

    table = Table(title="Related Offers", show_lines=True)
    table.add_column("Offer ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="bold")
    table.add_column("State", style="green", no_wrap=True)
    table.add_column("Client", style="magenta")
    table.add_column("Terms", justify="right")

    for offer in offers:
        table.add_row(
            str(offer.get("id", "")),
            str(offer.get("title", "")),
            str(offer.get("state", "Unknown")),
            _offer_client_name(offer),
            _format_offer_terms(offer.get("offerTerms")),
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
        applications_data = _collect_applications(
            client, statuses=statuses, limit=limit, sort_field=sort_field
        )
    except Exception as exc:
        console.print(f"[red]Failed to fetch applications: {exc}[/red]")
        raise SystemExit(1)

    if not applications_data:
        console.print("[yellow]No applications found for the selected filter.[/yellow]")
        return

    table = Table(title="Applications", show_lines=True)
    table.add_column("Application ID", style="cyan", no_wrap=True)
    table.add_column("Job", style="bold")
    table.add_column("Status", style="green", no_wrap=True)
    table.add_column("Submitted", style="magenta", no_wrap=True)
    table.add_column("Updated", style="magenta", no_wrap=True)

    for application in applications_data:
        job = application.get("marketplaceJobPosting") or {}
        status_data = application.get("status") or {}
        audit = application.get("auditDetails") or {}
        table.add_row(
            str(application.get("id", "")),
            str(job.get("title", "Untitled")),
            str(status_data.get("status", "Unknown")),
            str(audit.get("createdDateTime", "")),
            str(audit.get("modifiedDateTime", "")),
        )

    console.print(table)


@applications.command("show")
@click.argument("application_id")
def show_application(application_id: str) -> None:
    """Show detailed information for a specific application."""
    client = _get_client()

    try:
        application = client.get_application(application_id)
        related_offers = client.get_offers_for_application(application_id, limit=10)
    except Exception as exc:
        console.print(f"[red]Failed to fetch application {application_id}: {exc}[/red]")
        raise SystemExit(1)

    if not application:
        console.print(f"[yellow]Application {application_id} was not found.[/yellow]")
        raise SystemExit(1)

    job = application.get("marketplaceJobPosting") or {}
    client_info = job.get("client") or {}
    status_data = application.get("status") or {}
    audit = application.get("auditDetails") or {}
    cover_letter = (
        application.get("proposalCoverLetter")
        or application.get("coverLetter")
        or "(empty)"
    )

    summary = [
        f"[bold]Application ID:[/bold] {application.get('id', '')}",
        f"[bold]Status:[/bold] {status_data.get('status', 'Unknown')}",
        f"[bold]Job:[/bold] {job.get('title', 'Untitled')}",
        f"[bold]Budget:[/bold] {_format_money(job.get('amount'))}",
        f"[bold]Engagement:[/bold] {job.get('engagement', 'N/A')}",
        f"[bold]Duration:[/bold] {job.get('durationLabel', 'N/A')}",
        f"[bold]Submitted:[/bold] {audit.get('createdDateTime', '')}",
        f"[bold]Updated:[/bold] {audit.get('modifiedDateTime', '')}",
        f"[bold]Client Country:[/bold] {(client_info.get('location') or {}).get('country', 'N/A')}",
        f"[bold]Client Verified:[/bold] {client_info.get('verificationStatus', 'UNKNOWN')}",
        f"[bold]Client Spend:[/bold] {_format_money(client_info.get('totalSpent'))}",
        f"[bold]Client Hires:[/bold] {client_info.get('totalHires', 'N/A')}",
    ]

    console.print(
        Panel(
            "\n".join(summary),
            title="Application Details",
            border_style="cyan",
        )
    )

    description = str(job.get("description", "")).strip()
    if description:
        console.print(
            Panel(
                description,
                title="Job Description",
                border_style="magenta",
            )
        )

    console.print(
        Panel(
            cover_letter,
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
        result = client.get_offers({"limit": limit, "state": gql_state})
    except Exception as exc:
        console.print(f"[red]Failed to fetch offers: {exc}[/red]")
        raise SystemExit(1)

    offers_data = []
    for edge in result.get("edges", []):
        node = edge.get("node") or {}
        offer_id = _offer_identifier(node)
        if offer_id:
            offers_data.append(node)

    if not offers_data:
        console.print("[yellow]No offers found for the selected filter.[/yellow]")
        return

    table = Table(title="Offers", show_lines=True)
    table.add_column("Offer ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="bold")
    table.add_column("State", style="green", no_wrap=True)
    table.add_column("Type", style="yellow", no_wrap=True)
    table.add_column("Client", style="magenta")
    table.add_column("Updated", style="magenta", no_wrap=True)

    for offer in offers_data:
        table.add_row(
            _offer_identifier(offer),
            str(offer.get("title", "")),
            str(offer.get("state", "Unknown")),
            str(offer.get("type", "Unknown")),
            _offer_client_name(offer),
            str(
                offer.get("lastUpdatedDateTime")
                or offer.get("lastPublishedDateTime")
                or ""
            ),
        )

    console.print(table)


@offers.command("show")
@click.argument("offer_id")
def show_offer(offer_id: str) -> None:
    """Show detailed information for a specific offer."""
    client = _get_client()

    try:
        offer = client.get_offer(offer_id)
    except Exception as exc:
        console.print(f"[red]Failed to fetch offer {offer_id}: {exc}[/red]")
        raise SystemExit(1)

    if not offer:
        console.print(f"[yellow]Offer {offer_id} was not found.[/yellow]")
        raise SystemExit(1)

    terms = offer.get("offerTerms") or {}
    vendor_proposal = offer.get("vendorProposal") or {}
    lines = [
        f"[bold]Offer ID:[/bold] {offer.get('id', '')}",
        f"[bold]State:[/bold] {offer.get('state', 'Unknown')}",
        f"[bold]Type:[/bold] {offer.get('type', 'Unknown')}",
        f"[bold]Client:[/bold] {_offer_client_name(offer)}",
        f"[bold]Job:[/bold] {(offer.get('job') or {}).get('title', 'N/A')}",
        f"[bold]Application ID:[/bold] {vendor_proposal.get('id', 'N/A')}",
        f"[bold]Application Status:[/bold] {(vendor_proposal.get('status') or {}).get('status', 'N/A')}",
        f"[bold]Terms:[/bold] {_format_offer_terms(terms)}",
        f"[bold]Start Date:[/bold] {terms.get('expectedStartDate', 'N/A')}",
        f"[bold]End Date:[/bold] {terms.get('expectedEndDate', 'N/A')}",
        f"[bold]Close Job On Accept:[/bold] {offer.get('closeJobPostingOnAccept', False)}",
    ]

    console.print(
        Panel(
            "\n".join(lines),
            title=str(offer.get("title", "Offer Details")),
            border_style="cyan",
        )
    )

    description = str(offer.get("description", "")).strip()
    if description:
        console.print(
            Panel(
                description,
                title="Offer Description",
                border_style="magenta",
            )
        )

    message = str(offer.get("messageToContractor", "")).strip()
    if message:
        console.print(
            Panel(
                message,
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
        client.withdraw_offer(offer_id, reason=gql_reason, message=message or None)
    except Exception as exc:
        console.print(f"[red]Failed to withdraw offer: {exc}[/red]")
        raise SystemExit(1)

    console.print("[green]Offer withdrawn successfully.[/green]")
