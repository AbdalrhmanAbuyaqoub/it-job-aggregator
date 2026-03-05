"""Shared utility functions for the IT Job Aggregator package."""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def parse_job_date(date_str: str) -> datetime | None:
    """
    Parse a date string from jobs.ps into a datetime.

    Formats:
        - ``"24, Feb"`` — day + abbreviated month, current year assumed.
        - ``"16, Nov, 2025"`` — day + abbreviated month + explicit year.

    Year-boundary handling: when only day and month are given and the
    resulting date is in the future (e.g. parsing ``"15, Dec"`` in January),
    the year is rolled back by one so the date is treated as last December.

    Returns:
        A ``datetime`` on success, or ``None`` if *date_str* is empty or
        cannot be parsed.
    """
    if not date_str:
        return None

    parts = [p.strip() for p in date_str.split(",")]
    try:
        if len(parts) == 3:
            # "16, Nov, 2025" -> day, month, year
            return datetime.strptime(f"{parts[0]} {parts[1]} {parts[2]}", "%d %b %Y")
        elif len(parts) == 2:
            # "24, Feb" -> day, month (current year)
            now = datetime.now()
            parsed = datetime.strptime(f"{parts[0]} {parts[1]} {now.year}", "%d %b %Y")
            # If the date is in the future, it's from last year
            if parsed > now:
                parsed = parsed.replace(year=now.year - 1)
            return parsed
    except ValueError as e:
        logger.debug(f"Failed to parse date '{date_str}': {e}")

    return None
