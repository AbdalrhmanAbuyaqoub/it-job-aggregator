import os

import pytest

# Set environment variables for tests before any imports happen
os.environ["TELEGRAM_BOT_TOKEN"] = "test_bot_token"
os.environ["TELEGRAM_CHANNEL_ID"] = "test_channel_id"

from it_job_aggregator.models import Job  # noqa: E402


@pytest.fixture
def sample_job():
    """A reusable sample Job for tests."""
    return Job(
        title="Senior Software Engineer",
        company="Tech Corp",
        link="https://example.com/job/123",
        description="We are looking for a senior software engineer with 5+ years experience.",
        source="Jobs.ps",
        position_level="Mid-Level",
        location="Ramallah",
        deadline="2026-03-24",
        experience="3 Years",
        posted_date="24, Feb",
    )


@pytest.fixture
def sample_job_no_company():
    """A reusable sample Job without a company."""
    return Job(
        title="QA Automation Engineer",
        link="https://example.com/job/456",
        description="Join our QA team.",
        source="Jobs.ps",
    )
