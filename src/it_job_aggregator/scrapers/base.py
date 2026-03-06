from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, ClassVar, TypeVar

from it_job_aggregator.models import Job

if TYPE_CHECKING:
    from it_job_aggregator.db import Database

logger = logging.getLogger(__name__)

T = TypeVar("T")


class BaseScraper(ABC):
    """
    Abstract base class for all job scrapers.

    Subclasses **must** define a ``SOURCE_NAME`` class variable and implement
    :meth:`scrape`.  The shared :meth:`_retry` helper provides exponential-
    backoff retry logic so individual scrapers don't duplicate that pattern.
    """

    SOURCE_NAME: ClassVar[str]
    """Human-readable name of the job source (e.g. ``"Jobs.ps"``)."""

    MAX_RETRIES: ClassVar[int] = 3
    """Default maximum number of attempts for retryable operations."""

    INITIAL_BACKOFF: ClassVar[float] = 2
    """Default initial backoff in seconds (doubles each retry)."""

    @abstractmethod
    async def scrape(
        self,
        db: Database | None = None,
        max_retries: int | None = None,
        initial_backoff: float | None = None,
    ) -> list[Job]:
        """
        Scrape jobs from the target source and return a list of Job objects.

        Args:
            db: Optional database instance for incremental scraping.
                 When provided, scrapers can skip jobs already stored in the
                 database and stop pagination early once known jobs are reached.
            max_retries: Override the class-level ``MAX_RETRIES`` default.
            initial_backoff: Override the class-level ``INITIAL_BACKOFF`` default.
        """
        pass

    async def _retry(
        self,
        operation: Callable[[], Awaitable[T]],
        description: str,
        max_retries: int | None = None,
        initial_backoff: float | None = None,
    ) -> T | None:
        """
        Execute *operation* with exponential-backoff retry.

        Args:
            operation: An async callable (no arguments) that performs the I/O.
                       It should raise on failure and return a value on success.
            description: Human-readable label used in log messages
                         (e.g. ``"listing page 2"``).
            max_retries: Number of attempts.  Falls back to ``self.MAX_RETRIES``.
            initial_backoff: Starting backoff in seconds.  Falls back to
                             ``self.INITIAL_BACKOFF``.

        Returns:
            The value returned by *operation*, or ``None`` if all attempts fail.
        """
        retries = max_retries if max_retries is not None else self.MAX_RETRIES
        backoff_base = initial_backoff if initial_backoff is not None else self.INITIAL_BACKOFF

        for attempt in range(1, retries + 1):
            try:
                return await operation()
            except Exception as e:
                if attempt == retries:
                    logger.error(f"Failed after {retries} attempts for {description}: {e}")
                else:
                    backoff = backoff_base * (2 ** (attempt - 1))
                    logger.warning(
                        f"{description} attempt {attempt}/{retries} failed: {e}. "
                        f"Retrying in {backoff}s..."
                    )
                    await asyncio.sleep(backoff)

        return None
