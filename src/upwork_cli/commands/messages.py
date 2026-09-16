"""Click command group for managing Upwork messages from the terminal."""

import click
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from upwork_cli import messaging, output
from upwork_cli.client import NotAuthenticated, UpworkClient, get_client
from upwork_cli.models import Conversation, Message
from upwork_cli.output import console

AUTH_ERROR_MESSAGE = (
    "Not authenticated. Run [bold]upwork config setup[/bold] to configure "
    "your API credentials."
)


def _get_client() -> UpworkClient:
    """Return an authenticated client, reporting the failure to the terminal."""
    try:
        return get_client()
    except NotAuthenticated:
        output.fail(AUTH_ERROR_MESSAGE)


def _message_panel(message: Message, is_own: bool) -> Panel:
    """Render one message; own messages sit right, in blue."""
    stamp = f"{message.sender_label}  {message.created_at}"
    if is_own:
        return Panel(
            message.content or "(empty)",
            title=Text(
                f"{message.sender_label} (you)  {message.created_at}", style="bold blue"
            ),
            title_align="right",
            border_style="blue",
            padding=(0, 2),
        )
    return Panel(
        message.content or "(empty)",
        title=Text(stamp, style="bold green"),
        title_align="left",
        border_style="green",
        padding=(0, 2),
    )


def _print_conversation(conversation: Conversation) -> None:
    for message in conversation.messages:
        console.print(_message_panel(message, conversation.is_own(message)))


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
    try:
        rooms = messaging.list_rooms(client, limit)
    except messaging.MessagingError as exc:
        output.fail(exc)

    if not rooms:
        output.empty("No conversations found.")
        return

    table = Table(title="Recent Conversations", show_lines=True)
    table.add_column("Room ID", style="cyan", no_wrap=True)
    table.add_column("Participants", style="green")
    table.add_column("Last Message Preview", style="white", max_width=60)
    table.add_column("Updated At", style="magenta", no_wrap=True)

    for room in rooms:
        table.add_row(
            room.id,
            ", ".join(room.participants) or "N/A",
            room.last_message[:60] or "(no messages)",
            room.updated_at,
        )

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
    """Read the messages in a conversation."""
    client = _get_client()
    try:
        conversation = messaging.read_room(client, room_id, limit)
    except messaging.MessagingError as exc:
        output.fail(exc)

    if not conversation.messages:
        output.empty(f"No messages found in room {room_id}.")
        return

    console.print(f"\n[bold]Conversation in room [cyan]{room_id}[/cyan][/bold]\n")
    _print_conversation(conversation)
    console.print()


@messages.command("send")
@click.argument("room_id")
@click.argument("text")
def send_message(room_id: str, text: str) -> None:
    """Send a message to a conversation."""
    client = _get_client()

    console.print(f"\n[bold]Room:[/bold] {room_id}")
    console.print(f"[bold]Message:[/bold] {text}\n")

    if not click.confirm("Send this message?"):
        output.warn("Message not sent.")
        return

    try:
        messaging.send_message(client, room_id, text)
    except messaging.MessagingError as exc:
        output.fail(exc)

    console.print("[green]Message sent successfully.[/green]\n")
    console.print(
        Panel(
            text,
            title=Text("You (just now)", style="bold blue"),
            title_align="right",
            border_style="blue",
            padding=(0, 2),
        )
    )


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
    help="Number of recent messages to display.",
)
def find_room(contract: str, limit: int) -> None:
    """Find a message room by contract reference."""
    client = _get_client()
    try:
        conversation = messaging.find_room_for_contract(client, contract, limit)
    except messaging.MessagingError as exc:
        output.fail(exc)

    if conversation is None:
        output.empty(f"No room found for contract {contract}.")
        return

    console.print(
        f"\n[bold green]Found room:[/bold green] [cyan]{conversation.room_id}[/cyan] "
        f"for contract [cyan]{contract}[/cyan]\n"
    )

    if not conversation.messages:
        output.empty("No recent messages in this room.")
        return

    console.print(f"[bold]Recent messages ({len(conversation.messages)}):[/bold]\n")
    _print_conversation(conversation)
    console.print()
