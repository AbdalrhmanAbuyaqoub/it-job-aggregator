from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from it_job_aggregator.models import Job

if TYPE_CHECKING:
    from it_job_aggregator.db import Database


class BaseScraper(ABC):
    """
    Abstract base class for all job scrapers.
    """

    @abstractmethod
    async def scrape(self, db: Database | None = None) -> list[Job]:
        """
        Scrape jobs from the target source and return a list of Job objects.

        Args:
            db: Optional database instance for incremental scraping.
                 When provided, scrapers can skip jobs already stored in the
                 database and stop pagination early once known jobs are reached.
        """
        pass
