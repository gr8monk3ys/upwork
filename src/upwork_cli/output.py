"""Terminal output for the CLI.

One Console, and one home for the decisions every command was making
separately: what an error does to the exit code, what "nothing found" looks
like, and how money reads.

Deliberately not a table builder. The seventeen tables in this CLI differ in
column styles, widths, wrapping and justification, so a helper general enough
for all of them would take as many arguments as ``rich.Table`` itself and
hide nothing.
"""

from typing import NoReturn

from rich.console import Console

console = Console()


def fail(message: object) -> NoReturn:
    """Report a failure and exit non-zero.

    Every command failure exits 1. Two commands used to print an error and
    return 0, which left callers unable to tell an auth failure from an
    empty result.
    """
    console.print(f"[red]{message}[/red]")
    raise SystemExit(1)


def empty(message: str) -> None:
    """Report that there was nothing to show. Not an error: exit stays 0."""
    console.print(f"[yellow]{message}[/yellow]")


def warn(message: str) -> None:
    """Report something the user should notice but which is not fatal."""
    console.print(f"[yellow]{message}[/yellow]")


def money(amount: float | None, currency: str = "USD") -> str:
    """Format an amount of money.

    Always two decimals and always the currency: the old per-module
    formatters variously dropped the cents or dropped the currency, so the
    same figure read three different ways depending on which command
    printed it.
    """
    if amount is None:
        return "N/A"
    return f"${amount:,.2f} {currency}"


def truncate(text: str, length: int) -> str:
    """Shorten *text* to *length*, marking where it was cut."""
    text = text or ""
    return text if len(text) <= length else text[: max(0, length - 3)] + "..."
