"""Reading the timestamps this tool receives.

Upwork's API and SQLite spell a moment differently, and two modules had
grown their own parser for the overlap -- the pipeline's copy simply lacked
the two formats the jobs copy had learned.

Everything here returns UTC-aware datetimes. The earnings report keeps its
own naive parser on purpose; see ``earnings.summarise``.
"""

from datetime import datetime, timezone

#: Formats `datetime.fromisoformat` will not take.
_FALLBACK_FORMATS = ("%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%d")


def parse(value: str) -> datetime | None:
    """One timestamp as a UTC-aware datetime, or None if it is unreadable.

    Accepts ISO-8601 with or without a zone, the ``Z`` suffix, SQLite's
    space-separated form, and RFC-822. A value with no zone is read as UTC,
    which is what every source here means by it.
    """
    if not value:
        return None

    text = value.strip()
    candidates = [text]
    if text.endswith("Z"):
        candidates.append(text[:-1] + "+00:00")
    if " " in text and "T" not in text:
        candidates.append(text.replace(" ", "T", 1))

    for candidate in candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    for fmt in _FALLBACK_FORMATS:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    return None
