from unittest.mock import AsyncMock, patch

import pytest

from it_job_aggregator.scrapers.telegram_scraper import TelegramScraper

# Sample HTML structure resembling Telegram Web Preview
SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<body>
    <div class="tgme_widget_message" data-post="job_channel/123">
        <div class="tgme_widget_message_text">
            🚀 <b>Senior Python SDET Needed!</b><br>
            <br>
            We are looking for an experienced QA Automation Engineer to join our team.<br>
            Must know Pytest and Docker.<br>
            <br>
            Apply here: <a href="https://example.com/apply">Application Link</a>
        </div>
    </div>

    <div class="tgme_widget_message" data-post="job_channel/124">
        <div class="tgme_widget_message_text">
            Just a regular non-job message. Welcome to the channel!
        </div>
    </div>

    <div class="tgme_widget_message" data-post="job_channel/125">
        <div class="tgme_widget_message_text">
            Looking for a Junior QA!<br>
            DM me for details.
            <!-- No explicit link, should fallback to message link -->
        </div>
    </div>
</body>
</html>
"""


@pytest.fixture
def scraper():
    return TelegramScraper(channel_name="test_channel")


@pytest.mark.asyncio
async def test_telegram_scraper_success(scraper, httpx_mock):
    """Test that the scraper correctly parses valid HTML using mocked HTTP requests."""
    # Mock the HTTP response to return our sample HTML
    httpx_mock.add_response(text=SAMPLE_HTML)

    jobs = await scraper.scrape(max_retries=1)

    # We expect 3 jobs because the scraper no longer filters by keywords.
    assert len(jobs) == 3

    # Check the first job (explicit link)
    job1 = jobs[0]
    assert "Senior Python SDET Needed!" in job1.title
    assert "Pytest" in job1.description
    assert str(job1.link).rstrip("/") == "https://example.com/apply"
    assert job1.source == "Telegram (@test_channel)"
    assert job1.company is None

    # Check the third job (fallback link from data-post)
    job3 = jobs[2]
    assert "Looking for a Junior QA!" in job3.title
    assert str(job3.link) == "https://t.me/job_channel/125"


@pytest.mark.asyncio
async def test_telegram_scraper_http_error(scraper, httpx_mock):
    """Test that the scraper handles HTTP errors gracefully after retries."""
    # Mock 404 for all 3 retry attempts
    httpx_mock.add_response(status_code=404)
    httpx_mock.add_response(status_code=404)
    httpx_mock.add_response(status_code=404)

    with patch(
        "it_job_aggregator.scrapers.telegram_scraper.asyncio.sleep",
        new_callable=AsyncMock,
    ):
        jobs = await scraper.scrape(max_retries=3, initial_backoff=0)

    # Should return an empty list after all retries fail
    assert len(jobs) == 0


@pytest.mark.asyncio
async def test_telegram_scraper_succeeds_on_retry(scraper, httpx_mock):
    """Test that the scraper recovers after a transient HTTP error."""

    # First attempt fails, second succeeds
    httpx_mock.add_response(status_code=500)
    httpx_mock.add_response(text=SAMPLE_HTML)

    with patch(
        "it_job_aggregator.scrapers.telegram_scraper.asyncio.sleep",
        new_callable=AsyncMock,
    ) as mock_sleep:
        jobs = await scraper.scrape(max_retries=3, initial_backoff=2)

    assert len(jobs) == 3
    mock_sleep.assert_awaited_once_with(2)


# HTML where the first link is a false positive (VB.NET auto-linked by Telegram)
SAMPLE_HTML_FALSE_LINK = """
<!DOCTYPE html>
<html>
<body>
    <div class="tgme_widget_message" data-post="job_channel/200">
        <div class="tgme_widget_message_text">
            شاغر لدى شركة ERP Easy Solutions<br>
            مبرمج <a href="http://VB.NET/">VB.NET</a><br>
            للتقديم عبر جوبس: <a href="https://jobsps.co/4se8Xqa">https://jobsps.co/4se8Xqa</a>
        </div>
    </div>
</body>
</html>
"""


@pytest.mark.asyncio
async def test_telegram_scraper_skips_false_positive_links(scraper, httpx_mock):
    """Test that VB.NET and similar auto-linked domains are skipped in favor of real job links."""
    httpx_mock.add_response(text=SAMPLE_HTML_FALSE_LINK)

    jobs = await scraper.scrape(max_retries=1)

    assert len(jobs) == 1
    # Should use the jobsps.co link, not the VB.NET false positive
    assert str(jobs[0].link).rstrip("/") == "https://jobsps.co/4se8Xqa"


# HTML where the only link is a false positive — should fallback to message permalink
SAMPLE_HTML_ONLY_FALSE_LINK = """
<!DOCTYPE html>
<html>
<body>
    <div class="tgme_widget_message" data-post="job_channel/201">
        <div class="tgme_widget_message_text">
            مطلوب مبرمج <a href="http://ASP.NET/">ASP.NET</a> للعمل فوراً
        </div>
    </div>
</body>
</html>
"""


@pytest.mark.asyncio
async def test_telegram_scraper_fallback_when_only_false_link(scraper, httpx_mock):
    """Test fallback to message permalink when the only link is a false positive."""
    httpx_mock.add_response(text=SAMPLE_HTML_ONLY_FALSE_LINK)

    jobs = await scraper.scrape(max_retries=1)

    assert len(jobs) == 1
    # Should fallback to the Telegram message permalink
    assert str(jobs[0].link) == "https://t.me/job_channel/201"


def test_is_valid_job_link(scraper):
    """Test the false-positive link detection directly."""
    assert scraper._is_valid_job_link("http://VB.NET/") is False
    assert scraper._is_valid_job_link("http://ASP.NET/") is False
    assert scraper._is_valid_job_link("http://ADO.NET/") is False
    assert scraper._is_valid_job_link("https://jobsps.co/4se8Xqa") is True
    assert scraper._is_valid_job_link("https://example.com/apply") is True
    assert scraper._is_valid_job_link("https://t.me/job_channel/123") is True


# --- New tests ---


@pytest.mark.parametrize(
    "input_name,expected_channel",
    [
        ("test_channel", "test_channel"),
        ("@test_channel", "test_channel"),
        ("https://t.me/test_channel", "test_channel"),
        ("t.me/test_channel", "test_channel"),
    ],
)
def test_channel_name_normalization(input_name, expected_channel):
    """Test that various channel name formats are normalized correctly."""
    scraper = TelegramScraper(channel_name=input_name)
    assert scraper.channel_name == expected_channel


SAMPLE_HTML_EMPTY_PAGE = """
<!DOCTYPE html>
<html>
<body>
    <div class="tgme_page_widget">
        <!-- No message divs at all -->
    </div>
</body>
</html>
"""


@pytest.mark.asyncio
async def test_telegram_scraper_empty_page(httpx_mock):
    """Test that the scraper returns an empty list for an HTML page with no messages."""
    scraper = TelegramScraper(channel_name="empty_channel")
    httpx_mock.add_response(text=SAMPLE_HTML_EMPTY_PAGE)

    jobs = await scraper.scrape(max_retries=1)

    assert jobs == []


SAMPLE_HTML_EMPTY_MESSAGE = """
<!DOCTYPE html>
<html>
<body>
    <div class="tgme_widget_message" data-post="job_channel/300">
        <div class="tgme_widget_message_text">
        </div>
    </div>
</body>
</html>
"""


@pytest.mark.asyncio
async def test_telegram_scraper_empty_message_div(httpx_mock):
    """Test that a message div with no text content yields no jobs."""
    scraper = TelegramScraper(channel_name="test_channel")
    httpx_mock.add_response(text=SAMPLE_HTML_EMPTY_MESSAGE)

    jobs = await scraper.scrape(max_retries=1)

    # Empty message has no text lines and no links — _parse_message returns None
    assert jobs == []


SAMPLE_HTML_NO_LINK_NO_DATA_POST = """
<!DOCTYPE html>
<html>
<body>
    <div class="tgme_widget_message">
        <div class="tgme_widget_message_text">
            This message has no links and no data-post attribute on the parent.
        </div>
    </div>
</body>
</html>
"""


@pytest.mark.asyncio
async def test_telegram_scraper_no_link_no_data_post(httpx_mock):
    """Test that a message with no links and no data-post attribute is skipped."""
    scraper = TelegramScraper(channel_name="test_channel")
    httpx_mock.add_response(text=SAMPLE_HTML_NO_LINK_NO_DATA_POST)

    jobs = await scraper.scrape(max_retries=1)

    # No valid link can be constructed — _find_best_link returns None
    assert jobs == []


def test_scraper_url_construction():
    """Test that the scraper constructs the correct URL from the channel name."""
    scraper = TelegramScraper(channel_name="jobspsco")
    assert scraper.url == "https://t.me/s/jobspsco"
    assert scraper.source_name == "Telegram (@jobspsco)"


def test_scraper_source_name():
    """Test that the source name is formatted with the @ prefix."""
    scraper = TelegramScraper(channel_name="my_channel")
    assert scraper.source_name == "Telegram (@my_channel)"


@pytest.mark.asyncio
async def test_telegram_scraper_unexpected_exception_returns_empty(httpx_mock):
    """Test that an unexpected (non-HTTP) error during parsing returns an empty list."""
    scraper = TelegramScraper(channel_name="test_channel")

    # Return HTML that will cause BeautifulSoup to work, but patch _parse_message to raise
    httpx_mock.add_response(text=SAMPLE_HTML)

    with patch.object(scraper, "_parse_message", side_effect=TypeError("unexpected")):
        jobs = await scraper.scrape(max_retries=1)

    assert jobs == []
