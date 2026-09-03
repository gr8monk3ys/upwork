"""Click command group for job search, scoring, watching, and bookmarking."""

import json
import time
import urllib.request
from datetime import datetime, timedelta, timezone

import click
from rich.console import Console
from rich.table import Table

from upwork_cli.ai.scorer import score_jobs_batch
from upwork_cli.client import UpworkClient
from upwork_cli.config import load_profile, load_settings, save_settings
from upwork_cli.db import (
    get_bookmarks,
    get_jobs_with_scores,
    init_db,
    is_seen,
    mark_seen,
    save_bookmark,
    save_score,
    set_pipeline_stage_if_not_exists,
    upsert_job,
)
from upwork_cli.models import JobPosting

console = Console()


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
        console.print(f"[red]API search failed: {exc}[/red]")
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
            _truncate(job.title, 50),
            _format_budget(job.budget_amount, job.budget_currency),
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
    new_jobs = []
    for job in results:
        if is_seen(job.id):
            continue
        new_jobs.append(job)
        mark_seen(job.id, search_term)
        upsert_job(job.to_db_dict())
        set_pipeline_stage_if_not_exists(job.id, "found")
    return new_jobs


def _score_alert_jobs(
    new_jobs: list[JobPosting],
    min_score: int,
    has_scoring: bool,
    profile_summary: str,
    api_key: str,
    model: str = "",
) -> list[dict]:
    """Score new jobs when possible and return only alert-worthy items."""
    if not has_scoring:
        return [{"id": job.id, "title": job.title, "score": "?"} for job in new_jobs]

    batch = [
        {
            "id": job.id,
            "title": job.title,
            "summary": job.summary_for_ai(),
        }
        for job in new_jobs
    ]
    scored = score_jobs_batch(batch, profile_summary, api_key, model=model or None)
    # Failed scores (score=None) stay unsaved so the job is re-scored next cycle
    # instead of being permanently buried at 0.
    for item in scored:
        if item["score"] is not None:
            save_score(item["id"], item["score"], item.get("reasoning", ""))
    return [
        item
        for item in scored
        if item["score"] is not None and item["score"] >= min_score
    ]


def _notify_hot_jobs(hot_jobs: list[dict], notify: str, webhook_url: str) -> None:
    """Emit terminal or Discord alerts for high-priority jobs."""
    for item in hot_jobs:
        title = item.get("title", "Untitled")
        score = item.get("score", "?")
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
    settings = load_settings()
    client = UpworkClient(settings=settings)

    console.print(f"[bold]Searching for:[/bold] {query}")

    if not client.is_authenticated:
        console.print("[red]Not authenticated. Run 'upwork config setup' first.[/red]")
        return

    results = _search_via_api(client, query, limit)

    results = _filter_jobs(results, budget_min, budget_max, job_type, posted)

    if not results:
        console.print("[yellow]No jobs found matching your query.[/yellow]")
        return

    # Cache results in the database and add to pipeline
    for job in results:
        upsert_job(job.to_db_dict())
        set_pipeline_stage_if_not_exists(job.id, "found")

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
        console.print("[yellow]No saved search terms yet.[/yellow]")
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
        console.print(f"[yellow]Saved search already exists:[/yellow] {term}")
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
        console.print("[yellow]No saved search terms configured.[/yellow]")
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
        console.print(
            "[yellow]Scoring disabled: missing API key or profile. New jobs will not be scored.[/yellow]"
        )

    profile_summary = profile.summary() if has_scoring else ""
    client = UpworkClient(settings=settings)
    if not client.is_authenticated:
        console.print("[red]Not authenticated. Run 'upwork config setup' first.[/red]")
        raise SystemExit(1)

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
        console.print("[yellow]No new jobs found across saved searches.[/yellow]")
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
        console.print(
            "[yellow]Profile is empty. Run 'upwork config profile' to set up your profile first.[/yellow]"
        )
        return

    cached_jobs = get_jobs_with_scores(limit=50)
    # Filter to jobs that have not been scored yet
    unscored = [j for j in cached_jobs if j.get("score") is None]

    if not unscored:
        console.print(
            "[yellow]No unscored jobs found. Run 'jobs search' first.[/yellow]"
        )
        return

    console.print(
        f"[bold]Scoring {len(unscored)} job(s) against your profile...[/bold]\n"
    )

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
            client_verified=bool(row.get("client_verified")),
            created_at=row.get("created_at", ""),
        )
        batch.append(
            {
                "id": job_obj.id,
                "title": job_obj.title,
                "summary": job_obj.summary_for_ai(),
            }
        )

    scored = score_jobs_batch(
        batch, profile_summary, settings.anthropic_api_key, model=settings.ai_model
    )

    # Save scores to the database; failed jobs (score=None) stay unscored so
    # the next run retries them instead of caching a bogus 0.
    for item in scored:
        if item["score"] is not None:
            save_score(item["id"], item["score"], item.get("reasoning", ""))

    # Display scored results
    table = Table(title="Job Scores", show_lines=True)
    table.add_column("Score", justify="center", width=6)
    table.add_column("Title", style="bold cyan", max_width=50)
    table.add_column("Budget", justify="right")
    table.add_column("Reasoning", max_width=60)

    for item in scored:
        sc = item["score"]
        # Look up budget from the original row
        original = next((r for r in unscored if r["id"] == item["id"]), {})
        budget = _format_budget(
            original.get("budget_amount"), original.get("budget_currency", "USD")
        )

        if sc is None:
            score_cell = "[red]—[/red]"
            reasoning = f"[red]{item.get('error', 'Scoring failed')}[/red]"
        else:
            color = _score_color(sc)
            score_cell = f"[{color}]{sc}[/{color}]"
            reasoning = item.get("reasoning", "")

        table.add_row(
            score_cell,
            _truncate(item.get("title", ""), 50),
            budget,
            reasoning,
        )

    console.print(table)
    console.print(f"\n[dim]{len(scored)} job(s) scored.[/dim]")


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
        console.print(
            "[yellow]Scoring disabled: missing API key or profile. New jobs will not be scored.[/yellow]"
        )

    profile_summary = profile.summary() if has_scoring else ""
    client = UpworkClient(settings=settings)

    if not client.is_authenticated:
        console.print("[red]Not authenticated. Run 'upwork config setup' first.[/red]")
        return

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
    settings = load_settings()
    client = UpworkClient(settings=settings)

    # Try the API first if authenticated
    if client.is_authenticated:
        try:
            data = client.get_job_detail(job_id)
            job = JobPosting.from_rest(data) if data else None
        except Exception as exc:
            console.print(
                f"[yellow]API lookup failed ({exc}), checking local cache.[/yellow]"
            )
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
            client_verified=bool(match.get("client_verified")),
            created_at=match.get("created_at", ""),
        )

    # Display full details
    console.print()
    console.rule(f"[bold]{job.title}[/bold]")
    console.print(f"[bold]ID:[/bold] {job.id}")
    console.print(
        f"[bold]Budget:[/bold] {_format_budget(job.budget_amount, job.budget_currency)}"
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
        f"  Total Spent: {_format_budget(job.client_total_spent) if job.client_total_spent else 'N/A'}"
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
        console.print(
            "[yellow]No bookmarks yet. Use 'jobs save <job-id>' to bookmark a job.[/yellow]"
        )
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
