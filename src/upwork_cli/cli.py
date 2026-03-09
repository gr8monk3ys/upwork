"""Main CLI entry point for the Upwork toolkit."""

import click
from rich.console import Console

from upwork_cli.db import init_db

console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="upwork")
def cli():
    """Upwork CLI toolkit for freelancer management.

    Search jobs, generate AI proposals, track earnings, and manage messages
    from your terminal.

    Run 'upwork config setup' to get started.
    """
    init_db()


def register_commands():
    """Register all command groups."""
    from upwork_cli.commands.applications import applications, offers
    from upwork_cli.commands.config import config
    from upwork_cli.commands.jobs import jobs
    from upwork_cli.commands.propose import propose
    from upwork_cli.commands.earnings import earnings, contracts
    from upwork_cli.commands.messages import messages
    from upwork_cli.commands.pipeline import pipeline

    cli.add_command(config)
    cli.add_command(jobs)
    cli.add_command(propose)
    cli.add_command(applications)
    cli.add_command(offers)
    cli.add_command(earnings)
    cli.add_command(contracts)
    cli.add_command(messages)
    cli.add_command(pipeline)


register_commands()


if __name__ == "__main__":
    cli()
