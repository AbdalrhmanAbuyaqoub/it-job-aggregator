import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from it_job_aggregator.scrapers.jobsps_scraper import JobsPsScraper

# --- Sample HTML fixtures ---

SAMPLE_LISTING_HTML = """
<!DOCTYPE html>
<html>
<body>
    <div class="list-3--body">
        <a class="list-3--title list-3--row"
           href="https://www.jobs.ps/en/jobs/full-stack-developer-65321"
           title="Full Stack Developer">
            <div class="list-3--cell-1 list-3--cell-title-2">
                Full Stack Developer
                <div class="list--cell--company">Oyoun Media</div>
            </div>
            <div class="list-3--cell-1">
                <span class="tooltip" title="Ramallah">Ramallah</span>
            </div>
            <div class="list-3--cell-1 list-3--cell-4 align-right">24, Feb</div>
        </a>
        <a class="list-3--title list-3--row"
           href="https://www.jobs.ps/en/jobs/backend-developer-65300"
           title="Backend Developer">
            <div class="list-3--cell-1 list-3--cell-title-2">
                Backend Developer
                <div class="list--cell--company">Tech Corp</div>
            </div>
            <div class="list-3--cell-1">
                <span class="tooltip" title="Hebron">Hebron</span>
            </div>
            <div class="list-3--cell-1 list-3--cell-4 align-right">20, Feb</div>
        </a>
    </div>
    <div class="pagination-container">
        <ul class="pagination">
            <li><a href="#" class="disabled">First</a></li>
            <li><span class="active">1</span></li>
            <li><a href="https://www.jobs.ps/en/categories/it-jobs?page=2">2</a></li>
            <li><a href="https://www.jobs.ps/en/categories/it-jobs?page=3">Last</a></li>
        </ul>
    </div>
</body>
</html>
"""

SAMPLE_LISTING_HTML_SINGLE_PAGE = """
<!DOCTYPE html>
<html>
<body>
    <div class="list-3--body">
        <a class="list-3--title list-3--row"
           href="https://www.jobs.ps/en/jobs/qa-engineer-65400"
           title="QA Engineer">
            <div class="list-3--cell-1 list-3--cell-title-2">
                QA Engineer
                <div class="list--cell--company">QA Co</div>
            </div>
            <div class="list-3--cell-1">
                <span class="tooltip" title="Nablus">Nablus</span>
            </div>
            <div class="list-3--cell-1 list-3--cell-4 align-right">27, Feb</div>
        </a>
    </div>
    <div class="pagination-container">
        <ul class="pagination">
            <li><span class="active">1</span></li>
        </ul>
    </div>
</body>
</html>
"""

SAMPLE_LISTING_HTML_OLD_JOBS = """
<!DOCTYPE html>
<html>
<body>
    <div class="list-3--body">
        <a class="list-3--title list-3--row"
           href="https://www.jobs.ps/en/jobs/old-job-64000"
           title="Old Job">
            <div class="list-3--cell-1 list-3--cell-title-2">
                Old Job
                <div class="list--cell--company">Old Corp</div>
            </div>
            <div class="list-3--cell-1">
                <span class="tooltip" title="Gaza">Gaza</span>
            </div>
            <div class="list-3--cell-1 list-3--cell-4 align-right">15, Oct, 2025</div>
        </a>
    </div>
    <div class="pagination-container">
        <ul class="pagination">
            <li><span class="active">1</span></li>
        </ul>
    </div>
</body>
</html>
"""

SAMPLE_LISTING_HTML_EMPTY = """
<!DOCTYPE html>
<html>
<body>
    <div class="list-3--body">
    </div>
</body>
</html>
"""


def _make_detail_html(
    position_level: str = "Mid-Level",
    location: str = "Ramallah",
    deadline: str = "2026-03-24",
    experience: str = "3 Years",
) -> str:
    """Build a sample detail page HTML with JSON-LD and HTML metadata."""
    ld_json = json.dumps(
        {
            "@context": "http://schema.org",
            "@type": "JobPosting",
            "title": "Full Stack Developer",
            "validThrough": deadline,
            "experienceRequirements": experience,
            "jobLocation": [
                {
                    "@type": "Place",
                    "address": {
                        "@type": "PostalAddress",
                        "addressLocality": location,
                        "addressCountry": "Palestine",
                    },
                }
            ],
        }
    )
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script type="application/ld+json">{ld_json}</script>
    </head>
    <body>
        <div class="view--detail-custom">
            <div class="view--detail-item">
                <span>Job Title</span>
                <span>Full Stack Developer</span>
            </div>
            <div class="view--detail-item">
                <span>Deadline</span>
                <span>24 - Mar - 2026</span>
            </div>
            <div class="view--detail-item view--detail-item-location">
                <span>Location</span>
                <span class="tooltip" title="{location}">{location}</span>
            </div>
            <div class="view--detail-item">
                <span>Position Level</span>
                <span>{position_level}</span>
            </div>
            <div class="view--detail-item">
                <span>Experience</span>
                <span>{experience}</span>
            </div>
        </div>
    </body>
    </html>
    """


SAMPLE_DETAIL_HTML = _make_detail_html()


SAMPLE_DETAIL_HTML_NO_JSON_LD = """
<!DOCTYPE html>
<html>
<body>
    <div class="view--detail-custom">
        <div class="view--detail-item">
            <span>Position Level</span>
            <span>Senior</span>
        </div>
        <div class="view--detail-item view--detail-item-location">
            <span>Location</span>
            <span class="tooltip" title="Bethlehem">Bethlehem</span>
        </div>
        <div class="view--detail-item">
            <span>Deadline</span>
            <span>15 - Apr - 2026</span>
        </div>
        <div class="view--detail-item">
            <span>Experience</span>
            <span>5 Years</span>
        </div>
    </div>
</body>
</html>
"""


# --- Mock helpers ---


def _make_mock_page(html_responses: list[str]) -> AsyncMock:
    """
    Create a mock Playwright Page that returns HTML from a list in order.
    Each call to page.goto() + page.content() returns the next HTML string.
    If a response is None, goto() raises an exception (simulating failure).
    """
    mock_page = AsyncMock()
    response_iter = iter(html_responses)

    async def mock_goto(url, **kwargs):
        """Mock page.goto() that returns a response object."""
        html = next(response_iter, None)
        if html is None:
            raise Exception(f"Simulated failure for {url}")
        # Store the HTML so content() can return it
        mock_page._current_html = html
        mock_response = MagicMock()
        mock_response.status = 200
        return mock_response

    async def mock_content():
        """Mock page.content() that returns stored HTML."""
        return mock_page._current_html

    async def mock_title():
        """Mock page.title() for Cloudflare check."""
        return "Jobs.ps"

    mock_page.goto = mock_goto
    mock_page.content = mock_content
    mock_page.title = mock_title
    mock_page.wait_for_function = AsyncMock()
    mock_page.wait_for_load_state = AsyncMock()
    return mock_page


def _make_mock_page_with_errors(error_count: int, success_html: str | None = None) -> AsyncMock:
    """
    Create a mock Page that fails error_count times, then succeeds.
    If success_html is None, all attempts fail.
    """
    mock_page = AsyncMock()
    call_count = 0

    async def mock_goto(url, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= error_count:
            mock_response = MagicMock()
            mock_response.status = 500
            mock_page._current_html = ""
            return mock_response
        if success_html is not None:
            mock_page._current_html = success_html
            mock_response = MagicMock()
            mock_response.status = 200
            return mock_response
        mock_response = MagicMock()
        mock_response.status = 500
        mock_page._current_html = ""
        return mock_response

    async def mock_content():
        return mock_page._current_html

    async def mock_title():
        return "Jobs.ps"

    mock_page.goto = mock_goto
    mock_page.content = mock_content
    mock_page.title = mock_title
    mock_page.wait_for_function = AsyncMock()
    mock_page.wait_for_load_state = AsyncMock()
    return mock_page


# --- Scraper fixture ---


@pytest.fixture
def scraper():
    """Fixture providing a JobsPsScraper instance."""
    return JobsPsScraper()


# --- Listing page tests ---


@pytest.mark.asyncio
async def test_scrape_listing_page_parses_jobs(scraper):
    """Test that the scraper correctly parses job rows from a listing page."""
    mock_page = _make_mock_page([SAMPLE_LISTING_HTML])
    cutoff_date = datetime.now() - timedelta(days=30)

    jobs, has_old = await scraper._scrape_listing_page(
        mock_page, page_num=1, cutoff_date=cutoff_date, max_retries=1, initial_backoff=0
    )

    assert len(jobs) == 2
    assert jobs[0]["title"] == "Full Stack Developer"
    assert jobs[0]["company"] == "Oyoun Media"
    assert jobs[0]["location"] == "Ramallah"
    assert jobs[1]["title"] == "Backend Developer"
    assert jobs[1]["company"] == "Tech Corp"
    assert jobs[1]["location"] == "Hebron"


@pytest.mark.asyncio
async def test_scrape_listing_page_filters_old_jobs(scraper):
    """Test that jobs older than the cutoff date are excluded."""
    mock_page = _make_mock_page([SAMPLE_LISTING_HTML_OLD_JOBS])
    cutoff_date = datetime.now() - timedelta(days=30)

    jobs, has_old = await scraper._scrape_listing_page(
        mock_page, page_num=1, cutoff_date=cutoff_date, max_retries=1, initial_backoff=0
    )

    assert len(jobs) == 0
    assert has_old is True


@pytest.mark.asyncio
async def test_scrape_listing_page_empty(scraper):
    """Test that an empty listing page returns no jobs."""
    mock_page = _make_mock_page([SAMPLE_LISTING_HTML_EMPTY])
    cutoff_date = datetime.now() - timedelta(days=30)

    jobs, has_old = await scraper._scrape_listing_page(
        mock_page, page_num=1, cutoff_date=cutoff_date, max_retries=1, initial_backoff=0
    )

    assert jobs == []
    assert has_old is False


# --- Detail page tests ---


@pytest.mark.asyncio
async def test_scrape_detail_page_extracts_metadata(scraper):
    """Test that the detail page scraper extracts all metadata fields."""
    mock_page = _make_mock_page([SAMPLE_DETAIL_HTML])

    listing = {
        "title": "Full Stack Developer",
        "company": "Oyoun Media",
        "link": "https://www.jobs.ps/en/jobs/full-stack-developer-65321",
        "location": "Ramallah",
        "date_str": "24, Feb",
    }

    job = await scraper._scrape_detail_page(mock_page, listing, max_retries=1, initial_backoff=0)

    assert job is not None
    assert job.title == "Full Stack Developer"
    assert job.company == "Oyoun Media"
    assert job.position_level == "Mid-Level"
    assert job.location == "Ramallah"
    assert job.deadline == "2026-03-24"
    assert job.experience == "3 Years"
    assert job.source == "Jobs.ps"
    assert job.posted_date == "24, Feb"


@pytest.mark.asyncio
async def test_scrape_detail_page_html_fallback(scraper):
    """Test that HTML metadata is used when JSON-LD is missing."""
    mock_page = _make_mock_page([SAMPLE_DETAIL_HTML_NO_JSON_LD])

    listing = {
        "title": "Backend Developer",
        "company": "Tech Corp",
        "link": "https://www.jobs.ps/en/jobs/backend-dev-65300",
        "location": "Bethlehem",
        "date_str": "20, Feb",
    }

    job = await scraper._scrape_detail_page(mock_page, listing, max_retries=1, initial_backoff=0)

    assert job is not None
    assert job.position_level == "Senior"
    assert job.location == "Bethlehem"
    assert job.deadline == "15 - Apr - 2026"
    assert job.experience == "5 Years"
    assert job.posted_date == "20, Feb"


@pytest.mark.asyncio
async def test_scrape_detail_page_failure_returns_listing_fallback(scraper):
    """Test that when the detail page fails, a Job is created from listing data."""
    mock_page = _make_mock_page_with_errors(error_count=1)

    listing = {
        "title": "Some Job",
        "company": "Some Corp",
        "link": "https://www.jobs.ps/en/jobs/some-job-99999",
        "location": "Nablus",
        "date_str": "25, Feb",
    }

    job = await scraper._scrape_detail_page(mock_page, listing, max_retries=1, initial_backoff=0)

    assert job is not None
    assert job.title == "Some Job"
    assert job.company == "Some Corp"
    assert job.location == "Nablus"
    # No detail metadata available
    assert job.position_level is None
    assert job.deadline is None
    assert job.experience is None
    assert job.posted_date == "25, Feb"


# --- Date parsing tests ---


@pytest.mark.parametrize(
    "date_str, expected_month, expected_day",
    [
        ("24, Feb", 2, 24),
        ("5, Jan", 1, 5),
        ("15, Dec", 12, 15),
        ("1, Mar", 3, 1),
    ],
)
def test_parse_listing_date_current_year(scraper, date_str, expected_month, expected_day):
    """Test parsing date strings without an explicit year (assumes current year)."""
    result = scraper._parse_listing_date(date_str)
    assert result is not None
    assert result.year == datetime.now().year
    assert result.month == expected_month
    assert result.day == expected_day


@pytest.mark.parametrize(
    "date_str, expected_year, expected_month, expected_day",
    [
        ("16, Nov, 2025", 2025, 11, 16),
        ("23, Oct, 2025", 2025, 10, 23),
        ("1, Jan, 2024", 2024, 1, 1),
    ],
)
def test_parse_listing_date_explicit_year(
    scraper, date_str, expected_year, expected_month, expected_day
):
    """Test parsing date strings with an explicit year."""
    result = scraper._parse_listing_date(date_str)
    assert result is not None
    assert result.year == expected_year
    assert result.month == expected_month
    assert result.day == expected_day


def test_parse_listing_date_empty_string(scraper):
    """Test that an empty date string returns None."""
    assert scraper._parse_listing_date("") is None


def test_parse_listing_date_invalid_format(scraper):
    """Test that an invalid date string returns None."""
    assert scraper._parse_listing_date("invalid date") is None


# --- Pagination tests ---


@pytest.mark.asyncio
async def test_get_total_pages_multi_page(scraper):
    """Test that total pages is correctly extracted from pagination links."""
    mock_page = _make_mock_page([SAMPLE_LISTING_HTML])

    total = await scraper._get_total_pages(mock_page, max_retries=1, initial_backoff=0)

    assert total == 3


@pytest.mark.asyncio
async def test_get_total_pages_single_page(scraper):
    """Test that a single page listing returns 1 as total pages."""
    mock_page = _make_mock_page([SAMPLE_LISTING_HTML_SINGLE_PAGE])

    total = await scraper._get_total_pages(mock_page, max_retries=1, initial_backoff=0)

    assert total == 1


# --- Parse listing row tests ---


def test_parse_listing_row_valid(scraper):
    """Test parsing a well-formed listing row."""
    from bs4 import BeautifulSoup

    html = """
    <a class="list-3--title list-3--row"
       href="https://www.jobs.ps/en/jobs/test-job-123"
       title="Test Job">
        <div class="list-3--cell-1 list-3--cell-title-2">
            Test Job
            <div class="list--cell--company">Test Corp</div>
        </div>
        <div class="list-3--cell-1">
            <span class="tooltip" title="Ramallah, Hebron">Ramallah</span>
        </div>
        <div class="list-3--cell-1 list-3--cell-4 align-right">27, Feb</div>
    </a>
    """
    soup = BeautifulSoup(html, "html.parser")
    row = soup.find("a")
    result = scraper._parse_listing_row(row)

    assert result is not None
    assert result["title"] == "Test Job"
    assert result["company"] == "Test Corp"
    assert result["link"] == "https://www.jobs.ps/en/jobs/test-job-123"
    assert result["location"] == "Ramallah, Hebron"
    assert result["date_str"] == "27, Feb"


def test_parse_listing_row_missing_title(scraper):
    """Test that a row without a title attribute returns None."""
    from bs4 import BeautifulSoup

    html = '<a class="list-3--row" href="https://example.com"></a>'
    soup = BeautifulSoup(html, "html.parser")
    row = soup.find("a")
    result = scraper._parse_listing_row(row)

    assert result is None


def test_parse_listing_row_missing_href(scraper):
    """Test that a row without an href attribute returns None."""
    from bs4 import BeautifulSoup

    html = '<a class="list-3--row" title="Test Job"></a>'
    soup = BeautifulSoup(html, "html.parser")
    row = soup.find("a")
    result = scraper._parse_listing_row(row)

    assert result is None


# --- Extract detail metadata tests ---


def test_extract_detail_metadata_json_ld(scraper):
    """Test extracting metadata from JSON-LD structured data."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(SAMPLE_DETAIL_HTML, "html.parser")
    details = scraper._extract_detail_metadata(soup)

    assert details["deadline"] == "2026-03-24"
    assert details["experience"] == "3 Years"
    assert details["location"] == "Ramallah"
    assert details["position_level"] == "Mid-Level"


def test_extract_detail_metadata_html_only(scraper):
    """Test extracting metadata when JSON-LD is absent, using HTML fallback."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(SAMPLE_DETAIL_HTML_NO_JSON_LD, "html.parser")
    details = scraper._extract_detail_metadata(soup)

    assert details["position_level"] == "Senior"
    assert details["location"] == "Bethlehem"
    assert details["deadline"] == "15 - Apr - 2026"
    assert details["experience"] == "5 Years"


def test_extract_detail_metadata_empty_page(scraper):
    """Test that an empty detail page returns an empty dict."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup("<html><body></body></html>", "html.parser")
    details = scraper._extract_detail_metadata(soup)

    assert details == {}


# --- Full scrape integration test ---


@pytest.mark.asyncio
async def test_scrape_full_flow(scraper):
    """Test the full scrape flow: listing pages -> detail pages -> Job objects."""
    detail_html = _make_detail_html(
        position_level="Entry Level",
        location="Nablus",
        deadline="2026-04-01",
        experience="1 Years",
    )
    # Response order: _get_total_pages, _scrape_listing_page, detail page
    mock_page = _make_mock_page(
        [
            SAMPLE_LISTING_HTML_SINGLE_PAGE,
            SAMPLE_LISTING_HTML_SINGLE_PAGE,
            detail_html,
        ]
    )

    mock_context = AsyncMock()
    mock_context.new_page.return_value = mock_page

    mock_browser = AsyncMock()
    mock_browser.new_context.return_value = mock_context

    mock_pw = AsyncMock()
    mock_pw.chromium.launch.return_value = mock_browser

    mock_stealth_cm = AsyncMock()
    mock_stealth_cm.__aenter__.return_value = mock_pw

    mock_stealth = MagicMock()
    mock_stealth.use_async.return_value = mock_stealth_cm

    with (
        patch(
            "it_job_aggregator.scrapers.jobsps_scraper.Stealth",
            return_value=mock_stealth,
        ),
        patch(
            "it_job_aggregator.scrapers.jobsps_scraper.asyncio.sleep",
            new_callable=AsyncMock,
        ),
    ):
        jobs = await scraper.scrape(max_retries=1, initial_backoff=0)

    assert len(jobs) == 1
    job = jobs[0]
    assert job.title == "QA Engineer"
    assert job.company == "QA Co"
    assert job.position_level == "Entry Level"
    assert job.location == "Nablus"
    assert job.deadline == "2026-04-01"
    assert job.experience == "1 Years"
    assert job.source == "Jobs.ps"


@pytest.mark.asyncio
async def test_scrape_stops_pagination_on_old_jobs():
    """Test that pagination stops when all jobs on a page are older than 30 days."""
    scraper = JobsPsScraper()

    # Response order: _get_total_pages, _scrape_listing_page
    mock_page = _make_mock_page(
        [
            SAMPLE_LISTING_HTML_OLD_JOBS,
            SAMPLE_LISTING_HTML_OLD_JOBS,
        ]
    )

    mock_context = AsyncMock()
    mock_context.new_page.return_value = mock_page

    mock_browser = AsyncMock()
    mock_browser.new_context.return_value = mock_context

    mock_pw = AsyncMock()
    mock_pw.chromium.launch.return_value = mock_browser

    mock_stealth_cm = AsyncMock()
    mock_stealth_cm.__aenter__.return_value = mock_pw

    mock_stealth = MagicMock()
    mock_stealth.use_async.return_value = mock_stealth_cm

    with (
        patch(
            "it_job_aggregator.scrapers.jobsps_scraper.Stealth",
            return_value=mock_stealth,
        ),
        patch(
            "it_job_aggregator.scrapers.jobsps_scraper.asyncio.sleep",
            new_callable=AsyncMock,
        ),
    ):
        jobs = await scraper.scrape(max_retries=1, initial_backoff=0)

    assert len(jobs) == 0


# --- Retry tests ---


@pytest.mark.asyncio
async def test_fetch_page_retries_on_error(scraper):
    """Test that _fetch_page retries on errors with exponential backoff."""
    mock_page = _make_mock_page_with_errors(error_count=2, success_html="<html>Success</html>")

    with patch(
        "it_job_aggregator.scrapers.jobsps_scraper.asyncio.sleep",
        new_callable=AsyncMock,
    ) as mock_sleep:
        result = await scraper._fetch_page(
            mock_page,
            "https://www.jobs.ps/en/categories/it-jobs",
            max_retries=3,
            initial_backoff=2,
        )

    assert result == "<html>Success</html>"
    assert mock_sleep.await_count == 2
    mock_sleep.assert_any_await(2)
    mock_sleep.assert_any_await(4)


@pytest.mark.asyncio
async def test_fetch_page_returns_none_after_all_retries_fail(scraper):
    """Test that _fetch_page returns None when all retries are exhausted."""
    mock_page = _make_mock_page_with_errors(error_count=3)

    with patch(
        "it_job_aggregator.scrapers.jobsps_scraper.asyncio.sleep",
        new_callable=AsyncMock,
    ):
        result = await scraper._fetch_page(
            mock_page,
            "https://www.jobs.ps/en/categories/it-jobs",
            max_retries=2,
            initial_backoff=0,
        )

    assert result is None


# --- Cloudflare detection test ---


@pytest.mark.asyncio
async def test_wait_for_cloudflare_detects_challenge(scraper):
    """Test that Cloudflare challenge detection waits for resolution."""
    mock_page = AsyncMock()
    mock_page.title.return_value = "Just a moment..."
    mock_page.wait_for_function = AsyncMock()
    mock_page.wait_for_load_state = AsyncMock()

    await scraper._wait_for_cloudflare(mock_page, timeout=5000)

    mock_page.wait_for_function.assert_awaited_once()
    mock_page.wait_for_load_state.assert_awaited_once_with("domcontentloaded")


@pytest.mark.asyncio
async def test_wait_for_cloudflare_skips_normal_page(scraper):
    """Test that Cloudflare detection skips normal pages."""
    mock_page = AsyncMock()
    mock_page.title.return_value = "IT Jobs - Jobs.ps"
    mock_page.wait_for_function = AsyncMock()

    await scraper._wait_for_cloudflare(mock_page, timeout=5000)

    mock_page.wait_for_function.assert_not_awaited()


# --- Source name and URL tests ---


def test_scraper_base_url():
    """Test that the scraper has the correct base URL."""
    scraper = JobsPsScraper()
    assert scraper.BASE_URL == "https://www.jobs.ps/en/categories/it-jobs"


def test_scraper_source_name():
    """Test that the scraper source name is 'Jobs.ps'."""
    scraper = JobsPsScraper()
    assert scraper.SOURCE_NAME == "Jobs.ps"
