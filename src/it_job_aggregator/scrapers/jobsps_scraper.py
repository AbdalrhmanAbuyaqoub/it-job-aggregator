import asyncio
import json
import logging
from datetime import datetime, timedelta

from bs4 import BeautifulSoup, Tag
from playwright.async_api import Page, async_playwright
from playwright_stealth import Stealth
from pydantic import HttpUrl

from it_job_aggregator.models import Job
from it_job_aggregator.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
INITIAL_BACKOFF = 2  # seconds
PAGE_TIMEOUT = 60000  # milliseconds — generous for Cloudflare challenge
DETAIL_REQUEST_DELAY = 1.0  # seconds between detail page requests
MAX_AGE_DAYS = 30


class JobsPsScraper(BaseScraper):
    """
    Scrapes IT job postings from jobs.ps (https://www.jobs.ps/en/categories/it-jobs).
    Uses Playwright with stealth to bypass Cloudflare protection.
    Paginates through listing pages, filters by date (last 30 days),
    and fetches each job's detail page for metadata extraction.
    """

    BASE_URL = "https://www.jobs.ps/en/categories/it-jobs"
    SOURCE_NAME = "Jobs.ps"

    async def scrape(
        self,
        max_retries: int = MAX_RETRIES,
        initial_backoff: float = INITIAL_BACKOFF,
    ) -> list[Job]:
        """Scrape IT jobs from jobs.ps, returning jobs posted in the last 30 days."""
        jobs: list[Job] = []
        cutoff_date = datetime.now() - timedelta(days=MAX_AGE_DAYS)

        async with Stealth().use_async(async_playwright()) as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
            )
            page = await context.new_page()

            try:
                total_pages = await self._get_total_pages(page, max_retries, initial_backoff)
                logger.info(f"Found {total_pages} pages of job listings on jobs.ps")

                for page_num in range(1, total_pages + 1):
                    logger.info(f"Scraping listing page {page_num}/{total_pages}")
                    listing_jobs, has_old_jobs = await self._scrape_listing_page(
                        page, page_num, cutoff_date, max_retries, initial_backoff
                    )

                    for listing in listing_jobs:
                        detail_job = await self._scrape_detail_page(
                            page, listing, max_retries, initial_backoff
                        )
                        if detail_job:
                            jobs.append(detail_job)
                        await asyncio.sleep(DETAIL_REQUEST_DELAY)

                    if has_old_jobs:
                        logger.info(
                            f"Reached jobs older than {MAX_AGE_DAYS} days on page {page_num}. "
                            f"Stopping pagination."
                        )
                        break
            finally:
                await context.close()
                await browser.close()

        logger.info(f"Scraped {len(jobs)} jobs from jobs.ps (last {MAX_AGE_DAYS} days)")
        return jobs

    async def _get_total_pages(
        self,
        page: Page,
        max_retries: int,
        initial_backoff: float,
    ) -> int:
        """Fetch the first listing page and determine total number of pages."""
        html = await self._fetch_page(page, self.BASE_URL, max_retries, initial_backoff)
        if not html:
            return 0

        soup = BeautifulSoup(html, "html.parser")
        last_link = soup.select_one("ul.pagination li:last-child a")
        if last_link and last_link.get("href"):
            href = str(last_link["href"])
            if "page=" in href:
                try:
                    return int(href.split("page=")[-1])
                except ValueError:
                    pass
        return 1

    async def _scrape_listing_page(
        self,
        page: Page,
        page_num: int,
        cutoff_date: datetime,
        max_retries: int,
        initial_backoff: float,
    ) -> tuple[list[dict[str, str]], bool]:
        """
        Scrape a single listing page and return job metadata dicts
        along with a flag indicating whether we hit jobs older than the cutoff.

        Returns:
            A tuple of (list of job dicts, has_old_jobs).
            Each dict has keys: title, company, link, location, date_str.
        """
        url = self.BASE_URL if page_num == 1 else f"{self.BASE_URL}?page={page_num}"
        html = await self._fetch_page(page, url, max_retries, initial_backoff)
        if not html:
            return [], False

        soup = BeautifulSoup(html, "html.parser")
        rows = soup.select("div.list-3--body a.list-3--row")

        listing_jobs: list[dict[str, str]] = []
        has_old_jobs = False

        for row in rows:
            parsed = self._parse_listing_row(row)
            if not parsed:
                continue

            posted_date = self._parse_listing_date(parsed["date_str"])
            if posted_date and posted_date < cutoff_date:
                has_old_jobs = True
                continue

            listing_jobs.append(parsed)

        return listing_jobs, has_old_jobs

    async def _scrape_detail_page(
        self,
        page: Page,
        listing: dict[str, str],
        max_retries: int,
        initial_backoff: float,
    ) -> Job | None:
        """Fetch a job detail page and extract full metadata into a Job object."""
        url = listing["link"]
        html = await self._fetch_page(page, url, max_retries, initial_backoff)
        if not html:
            logger.warning(f"Failed to fetch detail page: {url}")
            return self._job_from_listing(listing)

        soup = BeautifulSoup(html, "html.parser")
        details = self._extract_detail_metadata(soup)

        try:
            return Job(
                title=listing["title"],
                company=listing.get("company") or None,
                link=HttpUrl(listing["link"]),
                description=listing["title"],
                source=self.SOURCE_NAME,
                position_level=details.get("position_level"),
                location=details.get("location") or listing.get("location"),
                deadline=details.get("deadline"),
                experience=details.get("experience"),
                posted_date=listing.get("date_str") or None,
            )
        except Exception as e:
            logger.warning(f"Failed to create Job from detail page {url}: {e}")
            return self._job_from_listing(listing)

    def _job_from_listing(self, listing: dict[str, str]) -> Job | None:
        """Create a Job from listing-page data only (fallback when detail page fails)."""
        try:
            return Job(
                title=listing["title"],
                company=listing.get("company") or None,
                link=HttpUrl(listing["link"]),
                description=listing["title"],
                source=self.SOURCE_NAME,
                location=listing.get("location"),
                posted_date=listing.get("date_str") or None,
            )
        except Exception as e:
            logger.warning(f"Failed to create Job from listing data: {e}")
            return None

    def _parse_listing_row(self, row: Tag) -> dict[str, str] | None:
        """Parse a single job row from the listing page into a dict."""
        title = row.get("title")
        href = row.get("href")
        if not title or not href:
            return None

        title = str(title).strip()
        href = str(href).strip()

        company_el = row.select_one("div.list--cell--company")
        company = company_el.get_text(strip=True) if company_el else ""

        location_el = row.select_one("span.tooltip")
        location = str(location_el.get("title", "")) if location_el else ""
        if not location and location_el:
            location = location_el.get_text(strip=True)

        date_el = row.select_one("div.list-3--cell-4")
        date_str = date_el.get_text(strip=True) if date_el else ""

        return {
            "title": title,
            "company": company,
            "link": href,
            "location": location,
            "date_str": date_str,
        }

    def _extract_detail_metadata(self, soup: BeautifulSoup) -> dict[str, str]:
        """
        Extract job metadata from a detail page.
        Uses JSON-LD structured data where available, falls back to HTML parsing.
        """
        details: dict[str, str] = {}

        # Try JSON-LD first for deadline and experience
        ld_script = soup.find("script", type="application/ld+json")
        if isinstance(ld_script, Tag) and ld_script.string:
            try:
                ld_data = json.loads(ld_script.string)
                if ld_data.get("validThrough"):
                    details["deadline"] = ld_data["validThrough"]
                if ld_data.get("experienceRequirements"):
                    details["experience"] = ld_data["experienceRequirements"]
                # Location from JSON-LD
                job_locations = ld_data.get("jobLocation", [])
                if job_locations and isinstance(job_locations, list):
                    address = job_locations[0].get("address", {})
                    locality = address.get("addressLocality", "")
                    if locality:
                        details["location"] = locality
            except (json.JSONDecodeError, KeyError, IndexError) as e:
                logger.debug(f"Failed to parse JSON-LD: {e}")

        # Parse HTML detail items for position_level (not in JSON-LD)
        # and as fallback for other fields
        html_details = self._parse_html_detail_items(soup)

        if "position_level" not in details and "Position Level" in html_details:
            details["position_level"] = html_details["Position Level"]

        if "location" not in details and "Location" in html_details:
            details["location"] = html_details["Location"]

        if "deadline" not in details and "Deadline" in html_details:
            details["deadline"] = html_details["Deadline"]

        if "experience" not in details and "Experience" in html_details:
            details["experience"] = html_details["Experience"]

        return details

    def _parse_html_detail_items(self, soup: BeautifulSoup) -> dict[str, str]:
        """Parse key-value pairs from the detail page's metadata box."""
        result: dict[str, str] = {}
        items = soup.select("div.view--detail-custom div.view--detail-item")
        for item in items:
            spans = item.find_all("span", recursive=False)
            if len(spans) >= 2:
                label = spans[0].get_text(strip=True)
                value = spans[1].get_text(strip=True)
                if label and value:
                    result[label] = value
        return result

    @staticmethod
    def _parse_listing_date(date_str: str) -> datetime | None:
        """
        Parse a date string from the listing page.
        Formats: "24, Feb" (current year) or "16, Nov, 2025" (explicit year).
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
                current_year = datetime.now().year
                return datetime.strptime(f"{parts[0]} {parts[1]} {current_year}", "%d %b %Y")
        except ValueError as e:
            logger.debug(f"Failed to parse date '{date_str}': {e}")

        return None

    async def _fetch_page(
        self,
        page: Page,
        url: str,
        max_retries: int,
        initial_backoff: float,
    ) -> str | None:
        """
        Navigate to a URL with retry logic, waiting for Cloudflare challenge
        to resolve. Returns the page HTML content or None on failure.
        """
        for attempt in range(1, max_retries + 1):
            try:
                response = await page.goto(url, timeout=PAGE_TIMEOUT, wait_until="domcontentloaded")

                # Wait for Cloudflare challenge to resolve if present
                await self._wait_for_cloudflare(page)

                if response and response.status >= 400:
                    raise Exception(f"HTTP {response.status} for {url}")

                return await page.content()
            except Exception as e:
                if attempt == max_retries:
                    logger.error(f"Failed after {max_retries} attempts fetching {url}: {e}")
                else:
                    backoff = initial_backoff * (2 ** (attempt - 1))
                    logger.warning(
                        f"Fetch attempt {attempt}/{max_retries} failed for {url}: {e}. "
                        f"Retrying in {backoff}s..."
                    )
                    await asyncio.sleep(backoff)

        return None

    @staticmethod
    async def _wait_for_cloudflare(page: Page, timeout: int = 30000) -> None:
        """
        Wait for Cloudflare challenge page to resolve.
        Detects the "Just a moment..." challenge page and waits for it to pass.
        """
        try:
            # Check if we're on a Cloudflare challenge page
            title = await page.title()
            if "just a moment" in title.lower():
                logger.info("Cloudflare challenge detected, waiting for resolution...")
                # Wait until the title changes (challenge resolved)
                await page.wait_for_function(
                    "() => !document.title.toLowerCase().includes('just a moment')",
                    timeout=timeout,
                )
                # Give the page a moment to fully load after challenge
                await page.wait_for_load_state("domcontentloaded")
                logger.info("Cloudflare challenge resolved.")
        except Exception as e:
            logger.warning(f"Cloudflare wait issue: {e}")
