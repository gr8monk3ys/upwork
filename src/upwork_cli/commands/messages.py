"""Click command group for managing Upwork messages from the terminal."""

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from upwork_cli.client import UpworkClient
from upwork_cli.config import load_settings
from upwork_cli.models import Message

console = Console()

AUTH_ERROR_MESSAGE = (
    "Not authenticated. Run [bold]upwork config setup[/bold] to configure "
    "your API credentials."
)


def _get_client() -> UpworkClient:
    """Create and validate an authenticated UpworkClient."""
    settings = load_settings()
    client = UpworkClient(settings=settings)
    if not client.is_authenticated:
        console.print(f"\n[red]{AUTH_ERROR_MESSAGE}[/red]\n")
        raise SystemExit(1)
    return client


def _get_company(client: UpworkClient) -> str:
    """Retrieve the user's company reference from the Upwork API."""
    try:
        result = client.get_companies()
        # The API typically returns a nested structure; extract the first company reference.
        company_list = (
            result.get("companies", {}).get("company", [])
            if isinstance(result.get("companies"), dict)
            else result.get("companies", [])
        )
        if isinstance(company_list, dict):
            company_list = [company_list]
        if not company_list:
            console.print("[red]No companies found for your account.[/red]")
            raise SystemExit(1)
        # Use the company reference (typically the first one for freelancers)
        company = company_list[0]
        return company.get("company_id", company.get("reference", ""))
    except SystemExit:
        raise
    except Exception as exc:
        console.print(f"[red]Failed to retrieve company info: {exc}[/red]")
        raise SystemExit(1)


def _get_user_id(client: UpworkClient) -> str:
    """Retrieve the current user's ID for identifying own messages."""
    try:
        info = client.get_user_info()
        return info.get("info", {}).get("ref", info.get("id", ""))
    except Exception:
        return ""


@click.group(invoke_without_command=True)
@click.pass_context
def messages(ctx: click.Context) -> None:
    """Manage Upwork messages and conversations."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(list_rooms)


@messages.command("list")
@click.option(
    "--limit",
    default=20,
    show_default=True,
    type=int,
    help="Number of rooms to display.",
)
def list_rooms(limit: int) -> None:
    """List recent message conversations/rooms."""
    client = _get_client()
    company = _get_company(client)

    try:
        result = client.get_rooms(company, {"paging": f"0;{limit}"})
    except Exception as exc:
        console.print(f"[red]Failed to fetch rooms: {exc}[/red]")
        raise SystemExit(1)

    rooms = result.get("rooms", [])
    if isinstance(rooms, dict):
        rooms = rooms.get("room", [])
    if isinstance(rooms, dict):
        rooms = [rooms]

    if not rooms:
        console.print("[yellow]No conversations found.[/yellow]")
        return

    table = Table(title="Recent Conversations", show_lines=True)
    table.add_column("Room ID", style="cyan", no_wrap=True)
    table.add_column("Participants", style="green")
    table.add_column("Last Message Preview", style="white", max_width=60)
    table.add_column("Updated At", style="magenta", no_wrap=True)

    for room in rooms[:limit]:
        room_id = room.get("roomId", room.get("id", ""))

        # Extract participant names
        roster = room.get("roster", [])
        if isinstance(roster, dict):
            roster = roster.get("user", [])
        if isinstance(roster, dict):
            roster = [roster]
        participants = (
            ", ".join(u.get("name", u.get("userId", "Unknown")) for u in roster)
            if roster
            else "N/A"
        )

        # Extract last message preview
        recent = room.get("recentMessage", room.get("lastMessage", {})) or {}
        if isinstance(recent, str):
            preview = recent[:60]
        else:
            preview = (recent.get("message", recent.get("text", "")) or "")[:60]
        if not preview:
            preview = "(no messages)"

        updated = room.get(
            "roomUpdatedDate", room.get("updatedAt", room.get("updated_at", ""))
        )

        table.add_row(str(room_id), participants, preview, str(updated or ""))

    console.print(table)


@messages.command("read")
@click.argument("room_id")
@click.option(
    "--limit",
    default=50,
    show_default=True,
    type=int,
    help="Number of messages to display.",
)
def read_messages(room_id: str, limit: int) -> None:
    """Read messages in a conversation."""
    client = _get_client()
    company = _get_company(client)
    user_id = _get_user_id(client)

    try:
        result = client.get_room_messages(company, room_id, {"paging": f"0;{limit}"})
    except Exception as exc:
        console.print(f"[red]Failed to fetch messages: {exc}[/red]")
        raise SystemExit(1)

    stories = result.get("stories", result.get("messages", []))
    if isinstance(stories, dict):
        stories = stories.get("story", stories.get("message", []))
    if isinstance(stories, dict):
        stories = [stories]

    if not stories:
        console.print(f"[yellow]No messages found in room {room_id}.[/yellow]")
        return

    console.print(f"\n[bold]Conversation in room [cyan]{room_id}[/cyan][/bold]\n")

    for entry in stories:
        msg = Message.from_api(entry, room_id=room_id)
        sender_id = entry.get("userId", entry.get("user", {}).get("id", ""))
        sender_name = msg.sender or "Unknown"
        timestamp = msg.created_at
        content = msg.content

        is_own = bool(user_id and str(sender_id) == str(user_id))

        if is_own:
            # Own messages: right-aligned, blue border
            header = Text(f"{sender_name} (you)  {timestamp}", style="bold blue")
            panel = Panel(
                content or "(empty)",
                title=header,
                title_align="right",
                border_style="blue",
                padding=(0, 2),
            )
        else:
            # Other messages: left-aligned, green border
            header = Text(f"{sender_name}  {timestamp}", style="bold green")
            panel = Panel(
                content or "(empty)",
                title=header,
                title_align="left",
                border_style="green",
                padding=(0, 2),
            )

        console.print(panel)

    console.print()


@messages.command("send")
@click.argument("room_id")
@click.argument("text")
def send_message(room_id: str, text: str) -> None:
    """Send a message to a conversation."""
    client = _get_client()
    company = _get_company(client)

    console.print(f"\n[bold]Room:[/bold] {room_id}")
    console.print(f"[bold]Message:[/bold] {text}\n")

    if not click.confirm("Send this message?"):
        console.print("[yellow]Message not sent.[/yellow]")
        return

    try:
        client.send_message(company, room_id, {"message": text})
    except Exception as exc:
        console.print(f"[red]Failed to send message: {exc}[/red]")
        raise SystemExit(1)

    console.print("[green]Message sent successfully.[/green]\n")

    # Display the sent message in a panel
    panel = Panel(
        text,
        title=Text("You (just now)", style="bold blue"),
        title_align="right",
        border_style="blue",
        padding=(0, 2),
    )
    console.print(panel)


@messages.command("find")
@click.option(
    "--contract",
    required=True,
    type=str,
    help="Contract reference to find the room for.",
)
@click.option(
    "--limit",
    default=10,
    show_default=True,
    type=int,
    help="Number of recent messages to show.",
)
def find_room(contract: str, limit: int) -> None:
    """Find a message room by contract reference."""
    client = _get_client()
    company = _get_company(client)

    try:
        result = client.get_room_by_contract(company, contract)
    except Exception as exc:
        console.print(f"[red]Failed to find room for contract {contract}: {exc}[/red]")
        raise SystemExit(1)

    room = result.get("room", result)
    if isinstance(room, list):
        room = room[0] if room else {}

    room_id = room.get("roomId", room.get("id", ""))
    if not room_id:
        console.print(f"[yellow]No room found for contract {contract}.[/yellow]")
        return

    console.print(
        f"\n[bold green]Found room:[/bold green] [cyan]{room_id}[/cyan] for contract [cyan]{contract}[/cyan]\n"
    )

    # Show recent messages from the room
    try:
        msg_result = client.get_room_messages(
            company, str(room_id), {"paging": f"0;{limit}"}
        )
    except Exception as exc:
        console.print(f"[yellow]Room found but could not load messages: {exc}[/yellow]")
        return

    stories = msg_result.get("stories", msg_result.get("messages", []))
    if isinstance(stories, dict):
        stories = stories.get("story", stories.get("message", []))
    if isinstance(stories, dict):
        stories = [stories]

    if not stories:
        console.print("[yellow]No recent messages in this room.[/yellow]")
        return

    user_id = _get_user_id(client)

    console.print(f"[bold]Recent messages ({len(stories)}):[/bold]\n")

    for entry in stories:
        msg = Message.from_api(entry, room_id=str(room_id))
        sender_id = entry.get("userId", entry.get("user", {}).get("id", ""))
        sender_name = msg.sender or "Unknown"
        timestamp = msg.created_at
        content = msg.content

        is_own = bool(user_id and str(sender_id) == str(user_id))

        if is_own:
            header = Text(f"{sender_name} (you)  {timestamp}", style="bold blue")
            panel = Panel(
                content or "(empty)",
                title=header,
                title_align="right",
                border_style="blue",
                padding=(0, 2),
            )
        else:
            header = Text(f"{sender_name}  {timestamp}", style="bold green")
            panel = Panel(
                content or "(empty)",
                title=header,
                title_align="left",
                border_style="green",
                padding=(0, 2),
            )

        console.print(panel)

    console.print()
