import asyncio
import logging

from it_job_aggregator.bot import send_job_posting
from it_job_aggregator.config import TARGET_CHANNELS
from it_job_aggregator.db import Database
from it_job_aggregator.filters import JobFilter
from it_job_aggregator.formatter import JobFormatter
from it_job_aggregator.scrapers.telegram_scraper import TelegramScraper

# Set up logging once, in the application entry point only
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


async def run_pipeline() -> None:
    logger.info("Starting IT Job Aggregator Pipeline...")

    # Initialize components
    with Database() as db:
        job_filter = JobFilter()

        channels = TARGET_CHANNELS
        logger.info(f"Target channels: {channels}")

        total_scraped = 0
        total_filtered = 0
        total_duplicates = 0
        total_posted = 0
        total_failed = 0

        for target_channel in channels:
            scraper = TelegramScraper(channel_name=target_channel)

            logger.info(f"Scraping jobs from: {target_channel}")
            scraped_jobs = await scraper.scrape()
            logger.info(f"Scraped {len(scraped_jobs)} raw messages from {target_channel}.")
            total_scraped += len(scraped_jobs)

            for job in scraped_jobs:
                # Step 1: Filter
                if not job_filter.is_it_job(job.description):
                    logger.debug(f"Filtered out non-IT job: {job.title}")
                    total_filtered += 1
                    continue

                # Step 2: Save to DB to check for duplicates
                is_new = db.save_job(job)
                if not is_new:
                    logger.debug(f"Duplicate job skipped: {job.title}")
                    total_duplicates += 1
                    continue

                # Step 3: Format and Send
                try:
                    logger.info(f"New IT Job found: {job.title}. Preparing to post...")
                    formatted_message = JobFormatter.format_job(job)
                    await send_job_posting(formatted_message)
                    total_posted += 1

                    # Small delay to avoid hitting Telegram API rate limits
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"Failed to process and post job '{job.title}': {e}")
                    total_failed += 1

    logger.info(
        f"Pipeline finished. "
        f"Scraped: {total_scraped}, "
        f"Filtered out: {total_filtered}, "
        f"Duplicates: {total_duplicates}, "
        f"Posted: {total_posted}, "
        f"Failed: {total_failed}"
    )


def cli() -> None:
    """CLI entry point for the package."""
    asyncio.run(run_pipeline())


if __name__ == "__main__":
    cli()
