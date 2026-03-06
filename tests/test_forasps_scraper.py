from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from it_job_aggregator.scrapers.forasps_scraper import ForasPsScraper

# --- Sample API response fixtures ---

SAMPLE_LISTING_RESPONSE = {
    "result": [
        {
            "id": "aaaa-bbbb-cccc-1111",
            "slugMapId": 2315,
            "nameEnglish": "Full Stack PHP Developer",
            "nameArabic": "مطور ويب",
            "descriptionEnglish": "<p>We are hiring...</p>",
            "descriptionArabic": "<p>نبحث عن...</p>",
            "categoryNameEnglish": "Jobs",
            "cityNameEnglish": "Ramallah and Al-Bireh",
            "endDate": "2026-03-09T00:00:00Z",
            "companyId": "comp-1111",
            "imagePath": "/images/job1.png",
            "skills": [],
            "isActive": True,
            "isFeatured": True,
        },
        {
            "id": "aaaa-bbbb-cccc-2222",
            "slugMapId": 2310,
            "nameEnglish": "Backend Developer",
            "nameArabic": "مطور خلفي",
            "descriptionEnglish": "<p>Backend position...</p>",
            "descriptionArabic": "<p>وظيفة خلفية...</p>",
            "categoryNameEnglish": "Jobs",
            "cityNameEnglish": "Gaza",
            "endDate": "2026-03-15T00:00:00Z",
            "companyId": "comp-2222",
            "imagePath": "/images/job2.png",
            "skills": [],
            "isActive": True,
            "isFeatured": False,
        },
    ],
    "totalRecords": 2,
    "returnRecords": 2,
}

SAMPLE_LISTING_RESPONSE_EMPTY = {
    "result": [],
    "totalRecords": 0,
    "returnRecords": 0,
}

SAMPLE_LISTING_RESPONSE_PAGE1 = {
    "result": [
        {
            "id": "page1-job-1111",
            "nameEnglish": "Page 1 Job",
            "cityNameEnglish": "Nablus",
            "endDate": "2026-04-01T00:00:00Z",
        },
    ],
    "totalRecords": 2,
    "returnRecords": 1,
}

SAMPLE_LISTING_RESPONSE_PAGE2 = {
    "result": [
        {
            "id": "page2-job-2222",
            "nameEnglish": "Page 2 Job",
            "cityNameEnglish": "Hebron",
            "endDate": "2026-04-10T00:00:00Z",
        },
    ],
    "totalRecords": 2,
    "returnRecords": 2,
}

SAMPLE_DETAIL_RESPONSE = {
    "info": [
        {
            "language": "en",
            "name": "Full Stack PHP Developer",
            "description": "<p>We are hiring a full stack developer...</p>",
        },
        {
            "language": "ar",
            "name": "مطور ويب",
            "description": "<p>نبحث عن مطور...</p>",
        },
    ],
    "companyInfo": [
        {"language": "en", "name": "Tech Solutions Ltd"},
        {"language": "ar", "name": "تك سولوشنز"},
    ],
    "cityInfo": [
        {"language": "en", "name": "Ramallah and Al-Bireh"},
    ],
    "categoryInfo": [
        {"language": "en", "name": "Jobs"},
    ],
    "specialtyInfo": [],
}

SAMPLE_DETAIL_RESPONSE_ARABIC_ONLY = {
    "info": [
        {
            "language": "ar",
            "name": "مطور خلفي",
            "description": "<p>وظيفة خلفية</p>",
        },
    ],
    "companyInfo": [
        {"language": "ar", "name": "شركة عربية"},
    ],
    "cityInfo": [],
    "categoryInfo": [],
    "specialtyInfo": [],
}

SAMPLE_DETAIL_RESPONSE_NO_COMPANY = {
    "info": [
        {
            "language": "en",
            "name": "Some Job",
            "description": "<p>Description</p>",
        },
    ],
    "companyInfo": [],
    "cityInfo": [],
    "categoryInfo": [],
    "specialtyInfo": [],
}


# --- Mock helpers ---


def _make_mock_response(json_data, status=200):
    """Create a mock aiohttp response."""
    mock_resp = AsyncMock()
    mock_resp.status = status
    mock_resp.json = AsyncMock(return_value=json_data)
    mock_resp.request_info = MagicMock()
    mock_resp.history = ()
    return mock_resp


def _make_mock_session(responses):
    """
    Create a mock aiohttp.ClientSession that returns responses in order.
    responses is a list of (method, json_data, status) tuples or (method, Exception) tuples.
    """
    mock_session = AsyncMock()
    response_iter = iter(responses)

    def _make_context_manager(method_name):
        def context_manager(*args, **kwargs):
            resp_spec = next(response_iter)
            cm = AsyncMock()
            if isinstance(resp_spec[1], Exception):
                cm.__aenter__.side_effect = resp_spec[1]
            else:
                mock_resp = _make_mock_response(
                    resp_spec[1], resp_spec[2] if len(resp_spec) > 2 else 200
                )
                cm.__aenter__.return_value = mock_resp
            cm.__aexit__.return_value = False
            return cm

        return context_manager

    mock_session.post = _make_context_manager("post")
    mock_session.get = _make_context_manager("get")

    return mock_session


# --- Scraper fixture ---


@pytest.fixture
def scraper():
    """Fixture providing a ForasPsScraper instance."""
    return ForasPsScraper()


# --- Source name tests ---


def test_scraper_source_name():
    """Test that the scraper source name is 'Foras.ps'."""
    scraper = ForasPsScraper()
    assert scraper.SOURCE_NAME == "Foras.ps"


# --- _extract_company_from_detail tests ---


def test_extract_company_english(scraper):
    """Test extracting the English company name from detail response."""
    result = scraper._extract_company_from_detail(SAMPLE_DETAIL_RESPONSE)
    assert result == "Tech Solutions Ltd"


def test_extract_company_arabic_fallback(scraper):
    """Test falling back to Arabic company name when English is not available."""
    result = scraper._extract_company_from_detail(SAMPLE_DETAIL_RESPONSE_ARABIC_ONLY)
    assert result == "شركة عربية"


def test_extract_company_empty_list(scraper):
    """Test that an empty companyInfo list returns None."""
    result = scraper._extract_company_from_detail(SAMPLE_DETAIL_RESPONSE_NO_COMPANY)
    assert result is None


def test_extract_company_missing_key(scraper):
    """Test that a detail response without companyInfo key returns None."""
    result = scraper._extract_company_from_detail({})
    assert result is None


def test_extract_company_blank_name(scraper):
    """Test that entries with blank names are skipped."""
    detail = {
        "companyInfo": [
            {"language": "en", "name": "  "},
            {"language": "ar", "name": "Real Company"},
        ]
    }
    result = scraper._extract_company_from_detail(detail)
    assert result == "Real Company"


# --- _build_job tests ---


def test_build_job_success(scraper):
    """Test building a Job from a listing item with company name."""
    item = SAMPLE_LISTING_RESPONSE["result"][0]
    job_url = "https://foras.ps/jobs/job-details/aaaa-bbbb-cccc-1111"

    job = scraper._build_job(item, job_url, company="Tech Solutions Ltd")

    assert job is not None
    assert job.title == "Full Stack PHP Developer"
    assert job.company == "Tech Solutions Ltd"
    assert str(job.link).rstrip("/") == job_url
    assert job.source == "Foras.ps"
    assert job.location == "Ramallah and Al-Bireh"
    assert job.deadline == "2026-03-09T00:00:00Z"


def test_build_job_no_company(scraper):
    """Test building a Job without a company name."""
    item = SAMPLE_LISTING_RESPONSE["result"][0]
    job_url = "https://foras.ps/jobs/job-details/aaaa-bbbb-cccc-1111"

    job = scraper._build_job(item, job_url, company=None)

    assert job is not None
    assert job.company is None


def test_build_job_arabic_title_fallback(scraper):
    """Test that Arabic title is used when English title is missing."""
    item = {
        "id": "test-id",
        "nameEnglish": "",
        "nameArabic": "مطور ويب",
        "cityNameEnglish": "Ramallah",
        "endDate": "2026-03-09T00:00:00Z",
    }
    job_url = "https://foras.ps/jobs/job-details/test-id"

    job = scraper._build_job(item, job_url, company=None)

    assert job is not None
    assert job.title == "مطور ويب"


def test_build_job_missing_title_returns_none(scraper):
    """Test that a listing item with no title returns None."""
    item = {
        "id": "no-title",
        "nameEnglish": "",
        "nameArabic": "",
        "cityNameEnglish": "Ramallah",
        "endDate": "2026-03-09T00:00:00Z",
    }
    job_url = "https://foras.ps/jobs/job-details/no-title"

    job = scraper._build_job(item, job_url, company=None)

    assert job is None


def test_build_job_missing_location(scraper):
    """Test building a Job when city is not provided."""
    item = {
        "id": "test-id",
        "nameEnglish": "Some Job",
        "cityNameEnglish": "",
        "endDate": "2026-03-09T00:00:00Z",
    }
    job_url = "https://foras.ps/jobs/job-details/test-id"

    job = scraper._build_job(item, job_url, company=None)

    assert job is not None
    assert job.location is None


def test_build_job_missing_deadline(scraper):
    """Test building a Job when endDate is not provided."""
    item = {
        "id": "test-id",
        "nameEnglish": "Some Job",
        "cityNameEnglish": "Ramallah",
        "endDate": "",
    }
    job_url = "https://foras.ps/jobs/job-details/test-id"

    job = scraper._build_job(item, job_url, company=None)

    assert job is not None
    assert job.deadline is None


# --- _fetch_listing_page tests ---


@pytest.mark.asyncio
async def test_fetch_listing_page_success(scraper):
    """Test successfully fetching a listing page."""
    mock_session = _make_mock_session(
        [
            ("post", SAMPLE_LISTING_RESPONSE),
        ]
    )

    result = await scraper._fetch_listing_page(
        mock_session, page=1, max_retries=1, initial_backoff=0
    )

    assert result is not None
    assert len(result["result"]) == 2
    assert result["totalRecords"] == 2


@pytest.mark.asyncio
async def test_fetch_listing_page_http_error(scraper):
    """Test that an HTTP error returns None after retries are exhausted."""
    mock_session = _make_mock_session(
        [
            ("post", {}, 500),
        ]
    )

    result = await scraper._fetch_listing_page(
        mock_session, page=1, max_retries=1, initial_backoff=0
    )

    assert result is None


@pytest.mark.asyncio
async def test_fetch_listing_page_retries_on_error(scraper):
    """Test that _fetch_listing_page retries on failure and succeeds."""
    mock_session = _make_mock_session(
        [
            ("post", {}, 500),
            ("post", SAMPLE_LISTING_RESPONSE),
        ]
    )

    with patch(
        "it_job_aggregator.scrapers.base.asyncio.sleep",
        new_callable=AsyncMock,
    ) as mock_sleep:
        result = await scraper._fetch_listing_page(
            mock_session, page=1, max_retries=2, initial_backoff=2
        )

    assert result is not None
    assert len(result["result"]) == 2
    mock_sleep.assert_awaited_once_with(2)


# --- _fetch_detail tests ---


@pytest.mark.asyncio
async def test_fetch_detail_success(scraper):
    """Test successfully fetching a detail page."""
    mock_session = _make_mock_session(
        [
            ("get", SAMPLE_DETAIL_RESPONSE),
        ]
    )

    result = await scraper._fetch_detail(
        mock_session, "aaaa-bbbb-cccc-1111", max_retries=1, initial_backoff=0
    )

    assert result is not None
    assert result["companyInfo"][0]["name"] == "Tech Solutions Ltd"


@pytest.mark.asyncio
async def test_fetch_detail_returns_none_on_failure(scraper):
    """Test that _fetch_detail returns None when all retries fail."""
    mock_session = _make_mock_session(
        [
            ("get", {}, 404),
        ]
    )

    result = await scraper._fetch_detail(mock_session, "bad-id", max_retries=1, initial_backoff=0)

    assert result is None


@pytest.mark.asyncio
async def test_fetch_detail_retries_with_backoff(scraper):
    """Test that _fetch_detail retries with exponential backoff."""
    mock_session = _make_mock_session(
        [
            ("get", {}, 500),
            ("get", {}, 500),
            ("get", SAMPLE_DETAIL_RESPONSE),
        ]
    )

    with patch(
        "it_job_aggregator.scrapers.base.asyncio.sleep",
        new_callable=AsyncMock,
    ) as mock_sleep:
        result = await scraper._fetch_detail(
            mock_session, "test-id", max_retries=3, initial_backoff=2
        )

    assert result is not None
    assert mock_sleep.await_count == 2
    mock_sleep.assert_any_await(2)  # First retry: 2 * (2^0) = 2
    mock_sleep.assert_any_await(4)  # Second retry: 2 * (2^1) = 4


# --- _fetch_company_name tests ---


@pytest.mark.asyncio
async def test_fetch_company_name_success(scraper):
    """Test fetching a company name from the detail endpoint."""
    mock_session = _make_mock_session(
        [
            ("get", SAMPLE_DETAIL_RESPONSE),
        ]
    )

    result = await scraper._fetch_company_name(
        mock_session, "aaaa-bbbb-cccc-1111", max_retries=1, initial_backoff=0
    )

    assert result == "Tech Solutions Ltd"


@pytest.mark.asyncio
async def test_fetch_company_name_returns_none_on_failure(scraper):
    """Test that _fetch_company_name returns None when the detail fetch fails."""
    mock_session = _make_mock_session(
        [
            ("get", {}, 500),
        ]
    )

    result = await scraper._fetch_company_name(
        mock_session, "bad-id", max_retries=1, initial_backoff=0
    )

    assert result is None


@pytest.mark.asyncio
async def test_fetch_company_name_no_company_info(scraper):
    """Test that _fetch_company_name returns None when detail has no company."""
    mock_session = _make_mock_session(
        [
            ("get", SAMPLE_DETAIL_RESPONSE_NO_COMPANY),
        ]
    )

    result = await scraper._fetch_company_name(
        mock_session, "some-id", max_retries=1, initial_backoff=0
    )

    assert result is None


# --- Full scrape integration tests ---


@pytest.mark.asyncio
async def test_scrape_full_flow():
    """Test the full scrape flow: listing -> detail -> Job objects."""
    scraper = ForasPsScraper()

    mock_session = _make_mock_session(
        [
            # Listing page 1
            ("post", SAMPLE_LISTING_RESPONSE),
            # Detail for job 1
            ("get", SAMPLE_DETAIL_RESPONSE),
            # Detail for job 2
            ("get", SAMPLE_DETAIL_RESPONSE_ARABIC_ONLY),
        ]
    )

    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__.return_value = mock_session
    mock_session_cm.__aexit__.return_value = False

    with (
        patch(
            "it_job_aggregator.scrapers.forasps_scraper.aiohttp.ClientSession",
            return_value=mock_session_cm,
        ),
        patch("it_job_aggregator.scrapers.forasps_scraper.asyncio.sleep", new_callable=AsyncMock),
    ):
        jobs = await scraper.scrape(max_retries=1, initial_backoff=0)

    assert len(jobs) == 2
    assert jobs[0].title == "Full Stack PHP Developer"
    assert jobs[0].company == "Tech Solutions Ltd"
    assert jobs[0].source == "Foras.ps"
    assert jobs[0].location == "Ramallah and Al-Bireh"
    assert jobs[0].deadline == "2026-03-09T00:00:00Z"

    assert jobs[1].title == "Backend Developer"
    assert jobs[1].company == "شركة عربية"
    assert jobs[1].location == "Gaza"


@pytest.mark.asyncio
async def test_scrape_empty_results():
    """Test that an empty listing response returns no jobs."""
    scraper = ForasPsScraper()

    mock_session = _make_mock_session(
        [
            ("post", SAMPLE_LISTING_RESPONSE_EMPTY),
        ]
    )

    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__.return_value = mock_session
    mock_session_cm.__aexit__.return_value = False

    with (
        patch(
            "it_job_aggregator.scrapers.forasps_scraper.aiohttp.ClientSession",
            return_value=mock_session_cm,
        ),
        patch("it_job_aggregator.scrapers.forasps_scraper.asyncio.sleep", new_callable=AsyncMock),
    ):
        jobs = await scraper.scrape(max_retries=1, initial_backoff=0)

    assert jobs == []


@pytest.mark.asyncio
async def test_scrape_pagination():
    """Test that the scraper paginates through multiple pages."""
    scraper = ForasPsScraper()

    mock_session = _make_mock_session(
        [
            # Listing page 1 (returnRecords < totalRecords => more pages)
            ("post", SAMPLE_LISTING_RESPONSE_PAGE1),
            # Detail for page 1 job
            ("get", SAMPLE_DETAIL_RESPONSE),
            # Listing page 2 (returnRecords == totalRecords => stop)
            ("post", SAMPLE_LISTING_RESPONSE_PAGE2),
            # Detail for page 2 job
            ("get", SAMPLE_DETAIL_RESPONSE_ARABIC_ONLY),
        ]
    )

    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__.return_value = mock_session
    mock_session_cm.__aexit__.return_value = False

    with (
        patch(
            "it_job_aggregator.scrapers.forasps_scraper.aiohttp.ClientSession",
            return_value=mock_session_cm,
        ),
        patch("it_job_aggregator.scrapers.forasps_scraper.asyncio.sleep", new_callable=AsyncMock),
    ):
        jobs = await scraper.scrape(max_retries=1, initial_backoff=0)

    assert len(jobs) == 2
    assert jobs[0].title == "Page 1 Job"
    assert jobs[1].title == "Page 2 Job"


@pytest.mark.asyncio
async def test_scrape_skips_known_jobs():
    """Test that the scraper skips jobs already known in the database."""
    scraper = ForasPsScraper()

    mock_session = _make_mock_session(
        [
            ("post", SAMPLE_LISTING_RESPONSE),
            # Only one detail fetch expected (second job is known)
            ("get", SAMPLE_DETAIL_RESPONSE),
        ]
    )

    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__.return_value = mock_session
    mock_session_cm.__aexit__.return_value = False

    mock_db = MagicMock()
    # Second job is already known
    mock_db.is_job_known.side_effect = lambda url: "cccc-2222" in url

    with (
        patch(
            "it_job_aggregator.scrapers.forasps_scraper.aiohttp.ClientSession",
            return_value=mock_session_cm,
        ),
        patch("it_job_aggregator.scrapers.forasps_scraper.asyncio.sleep", new_callable=AsyncMock),
    ):
        jobs = await scraper.scrape(db=mock_db, max_retries=1, initial_backoff=0)

    assert len(jobs) == 1
    assert jobs[0].title == "Full Stack PHP Developer"


@pytest.mark.asyncio
async def test_scrape_stops_pagination_when_all_known():
    """Test that pagination stops when all jobs on a page are already known."""
    scraper = ForasPsScraper()

    mock_session = _make_mock_session(
        [
            # Only listing page 1 fetched; no detail or page 2 expected
            ("post", SAMPLE_LISTING_RESPONSE),
        ]
    )

    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__.return_value = mock_session
    mock_session_cm.__aexit__.return_value = False

    mock_db = MagicMock()
    mock_db.is_job_known.return_value = True  # All jobs are known

    with (
        patch(
            "it_job_aggregator.scrapers.forasps_scraper.aiohttp.ClientSession",
            return_value=mock_session_cm,
        ),
        patch("it_job_aggregator.scrapers.forasps_scraper.asyncio.sleep", new_callable=AsyncMock),
    ):
        jobs = await scraper.scrape(db=mock_db, max_retries=1, initial_backoff=0)

    assert jobs == []


@pytest.mark.asyncio
async def test_scrape_listing_failure_stops():
    """Test that the scraper stops when the listing page fetch fails."""
    scraper = ForasPsScraper()

    mock_session = _make_mock_session(
        [
            ("post", {}, 500),
        ]
    )

    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__.return_value = mock_session
    mock_session_cm.__aexit__.return_value = False

    with (
        patch(
            "it_job_aggregator.scrapers.forasps_scraper.aiohttp.ClientSession",
            return_value=mock_session_cm,
        ),
        patch("it_job_aggregator.scrapers.forasps_scraper.asyncio.sleep", new_callable=AsyncMock),
    ):
        jobs = await scraper.scrape(max_retries=1, initial_backoff=0)

    assert jobs == []


@pytest.mark.asyncio
async def test_scrape_detail_failure_still_builds_job():
    """Test that a job is still created when the detail fetch fails (no company)."""
    scraper = ForasPsScraper()

    single_item_response = {
        "result": [
            {
                "id": "test-id-1234",
                "nameEnglish": "Test Job",
                "cityNameEnglish": "Ramallah",
                "endDate": "2026-04-01T00:00:00Z",
            },
        ],
        "totalRecords": 1,
        "returnRecords": 1,
    }

    mock_session = _make_mock_session(
        [
            ("post", single_item_response),
            # Detail fetch fails
            ("get", {}, 500),
        ]
    )

    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__.return_value = mock_session
    mock_session_cm.__aexit__.return_value = False

    with (
        patch(
            "it_job_aggregator.scrapers.forasps_scraper.aiohttp.ClientSession",
            return_value=mock_session_cm,
        ),
        patch("it_job_aggregator.scrapers.forasps_scraper.asyncio.sleep", new_callable=AsyncMock),
    ):
        jobs = await scraper.scrape(max_retries=1, initial_backoff=0)

    assert len(jobs) == 1
    assert jobs[0].title == "Test Job"
    assert jobs[0].company is None
    assert jobs[0].location == "Ramallah"


@pytest.mark.asyncio
async def test_scrape_skips_item_without_id():
    """Test that listing items without an 'id' field are skipped."""
    scraper = ForasPsScraper()

    response_with_no_id = {
        "result": [
            {
                "nameEnglish": "No ID Job",
                "cityNameEnglish": "Ramallah",
                "endDate": "2026-04-01T00:00:00Z",
            },
        ],
        "totalRecords": 1,
        "returnRecords": 1,
    }

    mock_session = _make_mock_session(
        [
            ("post", response_with_no_id),
        ]
    )

    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__.return_value = mock_session
    mock_session_cm.__aexit__.return_value = False

    with (
        patch(
            "it_job_aggregator.scrapers.forasps_scraper.aiohttp.ClientSession",
            return_value=mock_session_cm,
        ),
        patch("it_job_aggregator.scrapers.forasps_scraper.asyncio.sleep", new_callable=AsyncMock),
    ):
        jobs = await scraper.scrape(max_retries=1, initial_backoff=0)

    assert jobs == []


@pytest.mark.asyncio
async def test_scrape_does_not_stop_pagination_when_items_have_no_id():
    """Test that items with no id do not cause early pagination stop."""
    scraper = ForasPsScraper()

    # Page 1: single item with no id => should NOT trigger all_known_on_page
    page1_no_id = {
        "result": [
            {
                "nameEnglish": "No ID Job",
                "cityNameEnglish": "Ramallah",
                "endDate": "2026-04-01T00:00:00Z",
            },
        ],
        "totalRecords": 2,
        "returnRecords": 1,
    }

    # Page 2: normal item with id
    page2_with_id = {
        "result": [
            {
                "id": "valid-id-1234",
                "nameEnglish": "Valid Job",
                "cityNameEnglish": "Gaza",
                "endDate": "2026-04-15T00:00:00Z",
            },
        ],
        "totalRecords": 2,
        "returnRecords": 2,
    }

    mock_session = _make_mock_session(
        [
            ("post", page1_no_id),
            # Pagination continues to page 2
            ("post", page2_with_id),
            # Detail for page 2 job
            ("get", SAMPLE_DETAIL_RESPONSE),
        ]
    )

    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__.return_value = mock_session
    mock_session_cm.__aexit__.return_value = False

    with (
        patch(
            "it_job_aggregator.scrapers.forasps_scraper.aiohttp.ClientSession",
            return_value=mock_session_cm,
        ),
        patch("it_job_aggregator.scrapers.forasps_scraper.asyncio.sleep", new_callable=AsyncMock),
    ):
        jobs = await scraper.scrape(max_retries=1, initial_backoff=0)

    # Page 2 job should be found — pagination was NOT stopped by the no-id item on page 1
    assert len(jobs) == 1
    assert jobs[0].title == "Valid Job"


@pytest.mark.asyncio
async def test_scrape_without_db_returns_all():
    """Test that without a database, all jobs on the page are returned."""
    scraper = ForasPsScraper()

    mock_session = _make_mock_session(
        [
            ("post", SAMPLE_LISTING_RESPONSE),
            ("get", SAMPLE_DETAIL_RESPONSE),
            ("get", SAMPLE_DETAIL_RESPONSE_ARABIC_ONLY),
        ]
    )

    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__.return_value = mock_session
    mock_session_cm.__aexit__.return_value = False

    with (
        patch(
            "it_job_aggregator.scrapers.forasps_scraper.aiohttp.ClientSession",
            return_value=mock_session_cm,
        ),
        patch("it_job_aggregator.scrapers.forasps_scraper.asyncio.sleep", new_callable=AsyncMock),
    ):
        jobs = await scraper.scrape(db=None, max_retries=1, initial_backoff=0)

    assert len(jobs) == 2
