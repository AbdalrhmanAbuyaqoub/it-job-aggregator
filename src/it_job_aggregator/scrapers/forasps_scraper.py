from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import aiohttp
from pydantic import HttpUrl

from it_job_aggregator.models import Job
from it_job_aggregator.scrapers.base import BaseScraper

if TYPE_CHECKING:
    from it_job_aggregator.db import Database

logger = logging.getLogger(__name__)

DETAIL_REQUEST_DELAY = 0.5  # seconds between detail page requests
REQUEST_TIMEOUT = 30  # seconds

API_BASE_URL = "https://foras.ps/api"
LISTING_ENDPOINT = f"{API_BASE_URL}/v1/Opportunities/filteredJobs"
DETAIL_ENDPOINT = f"{API_BASE_URL}/v1/Opportunities"
JOB_DETAIL_URL_TEMPLATE = "https://foras.ps/jobs/job-details/{job_id}"

# Filter parameters for IT jobs posted in the last month, sorted by date
DEFAULT_FILTER_BODY: dict[str, Any] = {
    "page": 1,
    "datePosted": "pastMonth",
    "orderBy": "date",
    "major": [1],
    "category": 3,
}


class ForasPsScraper(BaseScraper):
    """
    Scrapes IT job postings from Foras.ps (https://foras.ps/opportunities).
    Uses the public REST API directly (no browser automation needed).
    Paginates through listing pages and fetches each job's detail endpoint
    for company name extraction.
    """

    SOURCE_NAME = "Foras.ps"

    async def scrape(
        self,
        db: Database | None = None,
        max_retries: int | None = None,
        initial_backoff: float | None = None,
    ) -> list[Job]:
        """
        Scrape IT jobs from Foras.ps, returning jobs posted in the last month.

        When *db* is provided, already-known job URLs are skipped (no detail
        API call) and pagination stops on the first page where all jobs are
        already known, making subsequent runs significantly faster.
        """
        retries = max_retries if max_retries is not None else self.MAX_RETRIES
        backoff = initial_backoff if initial_backoff is not None else self.INITIAL_BACKOFF

        jobs: list[Job] = []

        async with aiohttp.ClientSession() as session:
            page = 1
            while True:
                logger.info(f"Fetching Foras.ps listing page {page}")

                listing_data = await self._fetch_listing_page(session, page, retries, backoff)
                if listing_data is None:
                    logger.warning(f"Failed to fetch listing page {page}. Stopping pagination.")
                    break

                results = listing_data.get("result", [])
                total_records = listing_data.get("totalRecords", 0)
                return_records = listing_data.get("returnRecords", 0)

                if not results:
                    logger.info(f"No results on page {page}. Stopping pagination.")
                    break

                logger.info(
                    f"Page {page}: {len(results)} jobs "
                    f"(total: {total_records}, returned so far: {return_records})"
                )

                all_known_on_page = True

                for item in results:
                    job_id = item.get("id")
                    if not job_id:
                        logger.warning("Listing item missing 'id', skipping.")
                        all_known_on_page = False
                        continue

                    job_url = JOB_DETAIL_URL_TEMPLATE.format(job_id=job_id)

                    # Incremental scraping: skip already-known URLs
                    if db is not None and db.is_job_known(job_url):
                        logger.info(f"Job already known, skipping: {job_url}")
                        continue

                    all_known_on_page = False

                    # Fetch detail page for company name
                    company = await self._fetch_company_name(session, job_id, retries, backoff)

                    job = self._build_job(item, job_url, company)
                    if job is not None:
                        jobs.append(job)

                    await asyncio.sleep(DETAIL_REQUEST_DELAY)

                # Stop if all jobs on this page were already known
                if db is not None and all_known_on_page:
                    logger.info(f"All jobs on page {page} already known. Stopping pagination.")
                    break

                # Stop if we've fetched all available records
                if return_records >= total_records:
                    logger.info("All available jobs fetched. Stopping pagination.")
                    break

                page += 1

        logger.info(f"Scraped {len(jobs)} jobs from Foras.ps")
        return jobs

    async def _fetch_listing_page(
        self,
        session: aiohttp.ClientSession,
        page: int,
        max_retries: int,
        initial_backoff: float,
    ) -> dict[str, Any] | None:
        """
        Fetch a single page of job listings from the Foras.ps API.
        Returns the parsed JSON response or None on failure.
        """
        body = {**DEFAULT_FILTER_BODY, "page": page}

        async def _attempt() -> dict[str, Any]:
            async with session.post(
                LISTING_ENDPOINT,
                json=body,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as response:
                if response.status >= 400:
                    raise aiohttp.ClientResponseError(
                        response.request_info,
                        response.history,
                        status=response.status,
                        message=f"HTTP {response.status}",
                    )
                data: dict[str, Any] = await response.json()
                return data

        return await self._retry(
            _attempt,
            description=f"listing page {page}",
            max_retries=max_retries,
            initial_backoff=initial_backoff,
        )

    async def _fetch_detail(
        self,
        session: aiohttp.ClientSession,
        job_id: str,
        max_retries: int,
        initial_backoff: float,
    ) -> dict[str, Any] | None:
        """
        Fetch the detail endpoint for a single job.
        Returns the parsed JSON response or None on failure.
        """
        url = f"{DETAIL_ENDPOINT}/{job_id}"

        async def _attempt() -> dict[str, Any]:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as response:
                if response.status >= 400:
                    raise aiohttp.ClientResponseError(
                        response.request_info,
                        response.history,
                        status=response.status,
                        message=f"HTTP {response.status}",
                    )
                data: dict[str, Any] = await response.json()
                return data

        return await self._retry(
            _attempt,
            description=f"detail for {job_id}",
            max_retries=max_retries,
            initial_backoff=initial_backoff,
        )

    async def _fetch_company_name(
        self,
        session: aiohttp.ClientSession,
        job_id: str,
        max_retries: int,
        initial_backoff: float,
    ) -> str | None:
        """
        Fetch the company name for a job from the detail endpoint.
        Returns the English company name, or None if unavailable.
        """
        detail = await self._fetch_detail(session, job_id, max_retries, initial_backoff)
        if detail is None:
            return None

        return self._extract_company_from_detail(detail)

    @staticmethod
    def _extract_company_from_detail(detail: dict[str, Any]) -> str | None:
        """
        Extract the English company name from a detail API response.
        The detail response has a ``companyInfo`` list with entries per language.
        """
        company_info: list[dict[str, Any]] = detail.get("companyInfo", [])
        for entry in company_info:
            if entry.get("language") == "en":
                name: str = entry.get("name", "").strip()
                if name:
                    return name

        # Fallback: try any entry with a name
        for entry in company_info:
            name = str(entry.get("name", "")).strip()
            if name:
                return name

        return None

    def _build_job(
        self,
        item: dict[str, Any],
        job_url: str,
        company: str | None,
    ) -> Job | None:
        """
        Build a Job model from a listing API item and optional company name.
        Returns None if the Job cannot be constructed (e.g. missing required fields).
        """
        title = item.get("nameEnglish") or item.get("nameArabic")
        if not title:
            logger.warning(f"Listing item missing title, skipping: {item.get('id')}")
            return None

        title = str(title).strip()
        location = (item.get("cityNameEnglish") or "").strip() or None
        deadline = (item.get("endDate") or "").strip() or None

        try:
            return Job(
                title=title,
                company=company,
                link=HttpUrl(job_url),
                source=self.SOURCE_NAME,
                location=location,
                deadline=deadline,
            )
        except Exception as e:
            logger.warning(f"Failed to create Job for {job_url}: {e}")
            return None
