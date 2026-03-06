import argparse
import asyncio
import logging
import signal
import sys
from datetime import UTC, datetime, timedelta

from it_job_aggregator.bot import send_job_posting
from it_job_aggregator.config import DB_PATH, SCRAPE_INTERVAL
from it_job_aggregator.db import Database
from it_job_aggregator.formatter import JobFormatter
from it_job_aggregator.models import Job
from it_job_aggregator.scrapers.base import BaseScraper
from it_job_aggregator.scrapers.forasps_scraper import ForasPsScraper
from it_job_aggregator.scrapers.jobsps_scraper import JobsPsScraper
from it_job_aggregator.utils import parse_job_date

# Scraper registry: add new scraper classes here to include them in the pipeline.
SCRAPER_REGISTRY: list[type[BaseScraper]] = [
    JobsPsScraper,
    ForasPsScraper,
]

# Set up logging once, in the application entry point only
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def _parse_posted_date(date_str: str) -> datetime:
    """
    Parse a posted_date string into a datetime for sorting.
    Formats: "24, Feb" (current year) or "16, Nov, 2025" (explicit year).
    Returns datetime.max if parsing fails, pushing unparseable dates to the end.

    Delegates to :func:`~it_job_aggregator.utils.parse_job_date` which
    handles year-boundary roll-back for the short format.
    """
    result = parse_job_date(date_str)
    return result if result is not None else datetime.max


def sort_jobs_by_posted_date(jobs: list[Job]) -> list[Job]:
    """
    Sort jobs by posted_date ascending (earliest first), preserving the
    relative order of jobs that have no posted_date.

    Dated jobs are sorted among themselves and placed back into the positions
    originally occupied by dated jobs.  Undated jobs remain in their original
    positions.  This keeps per-source ordering intact for sources that don't
    provide a posted_date (e.g. Foras.ps) while correctly interleaving dated
    jobs from other sources.

    Example::

        [JobsPs(Feb 24), Foras(None), JobsPs(Feb 10), Foras(None)]
        → [JobsPs(Feb 10), Foras(None), JobsPs(Feb 24), Foras(None)]
    """
    if not jobs:
        return []

    # Collect indices and jobs that have a parseable posted_date
    dated_indices: list[int] = []
    dated_jobs: list[Job] = []

    for i, job in enumerate(jobs):
        if job.posted_date and _parse_posted_date(job.posted_date) != datetime.max:
            dated_indices.append(i)
            dated_jobs.append(job)

    # Sort dated jobs by their parsed date (earliest first)
    dated_jobs.sort(key=lambda j: _parse_posted_date(j.posted_date))  # type: ignore[arg-type]

    # Rebuild the list: undated jobs stay put, dated jobs fill dated slots
    result = list(jobs)
    for slot, job in zip(dated_indices, dated_jobs):
        result[slot] = job

    return result


async def run_pipeline() -> None:
    """Run a single scrape-deduplicate-format-send cycle across all registered scrapers."""
    logger.info("Starting IT Job Aggregator Pipeline...")

    # Initialize components
    with Database(db_path=DB_PATH) as db:
        all_scraped_jobs: list[Job] = []

        for scraper_class in SCRAPER_REGISTRY:
            scraper = scraper_class()
            scraper_name = scraper.SOURCE_NAME
            logger.info(f"Scraping IT jobs from {scraper_name}...")

            try:
                scraped_jobs = await scraper.scrape(db=db)
                logger.info(f"Scraped {len(scraped_jobs)} jobs from {scraper_name}.")
                all_scraped_jobs.extend(scraped_jobs)
            except Exception as e:
                logger.error(f"Scraper {scraper_name} failed: {e}")
                continue

        # Sort by posted date ascending (earliest first)
        all_scraped_jobs = sort_jobs_by_posted_date(all_scraped_jobs)

        total_scraped = len(all_scraped_jobs)
        total_duplicates = 0
        total_posted = 0
        total_failed = 0

        for job in all_scraped_jobs:
            # Step 1: Save to DB to check for duplicates
            is_new = db.save_job(job)
            if not is_new:
                logger.debug(f"Duplicate job skipped: {job.title}")
                total_duplicates += 1
                continue

            # Step 2: Format and Send
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
        description="Scrape IT jobs from multiple sources, deduplicate, and post to Telegram.",
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
