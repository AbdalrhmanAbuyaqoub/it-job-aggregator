from abc import ABC, abstractmethod

from it_job_aggregator.models import Job


class BaseScraper(ABC):
    """
    Abstract base class for all job scrapers.
    """

    @abstractmethod
    async def scrape(self) -> list[Job]:
        """
        Scrape jobs from the target source and return a list of Job objects.
        """
        pass
