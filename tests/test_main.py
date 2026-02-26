import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from it_job_aggregator.models import Job


# --- Fixtures ---

SAMPLE_JOBS = [
    Job(
        title="Software Engineer",
        company="Tech Corp",
        link="https://example.com/job/1",
        description="We need a software engineer with Python experience.",
        source="Telegram (@test_channel)",
    ),
    Job(
        title="Marketing Manager",
        company="Ad Corp",
        link="https://example.com/job/2",
        description="Looking for a marketing manager.",
        source="Telegram (@test_channel)",
    ),
    Job(
        title="DevOps Engineer",
        company="Cloud Co",
        link="https://example.com/job/3",
        description="DevOps engineer needed for cloud infrastructure.",
        source="Telegram (@test_channel)",
    ),
]


# --- Integration tests for run_pipeline ---


@pytest.mark.asyncio
async def test_run_pipeline_end_to_end():
    """Test the full pipeline: scrape -> filter -> deduplicate -> format -> send."""
    with (
        patch("it_job_aggregator.main.TelegramScraper") as mock_scraper_class,
        patch("it_job_aggregator.main.Database") as mock_db_class,
        patch("it_job_aggregator.main.JobFilter") as mock_filter_class,
        patch("it_job_aggregator.main.JobFormatter") as mock_formatter_class,
        patch(
            "it_job_aggregator.main.send_job_posting", new_callable=AsyncMock
        ) as mock_send,
        patch("it_job_aggregator.main.asyncio.sleep", new_callable=AsyncMock),
        patch("it_job_aggregator.main.TARGET_CHANNELS", ["test_channel"]),
    ):
        # Set up scraper mock
        mock_scraper = AsyncMock()
        mock_scraper.scrape.return_value = SAMPLE_JOBS
        mock_scraper_class.return_value = mock_scraper

        # Set up database mock (context manager)
        mock_db = MagicMock()
        # Job 1 (SW eng): IT job, new -> posted
        # Job 2 (marketing): filtered out by JobFilter
        # Job 3 (DevOps): IT job, new -> posted
        mock_db.save_job.side_effect = [True, True]  # Only called for IT jobs
        mock_db_class.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_class.return_value.__exit__ = MagicMock(return_value=False)

        # Set up filter mock — only IT jobs pass
        mock_filter = MagicMock()
        mock_filter.is_it_job.side_effect = [True, False, True]
        mock_filter_class.return_value = mock_filter

        # Set up formatter mock
        mock_formatter_class.format_job.side_effect = [
            "Formatted Job 1",
            "Formatted Job 3",
        ]

        from it_job_aggregator.main import run_pipeline

        await run_pipeline()

        # Verify scraper was called
        mock_scraper.scrape.assert_awaited_once()

        # Verify filter was called for all 3 jobs
        assert mock_filter.is_it_job.call_count == 3

        # Verify only 2 IT jobs were saved to DB
        assert mock_db.save_job.call_count == 2

        # Verify only 2 messages were sent
        assert mock_send.await_count == 2


@pytest.mark.asyncio
async def test_run_pipeline_all_duplicates():
    """Test pipeline when all jobs are duplicates (already in DB)."""
    with (
        patch("it_job_aggregator.main.TelegramScraper") as mock_scraper_class,
        patch("it_job_aggregator.main.Database") as mock_db_class,
        patch("it_job_aggregator.main.JobFilter") as mock_filter_class,
        patch("it_job_aggregator.main.JobFormatter") as mock_formatter_class,
        patch(
            "it_job_aggregator.main.send_job_posting", new_callable=AsyncMock
        ) as mock_send,
        patch("it_job_aggregator.main.asyncio.sleep", new_callable=AsyncMock),
        patch("it_job_aggregator.main.TARGET_CHANNELS", ["test_channel"]),
    ):
        mock_scraper = AsyncMock()
        mock_scraper.scrape.return_value = [SAMPLE_JOBS[0]]
        mock_scraper_class.return_value = mock_scraper

        mock_db = MagicMock()
        mock_db.save_job.return_value = False  # All duplicates
        mock_db_class.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_class.return_value.__exit__ = MagicMock(return_value=False)

        mock_filter = MagicMock()
        mock_filter.is_it_job.return_value = True
        mock_filter_class.return_value = mock_filter

        from it_job_aggregator.main import run_pipeline

        await run_pipeline()

        # Filter passed, but DB says duplicate — nothing should be sent
        mock_send.assert_not_awaited()
        mock_formatter_class.format_job.assert_not_called()


@pytest.mark.asyncio
async def test_run_pipeline_no_jobs_scraped():
    """Test pipeline when the scraper returns no jobs."""
    with (
        patch("it_job_aggregator.main.TelegramScraper") as mock_scraper_class,
        patch("it_job_aggregator.main.Database") as mock_db_class,
        patch("it_job_aggregator.main.JobFilter") as mock_filter_class,
        patch(
            "it_job_aggregator.main.send_job_posting", new_callable=AsyncMock
        ) as mock_send,
        patch("it_job_aggregator.main.asyncio.sleep", new_callable=AsyncMock),
        patch("it_job_aggregator.main.TARGET_CHANNELS", ["test_channel"]),
    ):
        mock_scraper = AsyncMock()
        mock_scraper.scrape.return_value = []  # No jobs
        mock_scraper_class.return_value = mock_scraper

        mock_db = MagicMock()
        mock_db_class.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_class.return_value.__exit__ = MagicMock(return_value=False)

        mock_filter_class.return_value = MagicMock()

        from it_job_aggregator.main import run_pipeline

        await run_pipeline()

        # Nothing to filter, save, or send
        mock_send.assert_not_awaited()
        mock_db.save_job.assert_not_called()


@pytest.mark.asyncio
async def test_run_pipeline_send_failure_continues():
    """Test that the pipeline continues processing jobs even if sending one fails."""
    jobs = [
        Job(
            title="Job A",
            link="https://example.com/a",
            description="Engineer needed",
            source="Telegram (@ch)",
        ),
        Job(
            title="Job B",
            link="https://example.com/b",
            description="Developer wanted",
            source="Telegram (@ch)",
        ),
    ]

    with (
        patch("it_job_aggregator.main.TelegramScraper") as mock_scraper_class,
        patch("it_job_aggregator.main.Database") as mock_db_class,
        patch("it_job_aggregator.main.JobFilter") as mock_filter_class,
        patch("it_job_aggregator.main.JobFormatter") as mock_formatter_class,
        patch(
            "it_job_aggregator.main.send_job_posting", new_callable=AsyncMock
        ) as mock_send,
        patch("it_job_aggregator.main.asyncio.sleep", new_callable=AsyncMock),
        patch("it_job_aggregator.main.TARGET_CHANNELS", ["test_channel"]),
    ):
        mock_scraper = AsyncMock()
        mock_scraper.scrape.return_value = jobs
        mock_scraper_class.return_value = mock_scraper

        mock_db = MagicMock()
        mock_db.save_job.return_value = True  # All new
        mock_db_class.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_class.return_value.__exit__ = MagicMock(return_value=False)

        mock_filter = MagicMock()
        mock_filter.is_it_job.return_value = True
        mock_filter_class.return_value = mock_filter

        mock_formatter_class.format_job.side_effect = [
            "Formatted A",
            "Formatted B",
        ]

        # First send fails, second succeeds
        mock_send.side_effect = [Exception("API Error"), None]

        from it_job_aggregator.main import run_pipeline

        await run_pipeline()

        # Both jobs should have been attempted
        assert mock_send.await_count == 2


@pytest.mark.asyncio
async def test_run_pipeline_multiple_channels():
    """Test that the pipeline scrapes from multiple configured channels."""
    with (
        patch("it_job_aggregator.main.TelegramScraper") as mock_scraper_class,
        patch("it_job_aggregator.main.Database") as mock_db_class,
        patch("it_job_aggregator.main.JobFilter") as mock_filter_class,
        patch("it_job_aggregator.main.JobFormatter") as mock_formatter_class,
        patch(
            "it_job_aggregator.main.send_job_posting", new_callable=AsyncMock
        ) as mock_send,
        patch("it_job_aggregator.main.asyncio.sleep", new_callable=AsyncMock),
        patch(
            "it_job_aggregator.main.TARGET_CHANNELS",
            ["channel_a", "channel_b"],
        ),
    ):
        mock_scraper = AsyncMock()
        mock_scraper.scrape.return_value = []
        mock_scraper_class.return_value = mock_scraper

        mock_db = MagicMock()
        mock_db_class.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_class.return_value.__exit__ = MagicMock(return_value=False)

        mock_filter_class.return_value = MagicMock()

        from it_job_aggregator.main import run_pipeline

        await run_pipeline()

        # TelegramScraper should have been instantiated twice (once per channel)
        assert mock_scraper_class.call_count == 2
        mock_scraper_class.assert_any_call(channel_name="channel_a")
        mock_scraper_class.assert_any_call(channel_name="channel_b")
