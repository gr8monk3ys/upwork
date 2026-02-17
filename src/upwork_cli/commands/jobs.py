"""Click command group for job search, scoring, watching, and bookmarking."""

import click
import time
import json
import urllib.request

from rich.console import Console
from rich.table import Table
import feedparser

from upwork_cli.client import UpworkClient
from upwork_cli.config import load_settings, load_profile
from upwork_cli.db import (
    init_db,
    upsert_job,
    save_score,
    save_bookmark,
    remove_bookmark,
    get_bookmarks,
    mark_seen,
    is_seen,
    get_jobs_with_scores,
)
from upwork_cli.models import JobPosting
from upwork_cli.ai.scorer import score_jobs_batch

console = Console()

RSS_URL = "https://www.upwork.com/ab/feed/jobs/rss?q={query}&sort=recency"


def _truncate(text: str, length: int) -> str:
    """Truncate text to a given length, appending ellipsis if needed."""
    if len(text) <= length:
        return text
    return text[: length - 3] + "..."


def _format_budget(amount, currency="USD") -> str:
    """Format a budget amount for display."""
    if amount is None:
        return "N/A"
    return f"${amount:,.0f} {currency}"


def _format_skills(skills, max_count: int = 3) -> str:
    """Format a skills list, showing only the first max_count items."""
    if not skills:
        return ""
    if isinstance(skills, str):
        try:
            skills = json.loads(skills)
        except (json.JSONDecodeError, TypeError):
            return skills
    shown = skills[:max_count]
    suffix = f" +{len(skills) - max_count}" if len(skills) > max_count else ""
    return ", ".join(shown) + suffix


def _score_color(score: int) -> str:
    """Return a Rich color string based on the score value."""
    if score >= 8:
        return "green"
    elif score >= 5:
        return "yellow"
    else:
        return "red"


def _search_via_rss(query: str, limit: int) -> list[JobPosting]:
    """Fetch jobs from the Upwork RSS feed (unauthenticated fallback).

    NOTE: Upwork deprecated RSS feeds in August 2024. This will return an
    empty list with a warning. Kept for potential future restoration.
    """
    encoded_query = urllib.request.quote(query)
    url = RSS_URL.format(query=encoded_query)
    feed = feedparser.parse(url)
    if feed.get("status", 0) in (410, 403, 404) or not feed.entries:
        console.print(
            "[yellow]Upwork RSS feeds were deprecated in August 2024.[/yellow]\n"
            "You need to authenticate to search jobs: [bold]upwork config setup[/bold]"
        )
        return []
    jobs = []
    for entry in feed.entries[:limit]:
        job = JobPosting.from_rss(entry)
        jobs.append(job)
    return jobs


def _search_via_api(client: UpworkClient, query: str, limit: int, **filters) -> list[JobPosting]:
    """Fetch jobs from the Upwork API (authenticated)."""
    try:
        result = client.search_jobs_graphql(search_term=query, limit=limit)
        postings = result.get("data", {}).get("marketplaceJobPostings", {})
        edges = postings.get("edges", [])
        jobs = []
        for edge in edges:
            node = edge.get("node", {})
            job = JobPosting.from_graphql(node)
            jobs.append(job)
        return jobs
    except Exception as exc:
        console.print(f"[yellow]API search failed ({exc}), falling back to RSS feed.[/yellow]")
        return _search_via_rss(query, limit)


def _filter_jobs(
    jobs: list[JobPosting],
    budget_min: float | None,
    budget_max: float | None,
    job_type: str | None,
    posted: str | None,
) -> list[JobPosting]:
    """Apply client-side filters to a list of jobs."""
    filtered = []
    for job in jobs:
        if budget_min is not None and (job.budget_amount is None or job.budget_amount < budget_min):
            continue
        if budget_max is not None and (job.budget_amount is None or job.budget_amount > budget_max):
            continue
        # Type and posted filters are best-effort since RSS/API may not expose these clearly
        filtered.append(job)
    return filtered


def _display_jobs_table(jobs: list[JobPosting], title: str = "Search Results") -> None:
    """Render a Rich table of job postings."""
    table = Table(title=title, show_lines=True)
    table.add_column("Title", style="bold cyan", max_width=50)
    table.add_column("Budget", justify="right")
    table.add_column("Skills")
    table.add_column("Client Country")
    table.add_column("Posted")

    for job in jobs:
        table.add_row(
            _truncate(job.title, 50),
            _format_budget(job.budget_amount, job.budget_currency),
            _format_skills(job.skills, 3),
            job.client_country or "N/A",
            job.created_at or "N/A",
        )

    console.print(table)


def _send_discord_notification(webhook_url: str, message: str) -> None:
    """Send a notification to a Discord webhook."""
    payload = json.dumps({"content": message}).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req)
    except Exception as exc:
        console.print(f"[red]Discord notification failed: {exc}[/red]")


@click.group()
def jobs():
    """Job search, scoring, watching, and bookmarking commands."""
    pass


@jobs.command()
@click.argument("query")
@click.option("--budget-min", type=float, default=None, help="Minimum budget filter.")
@click.option("--budget-max", type=float, default=None, help="Maximum budget filter.")
@click.option("--type", "job_type", type=click.Choice(["fixed", "hourly"]), default=None, help="Job type filter.")
@click.option(
    "--posted",
    type=click.Choice(["1h", "3h", "12h", "24h", "3d", "7d"]),
    default=None,
    help="Posted time filter.",
)
@click.option("--limit", type=int, default=20, help="Maximum number of results.")
@click.pass_context
def search(ctx, query, budget_min, budget_max, job_type, posted, limit):
    """Search for jobs on Upwork."""
    init_db()
    settings = load_settings()
    client = UpworkClient(settings=settings)

    console.print(f"[bold]Searching for:[/bold] {query}")

    if client.is_authenticated:
        results = _search_via_api(client, query, limit)
    else:
        console.print("[dim]Not authenticated -- using RSS feed.[/dim]")
        results = _search_via_rss(query, limit)

    results = _filter_jobs(results, budget_min, budget_max, job_type, posted)

    if not results:
        console.print("[yellow]No jobs found matching your query.[/yellow]")
        return

    # Cache results in the database
    for job in results:
        upsert_job(job.to_db_dict())

    _display_jobs_table(results, title=f"Jobs: {query}")
    console.print(f"\n[dim]{len(results)} job(s) found and cached.[/dim]")


@jobs.command()
@click.pass_context
def score(ctx):
    """AI-score the most recent search results."""
    init_db()
    settings = load_settings()
    profile = load_profile()

    if not settings.anthropic_api_key:
        console.print("[red]Anthropic API key not configured. Run 'upwork config' to set it.[/red]")
        return

    if not profile.title and not profile.skills:
        console.print("[yellow]Profile is empty. Run 'upwork profile' to set up your profile first.[/yellow]")
        return

    cached_jobs = get_jobs_with_scores(limit=50)
    # Filter to jobs that have not been scored yet
    unscored = [j for j in cached_jobs if j.get("score") is None]

    if not unscored:
        console.print("[yellow]No unscored jobs found. Run 'jobs search' first.[/yellow]")
        return

    console.print(f"[bold]Scoring {len(unscored)} job(s) against your profile...[/bold]\n")

    profile_summary = profile.summary()

    # Build the batch input for the scorer
    batch = []
    for row in unscored:
        skills = row.get("skills", "[]")
        if isinstance(skills, str):
            try:
                skills = json.loads(skills)
            except (json.JSONDecodeError, TypeError):
                skills = []

        job_obj = JobPosting(
            id=row["id"],
            title=row.get("title", ""),
            description=row.get("description", ""),
            skills=skills,
            budget_amount=row.get("budget_amount"),
            budget_currency=row.get("budget_currency", "USD"),
            duration=row.get("duration", ""),
            engagement=row.get("engagement", ""),
            client_country=row.get("client_country", ""),
            client_total_spent=row.get("client_total_spent"),
            client_total_hires=row.get("client_total_hires"),
            client_feedback=row.get("client_feedback"),
            created_at=row.get("created_at", ""),
        )
        batch.append({
            "id": job_obj.id,
            "title": job_obj.title,
            "summary": job_obj.summary_for_ai(),
        })

    scored = score_jobs_batch(batch, profile_summary, settings.anthropic_api_key)

    # Save scores to the database
    for item in scored:
        save_score(item["id"], item["score"], item.get("reasoning", ""))

    # Display scored results
    table = Table(title="Job Scores", show_lines=True)
    table.add_column("Score", justify="center", width=6)
    table.add_column("Title", style="bold cyan", max_width=50)
    table.add_column("Budget", justify="right")
    table.add_column("Reasoning", max_width=60)

    for item in scored:
        sc = item["score"]
        color = _score_color(sc)
        # Look up budget from the original row
        original = next((r for r in unscored if r["id"] == item["id"]), {})
        budget = _format_budget(original.get("budget_amount"), original.get("budget_currency", "USD"))

        table.add_row(
            f"[{color}]{sc}[/{color}]",
            _truncate(item.get("title", ""), 50),
            budget,
            item.get("reasoning", ""),
        )

    console.print(table)
    console.print(f"\n[dim]{len(scored)} job(s) scored.[/dim]")


@jobs.command()
@click.argument("query")
@click.option("--interval", type=int, default=5, help="Check interval in minutes.")
@click.option("--min-score", type=int, default=7, help="Minimum score threshold for alerts.")
@click.option(
    "--notify",
    type=click.Choice(["terminal", "discord"]),
    default="terminal",
    help="Notification method.",
)
@click.pass_context
def watch(ctx, query, interval, min_score, notify):
    """Monitor for new jobs matching a query."""
    init_db()
    settings = load_settings()
    profile = load_profile()

    if notify == "discord" and not settings.discord_webhook_url:
        console.print("[red]Discord webhook URL not configured. Run 'upwork config' to set it.[/red]")
        return

    has_scoring = bool(settings.anthropic_api_key and (profile.title or profile.skills))
    if not has_scoring:
        console.print("[yellow]Scoring disabled: missing API key or profile. New jobs will not be scored.[/yellow]")

    profile_summary = profile.summary() if has_scoring else ""
    client = UpworkClient(settings=settings)

    console.print(f"[bold]Watching for:[/bold] {query}")
    console.print(f"[dim]Interval: {interval}m | Min score: {min_score} | Notify: {notify}[/dim]")
    console.print("[dim]Press Ctrl+C to stop.[/dim]\n")

    try:
        while True:
            # Fetch latest results
            if client.is_authenticated:
                results = _search_via_api(client, query, limit=20)
            else:
                results = _search_via_rss(query, limit=20)

            # Deduplicate against previously seen jobs
            new_jobs = []
            for job in results:
                if not is_seen(job.id):
                    new_jobs.append(job)
                    mark_seen(job.id, query)
                    upsert_job(job.to_db_dict())

            if not new_jobs:
                console.print(f"[dim]{time.strftime('%H:%M:%S')} -- No new jobs.[/dim]")
            else:
                console.print(
                    f"[bold green]{time.strftime('%H:%M:%S')} -- {len(new_jobs)} new job(s) found![/bold green]"
                )

                # Score new jobs if possible
                if has_scoring:
                    batch = [
                        {
                            "id": job.id,
                            "title": job.title,
                            "summary": job.summary_for_ai(),
                        }
                        for job in new_jobs
                    ]
                    scored = score_jobs_batch(batch, profile_summary, settings.anthropic_api_key)

                    for item in scored:
                        save_score(item["id"], item["score"], item.get("reasoning", ""))

                    # Alert on jobs above threshold
                    hot_jobs = [s for s in scored if s["score"] >= min_score]
                else:
                    # Without scoring, treat all new jobs as alert-worthy
                    hot_jobs = [{"id": j.id, "title": j.title, "score": "?"} for j in new_jobs]

                for hj in hot_jobs:
                    title = hj.get("title", "Untitled")
                    sc = hj.get("score", "?")
                    alert_msg = f"[Score {sc}] {title}"

                    if notify == "terminal":
                        console.print(f"  [bold yellow]>> {alert_msg}[/bold yellow]")
                        console.bell()
                    elif notify == "discord":
                        _send_discord_notification(
                            settings.discord_webhook_url,
                            f"New Upwork job match!\n**{alert_msg}**",
                        )

                if not hot_jobs and has_scoring:
                    console.print(f"  [dim]No jobs scored above {min_score}.[/dim]")

            time.sleep(interval * 60)

    except KeyboardInterrupt:
        console.print("\n[bold]Watch stopped.[/bold]")


@jobs.command()
@click.argument("job_id")
@click.pass_context
def detail(ctx, job_id):
    """Show full details for a specific job."""
    init_db()
    settings = load_settings()
    client = UpworkClient(settings=settings)

    # Try the API first if authenticated
    if client.is_authenticated:
        try:
            data = client.get_job_detail(job_id)
            job = JobPosting.from_rest(data) if data else None
        except Exception as exc:
            console.print(f"[yellow]API lookup failed ({exc}), checking local cache.[/yellow]")
            job = None
    else:
        job = None

    # Fall back to the local DB cache
    if job is None:
        cached = get_jobs_with_scores(limit=500)
        match = next((r for r in cached if r["id"] == job_id), None)
        if match is None:
            console.print(f"[red]Job '{job_id}' not found in API or local cache.[/red]")
            return
        skills = match.get("skills", "[]")
        if isinstance(skills, str):
            try:
                skills = json.loads(skills)
            except (json.JSONDecodeError, TypeError):
                skills = []
        job = JobPosting(
            id=match["id"],
            title=match.get("title", ""),
            description=match.get("description", ""),
            skills=skills,
            budget_amount=match.get("budget_amount"),
            budget_currency=match.get("budget_currency", "USD"),
            duration=match.get("duration", ""),
            engagement=match.get("engagement", ""),
            client_country=match.get("client_country", ""),
            client_total_spent=match.get("client_total_spent"),
            client_total_hires=match.get("client_total_hires"),
            client_feedback=match.get("client_feedback"),
            created_at=match.get("created_at", ""),
        )

    # Display full details
    console.print()
    console.rule(f"[bold]{job.title}[/bold]")
    console.print(f"[bold]ID:[/bold] {job.id}")
    console.print(f"[bold]Budget:[/bold] {_format_budget(job.budget_amount, job.budget_currency)}")
    console.print(f"[bold]Skills:[/bold] {', '.join(job.skills) if job.skills else 'N/A'}")
    console.print(f"[bold]Duration:[/bold] {job.duration or job.duration_label or 'N/A'}")
    console.print(f"[bold]Engagement:[/bold] {job.engagement or 'N/A'}")
    console.print(f"[bold]Posted:[/bold] {job.created_at or 'N/A'}")
    console.print()
    console.print("[bold]Client Info:[/bold]")
    console.print(f"  Country: {job.client_country or 'N/A'}")
    console.print(f"  Total Spent: {_format_budget(job.client_total_spent) if job.client_total_spent else 'N/A'}")
    console.print(f"  Total Hires: {job.client_total_hires if job.client_total_hires is not None else 'N/A'}")
    console.print(f"  Feedback: {job.client_feedback if job.client_feedback is not None else 'N/A'}")
    console.print(f"  Verified: {'Yes' if job.client_verified else 'No'}")
    console.print()
    console.print("[bold]Description:[/bold]")
    console.print(job.description or "[dim]No description available.[/dim]")
    console.rule()


@jobs.command()
@click.argument("job_id")
@click.option("--note", type=str, default="", help="Optional note for the bookmark.")
@click.pass_context
def save(ctx, job_id, note):
    """Bookmark a job for later review."""
    init_db()
    save_bookmark(job_id, note)
    console.print(f"[green]Job '{job_id}' bookmarked.[/green]")
    if note:
        console.print(f"[dim]Note: {note}[/dim]")


@jobs.command()
@click.pass_context
def saved(ctx):
    """List all bookmarked jobs."""
    init_db()
    bookmarks = get_bookmarks()

    if not bookmarks:
        console.print("[yellow]No bookmarks yet. Use 'jobs save <job-id>' to bookmark a job.[/yellow]")
        return

    table = Table(title="Bookmarked Jobs", show_lines=True)
    table.add_column("Job ID", style="bold")
    table.add_column("Title", style="cyan", max_width=50)
    table.add_column("Budget", justify="right")
    table.add_column("Note", max_width=40)
    table.add_column("Bookmarked At")

    for bm in bookmarks:
        table.add_row(
            bm.get("job_id", ""),
            _truncate(bm.get("title", "") or "N/A", 50),
            _format_budget(bm.get("budget_amount"), bm.get("budget_currency", "USD")),
            bm.get("note", "") or "",
            bm.get("bookmarked_at", "") or "",
        )

    console.print(table)
    console.print(f"\n[dim]{len(bookmarks)} bookmark(s).[/dim]")
