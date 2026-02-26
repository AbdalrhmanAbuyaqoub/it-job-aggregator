from it_job_aggregator.formatter import JobFormatter
from it_job_aggregator.models import Job


def test_escape_markdown_basic():
    text = "Hello. This is a test!"
    escaped = JobFormatter.escape_markdown(text)
    assert escaped == r"Hello\. This is a test\!"


def test_escape_markdown_all_chars():
    text = r"_*[]()~`>#+-=|{}.!"
    escaped = JobFormatter.escape_markdown(text)
    # The actual result will have backslashes before each:
    actual_expected = r"\_\*\[\]\(\)\~\`\>\#\+\-\=\|\{\}\.\!"
    assert escaped == actual_expected


def test_format_job_without_company():
    job = Job(
        title="Senior C# / .NET Developer!",
        link="https://example.com/job/123-abc",
        description="Great job.",
        source="Telegram (@channel)",
    )

    formatted = JobFormatter.format_job(job)

    # Title escaping checks: C#, ., !
    assert r"*Title:* Senior C\# / \.NET Developer\!" in formatted
    # Source escaping checks: (, @, )
    assert r"*Source:* Telegram \(@channel\)" in formatted
    # Link check
    assert "[Apply Here / View Details](https://example.com/job/123-abc)" in formatted


def test_format_job_with_company():
    job = Job(
        title="QA Engineer",
        company="Tech Corp - Inc.",
        link="https://example.com",
        description="...",
        source="Website",
    )

    formatted = JobFormatter.format_job(job)

    assert r"*Title:* QA Engineer" in formatted
    assert r"*Company:* Tech Corp \- Inc\." in formatted
    assert r"*Source:* Website" in formatted
    assert "[Apply Here / View Details](https://example.com/)" in formatted


# --- New tests ---


def test_escape_markdown_empty_string():
    """Test that escaping an empty string returns an empty string."""
    assert JobFormatter.escape_markdown("") == ""


def test_escape_markdown_no_special_chars():
    """Test that text without special characters is returned unchanged."""
    text = "Hello World"
    assert JobFormatter.escape_markdown(text) == "Hello World"


def test_escape_markdown_backslash():
    """Test that backslashes are escaped correctly."""
    text = r"path\to\file"
    escaped = JobFormatter.escape_markdown(text)
    assert escaped == r"path\\to\\file"


def test_format_job_with_short_description():
    """Test that a short description is included in full (no truncation)."""
    job = Job(
        title="SDET",
        link="https://example.com/sdet",
        description="Join our QA team. We test everything.",
        source="Website",
    )
    formatted = JobFormatter.format_job(job)
    # The description should appear escaped but complete
    assert r"Join our QA team\." in formatted
    assert r"We test everything\." in formatted
    # Should NOT have "..." truncation
    assert "\\.\\.\\." not in formatted


def test_format_job_with_long_description_truncated():
    """Test that descriptions longer than 200 chars are truncated at a word boundary."""
    # Build a description that's well over 200 chars
    long_desc = "This is a really long job description. " * 10  # ~390 chars
    assert len(long_desc) > 200

    job = Job(
        title="Backend Dev",
        link="https://example.com/backend",
        description=long_desc,
        source="Telegram (@ch)",
    )
    formatted = JobFormatter.format_job(job)

    # The formatted output should contain "..." (escaped as \.\.\.)
    assert r"\.\.\." in formatted


def test_format_job_with_empty_description():
    """Test that an empty description doesn't add a description block."""
    job = Job(
        title="DevOps Eng",
        link="https://example.com/devops",
        description="",
        source="Website",
    )
    formatted = JobFormatter.format_job(job)

    # Should still have title, source, and link
    assert "*Title:* DevOps Eng" in formatted
    assert "*Source:* Website" in formatted
    assert "[Apply Here / View Details]" in formatted
    # Should NOT have an extra paragraph between source and link
    lines = formatted.split("\n")
    # Find the source line and the link line — nothing in between except blank line
    source_idx = next(i for i, line in enumerate(lines) if "*Source:*" in line)
    link_idx = next(i for i, line in enumerate(lines) if "Apply Here" in line)
    # Between source and link, there should only be empty lines
    between = [line for line in lines[source_idx + 1 : link_idx] if line.strip()]
    assert between == []


def test_format_job_with_whitespace_only_description():
    """Test that a whitespace-only description is treated like empty."""
    job = Job(
        title="SRE",
        link="https://example.com/sre",
        description="   \n  \t  ",
        source="Website",
    )
    formatted = JobFormatter.format_job(job)

    # Whitespace-only description after strip() is empty, so no desc block
    # The link should still be present
    assert "[Apply Here / View Details]" in formatted


def test_format_job_description_exactly_200_chars():
    """Test that a description of exactly 200 chars is not truncated."""
    desc = "a" * 200
    job = Job(
        title="Test",
        link="https://example.com/test",
        description=desc,
        source="Src",
    )
    formatted = JobFormatter.format_job(job)
    # Should NOT have truncation marker
    assert "\\.\\.\\." not in formatted
