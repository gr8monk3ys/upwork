"""Click command group for job search, scoring, watching, and bookmarking."""

import json
import time
import urllib.request
from datetime import datetime, timedelta, timezone

import click
from rich.table import Table

from upwork_cli import jobs as jobs_api
from upwork_cli import output
from upwork_cli.client import NotAuthenticated, UpworkClient, get_client
from upwork_cli.config import load_profile, load_settings, save_settings
from upwork_cli.db import (
    get_bookmarks,
    get_job,
    get_unscored_jobs,
    init_db,
    save_bookmark,
)
from upwork_cli.models import JobPosting, ScoreResult
from upwork_cli.output import console
from upwork_cli.scoring import score_jobs


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


def _parse_job_timestamp(value: str) -> datetime | None:
    """Parse common job timestamp formats into a timezone-aware datetime."""
    if not value:
        return None

    candidates = [value.strip()]
    if candidates[0].endswith("Z"):
        candidates.append(candidates[0][:-1] + "+00:00")
    if " " in candidates[0] and "T" not in candidates[0]:
        candidates.append(candidates[0].replace(" ", "T", 1))

    for candidate in candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            continue

    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            continue

    return None


def _matches_job_type(job: JobPosting, job_type: str | None) -> bool:
    """Best-effort job type matching from the engagement label."""
    if not job_type:
        return True

    engagement = (job.engagement or "").lower()
    if job_type == "hourly":
        return "hour" in engagement or "hr" in engagement
    if job_type == "fixed":
        return "fixed" in engagement or "budget" in engagement
    return True


def _matches_posted_window(job: JobPosting, posted: str | None) -> bool:
    """Best-effort recency filtering using the job's timestamp."""
    if not posted:
        return True

    created_at = _parse_job_timestamp(job.created_at)
    if created_at is None:
        return False

    windows = {
        "1h": timedelta(hours=1),
        "3h": timedelta(hours=3),
        "12h": timedelta(hours=12),
        "24h": timedelta(hours=24),
        "3d": timedelta(days=3),
        "7d": timedelta(days=7),
    }
    cutoff = datetime.now(timezone.utc) - windows[posted]
    return created_at >= cutoff


def _search_via_api(client: UpworkClient, query: str, limit: int) -> list[JobPosting]:
    """Fetch jobs from the Upwork API, reporting failure to the terminal."""
    try:
        return jobs_api.search(client, query, limit)
    except jobs_api.JobsError as exc:
        console.print(f"[red]{exc}[/red]")
        return []


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
        if budget_min is not None and (
            job.budget_amount is None or job.budget_amount < budget_min
        ):
            continue
        if budget_max is not None and (
            job.budget_amount is None or job.budget_amount > budget_max
        ):
            continue
        if not _matches_job_type(job, job_type):
            continue
        if not _matches_posted_window(job, posted):
            continue
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
            output.truncate(job.title, 50),
            output.money(job.budget_amount, job.budget_currency),
            _format_skills(job.skills, 3),
            job.client_country or "N/A",
            job.created_at or "N/A",
        )

    console.print(table)


def _send_discord_notification(webhook_url: str, message: str) -> None:
    """Send a notification to a Discord webhook."""
    if not webhook_url.startswith("https://"):
        console.print("[red]Discord webhook URL must use https://[/red]")
        return
    payload = json.dumps({"content": message}).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
        urllib.request.urlopen(req)
    except Exception as exc:
        console.print(f"[red]Discord notification failed: {exc}[/red]")


def _normalize_search_term(query: str) -> str:
    """Return a trimmed, whitespace-normalized search term."""
    return " ".join(query.split())


def _get_saved_search_terms(settings) -> list[str]:
    """Load saved search terms from settings, normalized and deduplicated."""
    seen: set[str] = set()
    terms: list[str] = []
    for item in settings.default_search_terms or []:
        term = _normalize_search_term(str(item))
        if term and term not in seen:
            seen.add(term)
            terms.append(term)
    return terms


def _save_search_terms(settings, terms: list[str]) -> None:
    """Persist saved search terms without changing existing secrets."""
    settings.default_search_terms = terms
    save_settings(settings)


def _collect_new_jobs(results: list[JobPosting], search_term: str) -> list[JobPosting]:
    """Persist and return only unseen jobs for a given search term."""
    return jobs_api.collect_new(results, search_term)


def _score_alert_jobs(
    new_jobs: list[JobPosting],
    min_score: int,
    has_scoring: bool,
    profile_summary: str,
    api_key: str,
    model: str = "",
) -> list[ScoreResult]:
    """Score new jobs when possible and return only alert-worthy ones."""
    if not has_scoring:
        return [ScoreResult(job=job) for job in new_jobs]

    results = score_jobs(new_jobs, profile_summary, api_key, model=model or None)
    return [r for r in results if r.score is not None and r.score >= min_score]


def _notify_hot_jobs(
    hot_jobs: list[ScoreResult], notify: str, webhook_url: str
) -> None:
    """Emit terminal or Discord alerts for high-priority jobs."""
    for result in hot_jobs:
        title = result.job.title or "Untitled"
        score = result.score if result.score is not None else "?"
        alert_msg = f"[Score {score}] {title}"

        if notify == "terminal":
            console.print(f"  [bold yellow]>> {alert_msg}[/bold yellow]")
            console.bell()
        else:
            _send_discord_notification(
                webhook_url,
                f"New Upwork job match!\n**{alert_msg}**",
            )


def _run_search_cycle(
    client: UpworkClient,
    settings,
    query: str,
    limit: int,
    min_score: int,
    notify: str,
    has_scoring: bool,
    profile_summary: str,
    prefix: str = "",
    show_empty_message: bool = True,
) -> tuple[int, int]:
    """Run one search-alert cycle for a query and return (new_jobs, alerts)."""
    results = _search_via_api(client, query, limit=limit)
    new_jobs = _collect_new_jobs(results, query)

    label = f"{prefix}{query}" if prefix else query
    if not new_jobs:
        if show_empty_message:
            console.print(f"[dim]{label}: No new jobs.[/dim]")
        return 0, 0

    console.print(
        f"[bold green]{label}: {len(new_jobs)} new job(s) found![/bold green]"
    )
    hot_jobs = _score_alert_jobs(
        new_jobs,
        min_score=min_score,
        has_scoring=has_scoring,
        profile_summary=profile_summary,
        api_key=settings.anthropic_api_key,
        model=settings.ai_model,
    )
    _notify_hot_jobs(hot_jobs, notify, settings.discord_webhook_url)

    if not hot_jobs and has_scoring:
        console.print(f"  [dim]No jobs scored above {min_score}.[/dim]")

    return len(new_jobs), len(hot_jobs)


@click.group()
def jobs():
    """Job search, scoring, watching, and bookmarking commands."""


@jobs.command()
@click.argument("query")
@click.option("--budget-min", type=float, default=None, help="Minimum budget filter.")
@click.option("--budget-max", type=float, default=None, help="Maximum budget filter.")
@click.option(
    "--type",
    "job_type",
    type=click.Choice(["fixed", "hourly"]),
    default=None,
    help="Job type filter.",
)
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

    console.print(f"[bold]Searching for:[/bold] {query}")

    try:
        client = get_client()
    except NotAuthenticated:
        output.fail("Not authenticated. Run 'upwork config setup' first.")

    results = _search_via_api(client, query, limit)

    results = _filter_jobs(results, budget_min, budget_max, job_type, posted)

    if not results:
        output.empty("No jobs found matching your query.")
        return

    jobs_api.cache(results)

    _display_jobs_table(results, title=f"Jobs: {query}")
    console.print(f"\n[dim]{len(results)} job(s) found and cached.[/dim]")


@jobs.group("searches")
def saved_searches():
    """Manage saved search terms and run job alerts across them."""


@saved_searches.command("list")
def list_saved_searches():
    """List saved search terms."""
    settings = load_settings()
    search_terms = _get_saved_search_terms(settings)
    if not search_terms:
        output.empty("No saved search terms yet.")
        console.print(
            "[dim]Use 'upwork jobs searches add \"python developer\"' to add one.[/dim]"
        )
        return

    table = Table(title="Saved Search Terms", show_lines=True)
    table.add_column("#", justify="right", style="dim")
    table.add_column("Query", style="bold cyan")
    for idx, term in enumerate(search_terms, 1):
        table.add_row(str(idx), term)
    console.print(table)


@saved_searches.command("add")
@click.argument("query")
def add_saved_search(query: str):
    """Add a saved search term."""
    settings = load_settings()
    search_terms = _get_saved_search_terms(settings)
    term = _normalize_search_term(query)
    if not term:
        console.print("[red]Search term cannot be empty.[/red]")
        raise SystemExit(1)
    if term in search_terms:
        output.warn(f"Saved search already exists: {term}")
        return
    search_terms.append(term)
    _save_search_terms(settings, search_terms)
    console.print(f"[green]Added saved search:[/green] {term}")


@saved_searches.command("remove")
@click.argument("query")
def remove_saved_search(query: str):
    """Remove a saved search term."""
    settings = load_settings()
    search_terms = _get_saved_search_terms(settings)
    term = _normalize_search_term(query)
    if term not in search_terms:
        console.print(f"[yellow]Saved search not found:[/yellow] {term}")
        return
    updated_terms = [item for item in search_terms if item != term]
    _save_search_terms(settings, updated_terms)
    console.print(f"[green]Removed saved search:[/green] {term}")


def _prepare_saved_search_run(
    notify: str,
) -> tuple[object, list[str], bool, str, UpworkClient, int, int]:
    """Load shared state for saved-search commands."""
    init_db()
    settings = load_settings()
    profile = load_profile()
    search_terms = _get_saved_search_terms(settings)
    if not search_terms:
        console.print("[yellow]No saved search terms configured.")
        console.print(
            "[dim]Use 'upwork jobs searches add \"python developer\"' to add one.[/dim]"
        )
        raise SystemExit(1)

    if notify == "discord" and not settings.discord_webhook_url:
        console.print(
            "[red]Discord webhook URL not configured. Run 'upwork config setup' to set it.[/red]"
        )
        raise SystemExit(1)

    has_scoring = bool(settings.anthropic_api_key and (profile.title or profile.skills))
    if not has_scoring:
        output.warn(
            "Scoring disabled: missing API key or profile. New jobs will not be scored."
        )

    profile_summary = profile.summary() if has_scoring else ""
    try:
        client = get_client()
    except NotAuthenticated:
        output.fail("Not authenticated. Run 'upwork config setup' first.")

    return (
        settings,
        search_terms,
        has_scoring,
        profile_summary,
        client,
        settings.watch_interval_minutes,
        settings.min_score_threshold,
    )


@saved_searches.command("run")
@click.option(
    "--limit",
    type=int,
    default=20,
    show_default=True,
    help="Maximum results per saved search.",
)
@click.option(
    "--min-score", type=int, default=None, help="Minimum score threshold for alerts."
)
@click.option(
    "--notify",
    type=click.Choice(["terminal", "discord"]),
    default="terminal",
    show_default=True,
    help="Notification method.",
)
def run_saved_searches(limit: int, min_score: int | None, notify: str):
    """Run all saved searches once and alert on new matches."""
    (
        settings,
        search_terms,
        has_scoring,
        profile_summary,
        client,
        _interval_default,
        min_score_default,
    ) = _prepare_saved_search_run(notify)
    min_score = min_score if min_score is not None else min_score_default

    console.print(f"[bold]Running {len(search_terms)} saved search(es)...[/bold]")
    total_new = 0
    total_alerts = 0
    for query in search_terms:
        new_count, alert_count = _run_search_cycle(
            client,
            settings,
            query=query,
            limit=limit,
            min_score=min_score,
            notify=notify,
            has_scoring=has_scoring,
            profile_summary=profile_summary,
        )
        total_new += new_count
        total_alerts += alert_count

    if total_new == 0:
        output.empty("No new jobs found across saved searches.")
        return

    console.print(
        f"\n[dim]Saved search run complete: {total_new} new job(s), {total_alerts} alert(s).[/dim]"
    )


@saved_searches.command("watch")
@click.option("--interval", type=int, default=None, help="Check interval in minutes.")
@click.option(
    "--limit",
    type=int,
    default=20,
    show_default=True,
    help="Maximum results per saved search.",
)
@click.option(
    "--min-score", type=int, default=None, help="Minimum score threshold for alerts."
)
@click.option(
    "--notify",
    type=click.Choice(["terminal", "discord"]),
    default="terminal",
    show_default=True,
    help="Notification method.",
)
def watch_saved_searches(
    interval: int | None, limit: int, min_score: int | None, notify: str
):
    """Continuously watch all saved searches."""
    (
        settings,
        search_terms,
        has_scoring,
        profile_summary,
        client,
        interval_default,
        min_score_default,
    ) = _prepare_saved_search_run(notify)
    interval = interval if interval is not None else interval_default
    min_score = min_score if min_score is not None else min_score_default

    console.print(f"[bold]Watching {len(search_terms)} saved search(es)...[/bold]")
    for query in search_terms:
        console.print(f"[dim]- {query}[/dim]")
    console.print(
        f"[dim]Interval: {interval}m | Min score: {min_score} | Notify: {notify}[/dim]"
    )
    console.print("[dim]Press Ctrl+C to stop.[/dim]\n")

    try:
        while True:
            cycle_new = 0
            cycle_alerts = 0
            stamp = time.strftime("%H:%M:%S")
            for query in search_terms:
                new_count, alert_count = _run_search_cycle(
                    client,
                    settings,
                    query=query,
                    limit=limit,
                    min_score=min_score,
                    notify=notify,
                    has_scoring=has_scoring,
                    profile_summary=profile_summary,
                    prefix=f"{stamp} -- ",
                    show_empty_message=False,
                )
                cycle_new += new_count
                cycle_alerts += alert_count

            if cycle_new == 0:
                console.print(
                    f"[dim]{stamp} -- No new jobs across saved searches.[/dim]"
                )
            elif has_scoring and cycle_alerts == 0:
                console.print(
                    f"[dim]{stamp} -- No saved-search jobs scored above {min_score}.[/dim]"
                )

            time.sleep(interval * 60)
    except KeyboardInterrupt:
        console.print("\n[bold]Saved-search watch stopped.[/bold]")


@jobs.command()
@click.pass_context
def score(ctx):
    """AI-score the most recent search results."""
    init_db()
    settings = load_settings()
    profile = load_profile()

    if not settings.anthropic_api_key:
        console.print(
            "[red]Anthropic API key not configured. Run 'upwork config setup' to set it.[/red]"
        )
        return

    if not profile.title and not profile.skills:
        output.warn(
            "Profile is empty. Run 'upwork config profile' to set up your profile first."
        )
        return

    unscored = get_unscored_jobs(limit=50)

    if not unscored:
        output.empty("No unscored jobs found. Run 'jobs search' first.")
        return

    console.print(
        f"[bold]Scoring {len(unscored)} job(s) against your profile...[/bold]\n"
    )

    results = score_jobs(
        unscored,
        profile.summary(),
        settings.anthropic_api_key,
        model=settings.ai_model,
    )

    table = Table(title="Job Scores", show_lines=True)
    table.add_column("Score", justify="center", width=6)
    table.add_column("Title", style="bold cyan", max_width=50)
    table.add_column("Budget", justify="right")
    table.add_column("Reasoning", max_width=60)

    for result in results:
        if result.score is None:
            score_cell = "[red]—[/red]"
            reasoning = f"[red]{result.error or 'Scoring failed'}[/red]"
        else:
            color = _score_color(result.score)
            score_cell = f"[{color}]{result.score}[/{color}]"
            reasoning = result.reasoning

        table.add_row(
            score_cell,
            output.truncate(result.job.title, 50),
            output.money(result.job.budget_amount, result.job.budget_currency),
            reasoning,
        )

    console.print(table)
    console.print(f"\n[dim]{len(results)} job(s) scored.[/dim]")


@jobs.command()
@click.argument("query")
@click.option("--interval", type=int, default=None, help="Check interval in minutes.")
@click.option(
    "--min-score", type=int, default=None, help="Minimum score threshold for alerts."
)
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
    interval = interval if interval is not None else settings.watch_interval_minutes
    min_score = min_score if min_score is not None else settings.min_score_threshold

    if notify == "discord" and not settings.discord_webhook_url:
        console.print(
            "[red]Discord webhook URL not configured. Run 'upwork config setup' to set it.[/red]"
        )
        return

    has_scoring = bool(settings.anthropic_api_key and (profile.title or profile.skills))
    if not has_scoring:
        output.warn(
            "Scoring disabled: missing API key or profile. New jobs will not be scored."
        )

    profile_summary = profile.summary() if has_scoring else ""
    try:
        client = get_client()
    except NotAuthenticated:
        output.fail("Not authenticated. Run 'upwork config setup' first.")

    console.print(f"[bold]Watching for:[/bold] {query}")
    console.print(
        f"[dim]Interval: {interval}m | Min score: {min_score} | Notify: {notify}[/dim]"
    )
    console.print("[dim]Press Ctrl+C to stop.[/dim]\n")

    try:
        while True:
            _run_search_cycle(
                client,
                settings,
                query=query,
                limit=20,
                min_score=min_score,
                notify=notify,
                has_scoring=has_scoring,
                profile_summary=profile_summary,
                prefix=f"{time.strftime('%H:%M:%S')} -- ",
            )

            time.sleep(interval * 60)

    except KeyboardInterrupt:
        console.print("\n[bold]Watch stopped.[/bold]")


@jobs.command()
@click.argument("job_id")
@click.pass_context
def detail(ctx, job_id):
    """Show full details for a specific job."""
    init_db()
    # Try the API first, but an unauthenticated client is not an error here:
    # the local cache is a legitimate answer.
    try:
        job = jobs_api.get_detail(get_client(), job_id)
    except NotAuthenticated:
        job = None
    except jobs_api.JobsError as exc:
        output.warn(f"{exc}, checking local cache.")
        job = None

    # Fall back to the local DB cache
    if job is None:
        job = get_job(job_id)
        if job is None:
            console.print(f"[red]Job '{job_id}' not found in API or local cache.[/red]")
            return

    # Display full details
    console.print()
    console.rule(f"[bold]{job.title}[/bold]")
    console.print(f"[bold]ID:[/bold] {job.id}")
    console.print(
        f"[bold]Budget:[/bold] {output.money(job.budget_amount, job.budget_currency)}"
    )
    console.print(
        f"[bold]Skills:[/bold] {', '.join(job.skills) if job.skills else 'N/A'}"
    )
    console.print(
        f"[bold]Duration:[/bold] {job.duration or job.duration_label or 'N/A'}"
    )
    console.print(f"[bold]Engagement:[/bold] {job.engagement or 'N/A'}")
    console.print(f"[bold]Posted:[/bold] {job.created_at or 'N/A'}")
    console.print()
    console.print("[bold]Client Info:[/bold]")
    console.print(f"  Country: {job.client_country or 'N/A'}")
    console.print(
        f"  Total Spent: {output.money(job.client_total_spent) if job.client_total_spent else 'N/A'}"
    )
    console.print(
        f"  Total Hires: {job.client_total_hires if job.client_total_hires is not None else 'N/A'}"
    )
    console.print(
        f"  Feedback: {job.client_feedback if job.client_feedback is not None else 'N/A'}"
    )
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
        output.empty("No bookmarks yet. Use 'jobs save <job-id>' to bookmark a job.")
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
            output.truncate(bm.get("title", "") or "N/A", 50),
            output.money(bm.get("budget_amount"), bm.get("budget_currency", "USD")),
            bm.get("note", "") or "",
            bm.get("bookmarked_at", "") or "",
        )

    console.print(table)
    console.print(f"\n[dim]{len(bookmarks)} bookmark(s).[/dim]")
