import asyncio
import logging
from it_job_aggregator.scrapers.telegram_scraper import TelegramScraper
from it_job_aggregator.db import Database

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Initializing database...")
    db = Database("jobs_demo.db")

    # The channel we want to scrape
    channel_name = "jobspsco"
    logger.info(f"Initializing Telegram Scraper for channel: {channel_name}")
    scraper = TelegramScraper(channel_name=channel_name)

    logger.info("Scraping jobs...")
    jobs = await scraper.scrape()

    logger.info(f"Scraped {len(jobs)} potential jobs.")

    new_jobs_count = 0
    for job in jobs:
        if db.save_job(job):
            logger.info(f"New Job Saved! -> {job.title} | Link: {job.link}")
            new_jobs_count += 1
        else:
            logger.info(f"Duplicate Job Skipped -> {job.title}")

    logger.info(f"Summary: Found {new_jobs_count} new jobs out of {len(jobs)} scraped.")


if __name__ == "__main__":
    asyncio.run(main())
