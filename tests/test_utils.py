from datetime import datetime
from unittest.mock import patch

from it_job_aggregator.utils import parse_job_date


def test_parse_job_date_short_format():
    """Test parsing 'DD, Mon' format uses current year for past months."""
    result = parse_job_date("24, Feb")
    assert result is not None
    assert result.day == 24
    assert result.month == 2


def test_parse_job_date_long_format():
    """Test parsing 'DD, Mon, YYYY' format uses the explicit year."""
    result = parse_job_date("16, Nov, 2025")
    assert result is not None
    assert result.day == 16
    assert result.month == 11
    assert result.year == 2025


def test_parse_job_date_empty_string():
    """Test that an empty string returns None."""
    assert parse_job_date("") is None


def test_parse_job_date_invalid_format():
    """Test that an invalid date string returns None."""
    assert parse_job_date("not a date") is None


def test_parse_job_date_year_boundary_rollback():
    """Test that a future-month date in short format rolls back to the previous year.

    Simulates running in January when parsing a December date — the result
    should be December of the previous year, not December of the current year.
    """
    # Freeze "now" to January 15, 2026
    fake_now = datetime(2026, 1, 15)
    with patch("it_job_aggregator.utils.datetime") as mock_dt:
        mock_dt.now.return_value = fake_now
        mock_dt.strptime = datetime.strptime
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        result = parse_job_date("15, Dec")

    assert result is not None
    assert result.year == 2025
    assert result.month == 12
    assert result.day == 15


def test_parse_job_date_year_boundary_no_rollback():
    """Test that a past-month date in short format stays in the current year.

    Simulates running in June when parsing a February date — the result
    should be February of the current year.
    """
    fake_now = datetime(2026, 6, 15)
    with patch("it_job_aggregator.utils.datetime") as mock_dt:
        mock_dt.now.return_value = fake_now
        mock_dt.strptime = datetime.strptime
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        result = parse_job_date("10, Feb")

    assert result is not None
    assert result.year == 2026
    assert result.month == 2
    assert result.day == 10


def test_parse_job_date_explicit_year_not_affected_by_boundary():
    """Test that explicit-year dates are never modified by year-boundary logic."""
    # Dec 2025 is in the past relative to any 2026 date, but the year is explicit
    result = parse_job_date("15, Dec, 2027")
    assert result is not None
    assert result.year == 2027
    assert result.month == 12
    assert result.day == 15


def test_parse_job_date_single_digit_day():
    """Test parsing a single-digit day like '5, Jan'."""
    result = parse_job_date("5, Jan")
    assert result is not None
    assert result.day == 5
    assert result.month == 1
