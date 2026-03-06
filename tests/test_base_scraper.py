from unittest.mock import AsyncMock, patch

import pytest

from it_job_aggregator.models import Job
from it_job_aggregator.scrapers.base import BaseScraper


class _StubScraper(BaseScraper):
    """Minimal concrete subclass used to test ``BaseScraper._retry()``."""

    SOURCE_NAME = "Stub"

    async def scrape(
        self,
        db=None,
        max_retries: int | None = None,
        initial_backoff: float | None = None,
    ) -> list[Job]:
        return []


@pytest.fixture
def scraper() -> _StubScraper:
    """Return a fresh ``_StubScraper`` instance."""
    return _StubScraper()


# ---------------------------------------------------------------------------
# Success on first attempt
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_success_on_first_attempt(scraper: _StubScraper):
    """Return the value immediately when the operation succeeds on the first call."""
    operation = AsyncMock(return_value="ok")

    result = await scraper._retry(operation, "test op")

    assert result == "ok"
    operation.assert_awaited_once()


# ---------------------------------------------------------------------------
# Success after transient failures
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_success_after_transient_failures(scraper: _StubScraper):
    """Return the value when the operation fails then succeeds within the retry budget."""
    operation = AsyncMock(side_effect=[Exception("fail"), Exception("fail"), "ok"])

    with patch("it_job_aggregator.scrapers.base.asyncio.sleep", new_callable=AsyncMock):
        result = await scraper._retry(operation, "test op", max_retries=3)

    assert result == "ok"
    assert operation.await_count == 3


# ---------------------------------------------------------------------------
# All retries exhausted → returns None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_returns_none_after_exhausting_retries(scraper: _StubScraper):
    """Return None when the operation fails on every attempt."""
    operation = AsyncMock(side_effect=Exception("boom"))

    with patch("it_job_aggregator.scrapers.base.asyncio.sleep", new_callable=AsyncMock):
        result = await scraper._retry(operation, "test op", max_retries=3)

    assert result is None
    assert operation.await_count == 3


# ---------------------------------------------------------------------------
# Exponential backoff timing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_exponential_backoff(scraper: _StubScraper):
    """Sleep with exponential backoff between failed attempts."""
    operation = AsyncMock(side_effect=[Exception("1"), Exception("2"), Exception("3"), "ok"])

    with patch(
        "it_job_aggregator.scrapers.base.asyncio.sleep", new_callable=AsyncMock
    ) as mock_sleep:
        result = await scraper._retry(operation, "test op", max_retries=4, initial_backoff=2)

    assert result == "ok"
    assert mock_sleep.await_count == 3
    # backoff sequence: 2*2^0=2, 2*2^1=4, 2*2^2=8
    mock_sleep.assert_any_await(2)
    mock_sleep.assert_any_await(4)
    mock_sleep.assert_any_await(8)


@pytest.mark.asyncio
async def test_retry_no_sleep_on_final_failure(scraper: _StubScraper):
    """Do not sleep after the last failed attempt (no pending retry)."""
    operation = AsyncMock(side_effect=Exception("err"))

    with patch(
        "it_job_aggregator.scrapers.base.asyncio.sleep", new_callable=AsyncMock
    ) as mock_sleep:
        await scraper._retry(operation, "test op", max_retries=2, initial_backoff=1)

    # 2 attempts, sleep only after attempt 1 (not after the final attempt 2)
    assert mock_sleep.await_count == 1
    mock_sleep.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_retry_no_sleep_on_first_attempt_success(scraper: _StubScraper):
    """Never sleep when the operation succeeds on the first attempt."""
    operation = AsyncMock(return_value="ok")

    with patch(
        "it_job_aggregator.scrapers.base.asyncio.sleep", new_callable=AsyncMock
    ) as mock_sleep:
        await scraper._retry(operation, "test op")

    mock_sleep.assert_not_awaited()


# ---------------------------------------------------------------------------
# Class-level defaults when None is passed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_uses_class_defaults_when_none(scraper: _StubScraper):
    """Fall back to MAX_RETRIES and INITIAL_BACKOFF when None is passed."""
    # Class defaults: MAX_RETRIES=3, INITIAL_BACKOFF=2
    operation = AsyncMock(side_effect=Exception("err"))

    with patch(
        "it_job_aggregator.scrapers.base.asyncio.sleep", new_callable=AsyncMock
    ) as mock_sleep:
        result = await scraper._retry(operation, "test op", max_retries=None, initial_backoff=None)

    assert result is None
    # Should have tried 3 times (class default MAX_RETRIES=3)
    assert operation.await_count == 3
    # Should have slept 2 times (no sleep after final failure)
    assert mock_sleep.await_count == 2
    # Backoff: 2*2^0=2, 2*2^1=4  (class default INITIAL_BACKOFF=2)
    mock_sleep.assert_any_await(2)
    mock_sleep.assert_any_await(4)


# ---------------------------------------------------------------------------
# Custom overrides beat class defaults
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_custom_overrides(scraper: _StubScraper):
    """Custom max_retries and initial_backoff override class-level defaults."""
    operation = AsyncMock(side_effect=Exception("err"))

    with patch(
        "it_job_aggregator.scrapers.base.asyncio.sleep", new_callable=AsyncMock
    ) as mock_sleep:
        result = await scraper._retry(operation, "test op", max_retries=5, initial_backoff=0.5)

    assert result is None
    assert operation.await_count == 5
    # 4 sleeps (no sleep after last failure)
    assert mock_sleep.await_count == 4
    # Backoff: 0.5, 1.0, 2.0, 4.0
    mock_sleep.assert_any_await(0.5)
    mock_sleep.assert_any_await(1.0)
    mock_sleep.assert_any_await(2.0)
    mock_sleep.assert_any_await(4.0)


# ---------------------------------------------------------------------------
# Single-attempt edge case (max_retries=1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_single_attempt_success(scraper: _StubScraper):
    """With max_retries=1, a successful call returns the value with no sleep."""
    operation = AsyncMock(return_value=42)

    with patch(
        "it_job_aggregator.scrapers.base.asyncio.sleep", new_callable=AsyncMock
    ) as mock_sleep:
        result = await scraper._retry(operation, "test op", max_retries=1)

    assert result == 42
    mock_sleep.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_single_attempt_failure(scraper: _StubScraper):
    """With max_retries=1, a failed call returns None immediately with no sleep."""
    operation = AsyncMock(side_effect=Exception("err"))

    with patch(
        "it_job_aggregator.scrapers.base.asyncio.sleep", new_callable=AsyncMock
    ) as mock_sleep:
        result = await scraper._retry(operation, "test op", max_retries=1)

    assert result is None
    operation.assert_awaited_once()
    mock_sleep.assert_not_awaited()


# ---------------------------------------------------------------------------
# Return type preservation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_preserves_return_type(scraper: _StubScraper):
    """The return value from the operation is passed through unchanged."""
    expected = {"jobs": [1, 2, 3], "page": 1}
    operation = AsyncMock(return_value=expected)

    result = await scraper._retry(operation, "test op")

    assert result is expected


# ---------------------------------------------------------------------------
# Subclass with custom class-level defaults
# ---------------------------------------------------------------------------


class _CustomDefaultsScraper(BaseScraper):
    """Subclass with non-standard retry defaults."""

    SOURCE_NAME = "Custom"
    MAX_RETRIES = 5
    INITIAL_BACKOFF = 0.1

    async def scrape(
        self,
        db=None,
        max_retries: int | None = None,
        initial_backoff: float | None = None,
    ) -> list[Job]:
        return []


@pytest.mark.asyncio
async def test_retry_respects_subclass_defaults():
    """_retry() uses the subclass MAX_RETRIES and INITIAL_BACKOFF, not BaseScraper's."""
    scraper = _CustomDefaultsScraper()
    operation = AsyncMock(side_effect=Exception("err"))

    with patch(
        "it_job_aggregator.scrapers.base.asyncio.sleep", new_callable=AsyncMock
    ) as mock_sleep:
        result = await scraper._retry(operation, "test op")

    assert result is None
    # Subclass MAX_RETRIES=5
    assert operation.await_count == 5
    # 4 sleeps; initial_backoff=0.1 → 0.1, 0.2, 0.4, 0.8
    assert mock_sleep.await_count == 4
    mock_sleep.assert_any_await(0.1)
    mock_sleep.assert_any_await(0.2)
    mock_sleep.assert_any_await(pytest.approx(0.4))
    mock_sleep.assert_any_await(pytest.approx(0.8))
