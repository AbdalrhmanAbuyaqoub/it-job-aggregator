import asyncio
import logging
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from it_job_aggregator.models import Job
from it_job_aggregator.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
INITIAL_BACKOFF = 2  # seconds
HTTP_TIMEOUT = 15.0  # seconds
USER_AGENT = "ITJobAggregator/0.1 (+https://github.com)"


class TelegramScraper(BaseScraper):
    """
    Scrapes job postings from a public Telegram channel's web preview.
    Uses the /s/ endpoint (e.g. https://t.me/s/job_channel)
    """

    def __init__(self, channel_name: str):
        # Ensure channel_name doesn't have the @ or t.me/ prefixes
        self.channel_name = (
            channel_name.replace("@", "").replace("t.me/", "").replace("https://", "")
        )
        self.url = f"https://t.me/s/{self.channel_name}"
        self.source_name = f"Telegram (@{self.channel_name})"

    async def scrape(
        self,
        max_retries: int = MAX_RETRIES,
        initial_backoff: float = INITIAL_BACKOFF,
    ) -> list[Job]:
        jobs: list[Job] = []

        for attempt in range(1, max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=HTTP_TIMEOUT,
                    headers={"User-Agent": USER_AGENT},
                ) as client:
                    response = await client.get(self.url)
                    response.raise_for_status()

                soup = BeautifulSoup(response.text, "html.parser")
                messages = soup.find_all("div", class_="tgme_widget_message_text")

                for msg in messages:
                    job = self._parse_message(msg)
                    if job:
                        jobs.append(job)

                return jobs

            except httpx.HTTPError as e:
                if attempt == max_retries:
                    logger.error(
                        f"HTTP error after {max_retries} attempts scraping {self.url}: {e}"
                    )
                else:
                    backoff = initial_backoff * (2 ** (attempt - 1))
                    logger.warning(
                        f"Scrape attempt {attempt}/{max_retries} failed: {e}. "
                        f"Retrying in {backoff}s..."
                    )
                    await asyncio.sleep(backoff)
            except Exception as e:
                logger.error(f"An unexpected error occurred: {e}")
                break

        return jobs

    # Known false-positive TLDs that Telegram auto-links from programming language
    # names or tech terms (e.g. VB.NET -> http://VB.NET/)
    FALSE_POSITIVE_DOMAINS = {
        "vb.net",
        "asp.net",
        "ado.net",
    }

    def _is_valid_job_link(self, url: str) -> bool:
        """
        Check if a URL is a real job application link vs a false positive
        auto-linked by Telegram (e.g. VB.NET being parsed as a domain).
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower().removeprefix("www.")
            # Reject known false-positive domains
            if domain in self.FALSE_POSITIVE_DOMAINS:
                return False
            # Reject URLs where the path is just "/" and domain looks like
            # a programming language TLD (single-segment path on a short domain)
            if parsed.path in ("", "/") and "." in domain:
                parts = domain.split(".")
                # e.g. "vb.net" has only 2 parts and the first is very short
                if len(parts) == 2 and len(parts[0]) <= 3:
                    return False
            return True
        except Exception:
            return True

    def _find_best_link(self, message_div) -> str | None:
        """
        Find the best job application link from a message.
        Prefers actual job board URLs over auto-linked false positives.
        Falls back to the Telegram message permalink.
        """
        all_links = message_div.find_all("a")
        valid_links = []

        for link_tag in all_links:
            href = link_tag.get("href", "")
            if href and self._is_valid_job_link(href):
                valid_links.append(href)

        if valid_links:
            return valid_links[0]

        # Fallback: link to the Telegram message itself
        msg_wrapper = message_div.find_parent("div", class_="tgme_widget_message")
        if msg_wrapper and msg_wrapper.has_attr("data-post"):
            return f"https://t.me/{msg_wrapper['data-post']}"

        return None

    def _parse_message(self, message_div) -> Job | None:
        """
        Extracts job details from a Telegram message HTML div.
        Returns a Job model if it looks like a valid job, else None.
        """
        # Get the full text content, replacing <br> with newlines for readability
        for br in message_div.find_all("br"):
            br.replace_with("\n")

        full_text = message_div.get_text()

        job_link = self._find_best_link(message_div)
        if not job_link:
            return None

        # Extracting a title is tricky from raw text.
        # We'll use the first line as the title, up to 100 characters.
        lines = [line.strip() for line in full_text.split("\n") if line.strip()]
        if not lines:
            return None

        raw_title = lines[0][:100]

        try:
            return Job(
                title=raw_title,
                # Extracting company reliably requires NLP or strict
                # formatting, leaving None for now
                company=None,
                link=job_link,
                description=full_text,
                source=self.source_name,
            )
        except Exception as e:
            logger.warning(f"Failed to validate job from message: {e}")
            return None
