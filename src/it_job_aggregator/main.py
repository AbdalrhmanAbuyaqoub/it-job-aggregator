import argparse
import asyncio
import logging
import signal
import sys
from datetime import UTC, datetime, timedelta

from it_job_aggregator.bot import send_job_posting
from it_job_aggregator.config import SCRAPE_INTERVAL, TARGET_CHANNELS
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
    """Run a single scrape-filter-deduplicate-format-send cycle."""
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


async def run_loop(interval_minutes: int) -> None:
    """
    Run the pipeline in a continuous loop with a configurable interval.

    Handles SIGINT/SIGTERM for graceful shutdown. Errors in a single pipeline
    run are logged but do not crash the loop.
    """
    shutdown_event = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("Shutdown signal received. Finishing current cycle...")
        shutdown_event.set()

    # Register signal handlers on the running event loop
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    logger.info(
        f"Starting continuous loop (interval: {interval_minutes} min). Press Ctrl+C to stop."
    )

    while not shutdown_event.is_set():
        try:
            await run_pipeline()
        except Exception as e:
            logger.error(f"Pipeline error (will retry next cycle): {e}")

        if shutdown_event.is_set():
            break

        next_run = datetime.now(tz=UTC) + timedelta(minutes=interval_minutes)
        logger.info(f"Next run at {next_run.strftime('%Y-%m-%d %H:%M:%S UTC')}")

        # Sleep in small increments so shutdown is responsive
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=interval_minutes * 60)
        except TimeoutError:
            # Timeout means the interval elapsed without a shutdown signal — continue
            pass

    logger.info("Shutting down gracefully.")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="it-job-aggregator",
        description="Scrape IT jobs from Telegram channels, filter, deduplicate, and post.",
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--once",
        action="store_true",
        help="Run the pipeline once and exit.",
    )
    mode.add_argument(
        "--loop",
        action="store_true",
        default=True,
        help="Run the pipeline in a continuous loop (default).",
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        metavar="MINUTES",
        help=(
            "Scrape interval in minutes (overrides SCRAPE_INTERVAL env var). "
            "Must be a positive integer."
        ),
    )

    return parser.parse_args(argv)


def cli(argv: list[str] | None = None) -> None:
    """CLI entry point for the package."""
    args = parse_args(argv)

    # Determine interval: CLI flag > env var > default (30)
    if args.interval is not None:
        if args.interval <= 0:
            logger.error("--interval must be a positive integer.")
            sys.exit(1)
        interval = args.interval
    else:
        interval = SCRAPE_INTERVAL

    if args.once:
        asyncio.run(run_pipeline())
    else:
        asyncio.run(run_loop(interval))


if __name__ == "__main__":
    cli()
