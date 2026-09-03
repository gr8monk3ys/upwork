"""Fetching and summarising Upwork earnings.

Sits between the commands and ``UpworkClient``: the client returns a report
payload whose shape varies, and this module turns it into EarningRows and
totals. Failures are raised, not printed.
"""

from datetime import datetime, timedelta
from typing import Any

from upwork_cli.client import UpworkClient
from upwork_cli.models import EarningRow, EarningsSummary


class EarningsError(RuntimeError):
    """Raised when the Upwork API cannot answer an earnings request."""


def _freelancer_ref(client: UpworkClient) -> str:
    """The account's freelancer reference, which the earnings report needs."""
    try:
        info = client.get_user_info()
    except Exception as exc:
        raise EarningsError(f"Failed to get user info: {exc}") from exc

    ref = info.get("info", {}).get("ref", "") or info.get("ref", info.get("id", ""))
    if not ref:
        raise EarningsError("Could not determine your freelancer reference.")
    return str(ref)


def _date_query(from_date: str | None, to_date: str | None) -> dict[str, Any] | None:
    """Build the report's date filter, or None when unfiltered."""
    clauses = []
    if from_date:
        clauses.append(f"date >= '{from_date}'")
    if to_date:
        clauses.append(f"date <= '{to_date}'")
    return {"tq": " AND ".join(clauses)} if clauses else None


def _rows_in(payload: dict[str, Any]) -> list[Any]:
    """The report rows, wherever this payload happens to keep them."""
    table = payload.get("table") or {}
    return (
        (table.get("rows") if isinstance(table, dict) else None)
        or payload.get("rows")
        or payload.get("earnings")
        or []
    )


def column_names(payload: dict[str, Any]) -> list[str]:
    """Report column headings, falling back to the standard five."""
    table = payload.get("table") or {}
    columns = (
        (table.get("cols") if isinstance(table, dict) else None)
        or payload.get("cols")
        or []
    )
    names = [
        str(c.get("label", c.get("name", f"Col {i}")))
        for i, c in enumerate(columns)
        if isinstance(c, dict)
    ]
    return names or list(EarningRow.COLUMNS)


def fetch(
    client: UpworkClient,
    from_date: str | None = None,
    to_date: str | None = None,
) -> tuple[list[EarningRow], dict[str, Any]]:
    """Earnings rows for the period, with the raw payload for its headings.

    The payload comes back alongside the rows only so a caller can render
    the report's own column labels; nothing else should read it.
    """
    ref = _freelancer_ref(client)
    try:
        payload = client.get_earnings(ref, _date_query(from_date, to_date))
    except Exception as exc:
        raise EarningsError(f"Failed to fetch earnings: {exc}") from exc

    payload = payload or {}
    return [EarningRow.from_api(row) for row in _rows_in(payload)], payload


def summarise(rows: list[EarningRow], now: datetime | None = None) -> EarningsSummary:
    """Total the rows, and the subsets falling in this month and this week.

    ``now`` is a parameter so the period boundaries can be tested without
    freezing the clock. Dates are compared naively: Upwork's rows carry
    bare dates with no zone, and month and week should follow the user's
    own calendar.
    """
    now = now or datetime.now()  # noqa: DTZ005 - see docstring
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    week_start = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    summary = EarningsSummary()
    for row in rows:
        summary.total += row.amount
        when = _parse_date(row.date)
        if when is None:
            continue
        if when >= month_start:
            summary.this_month += row.amount
        if when >= week_start:
            summary.this_week += row.amount
    return summary


def _parse_date(value: str) -> datetime | None:
    """Parse a report date, which arrives in any of several formats."""
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(value[:10], fmt)  # noqa: DTZ007 - see summarise
        except (ValueError, TypeError):
            continue
    return None
