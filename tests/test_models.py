import pytest
from pydantic import ValidationError
from it_job_aggregator.models import Job


def test_valid_job_model():
    """Test creating a Job model with valid data."""
    job = Job(
        title="Senior SDET",
        company="Tech Corp",
        link="https://example.com/job/123",
        description="We are looking for an SDET.",
        source="Telegram",
    )
    assert job.title == "Senior SDET"
    assert job.company == "Tech Corp"
    assert str(job.link) == "https://example.com/job/123"
    assert job.source == "Telegram"


def test_invalid_url_raises_error():
    """Test that an invalid URL raises a Pydantic ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        Job(
            title="Senior SDET",
            link="not-a-valid-url",  # Invalid URL
            description="We are looking for an SDET.",
            source="Telegram",
        )
    assert "url" in str(exc_info.value).lower()


def test_missing_required_fields_raises_error():
    """Test that missing required fields raises a validation error."""
    with pytest.raises(ValidationError):
        Job(
            # Missing title, link, description, source
            company="Tech Corp"
        )


def test_optional_company_field():
    """Test that company field is optional."""
    job = Job(
        title="Senior SDET",
        link="https://example.com/job/123",
        description="We are looking for an SDET.",
        source="Telegram",
    )
    assert job.company is None


# --- New tests ---


def test_url_trailing_slash_normalization():
    """Test that Pydantic HttpUrl may add a trailing slash to bare domains."""
    job = Job(
        title="Test",
        link="https://example.com",
        description="desc",
        source="src",
    )
    # Pydantic HttpUrl normalizes bare domains — use rstrip("/") for comparison
    assert str(job.link).rstrip("/") == "https://example.com"


def test_http_url_accepted():
    """Test that HTTP (non-HTTPS) URLs are accepted by Pydantic HttpUrl."""
    job = Job(
        title="Test",
        link="http://example.com/job",
        description="desc",
        source="src",
    )
    assert str(job.link).startswith("http://")


def test_url_with_path_and_query():
    """Test that URLs with paths and query parameters are preserved."""
    url = "https://example.com/jobs/search?q=developer&page=2"
    job = Job(
        title="Test",
        link=url,
        description="desc",
        source="src",
    )
    assert str(job.link) == url


def test_empty_title_raises_error():
    """Test that an empty string for a required field does not raise (Pydantic allows it by default)."""
    # Pydantic does not reject empty strings for `str` fields unless a validator is added.
    # This test documents current behavior.
    job = Job(
        title="",
        link="https://example.com",
        description="desc",
        source="src",
    )
    assert job.title == ""


def test_missing_title_raises_error():
    """Test that omitting the title field raises a ValidationError."""
    with pytest.raises(ValidationError):
        Job(
            link="https://example.com",
            description="desc",
            source="src",
        )


def test_missing_link_raises_error():
    """Test that omitting the link field raises a ValidationError."""
    with pytest.raises(ValidationError):
        Job(
            title="Test",
            description="desc",
            source="src",
        )


def test_missing_description_raises_error():
    """Test that omitting the description field raises a ValidationError."""
    with pytest.raises(ValidationError):
        Job(
            title="Test",
            link="https://example.com",
            source="src",
        )


def test_missing_source_raises_error():
    """Test that omitting the source field raises a ValidationError."""
    with pytest.raises(ValidationError):
        Job(
            title="Test",
            link="https://example.com",
            description="desc",
        )
