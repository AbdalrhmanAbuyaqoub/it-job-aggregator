from it_job_aggregator.formatter import JobFormatter
from it_job_aggregator.models import Job


def test_escape_markdown_basic():
    """Test that special characters are escaped with backslashes."""
    text = "Hello. This is a test!"
    escaped = JobFormatter.escape_markdown(text)
    assert escaped == r"Hello\. This is a test\!"


def test_escape_markdown_all_chars():
    """Test that all MarkdownV2 special characters are escaped."""
    text = r"_*[]()~`>#+-=|{}.!"
    escaped = JobFormatter.escape_markdown(text)
    actual_expected = r"\_\*\[\]\(\)\~\`\>\#\+\-\=\|\{\}\.\!"
    assert escaped == actual_expected


def test_format_job_without_company():
    """Test formatting a job that has no company field."""
    job = Job(
        title="Senior C# / .NET Developer!",
        link="https://example.com/job/123-abc",
        description="Great job.",
        source="Jobs.ps",
    )

    formatted = JobFormatter.format_job(job)

    # Title escaping checks: C#, ., !
    assert r"*Title:* *Senior C\# / \.NET Developer\!*" in formatted
    # Source escaping checks
    assert r"*Source:* Jobs\.ps" in formatted
    # Link check
    assert "[Apply Here / View Details](https://example.com/job/123-abc)" in formatted
    # Company should NOT be present
    assert "*Company:*" not in formatted


def test_format_job_with_company():
    """Test formatting a job that includes company field."""
    job = Job(
        title="QA Engineer",
        company="Tech Corp - Inc.",
        link="https://example.com",
        description="...",
        source="Jobs.ps",
    )

    formatted = JobFormatter.format_job(job)

    assert r"*Title:* *QA Engineer*" in formatted
    assert r"*Company:* Tech Corp \- Inc\." in formatted
    assert r"*Source:* Jobs\.ps" in formatted
    assert "[Apply Here / View Details](https://example.com/)" in formatted


def test_format_job_with_all_fields():
    """Test formatting a job with all optional metadata fields populated."""
    job = Job(
        title="Software Engineer",
        company="Tech Corp",
        link="https://example.com/job/1",
        description="A great job.",
        source="Jobs.ps",
        position_level="Mid-Level",
        location="Ramallah",
        deadline="2026-03-24",
        experience="3 Years",
        posted_date="24, Feb",
    )

    formatted = JobFormatter.format_job(job)

    assert r"*Title:* *Software Engineer*" in formatted
    assert r"*Company:* Tech Corp" in formatted
    assert r"*Location:* Ramallah" in formatted
    assert r"*Position Level:* Mid\-Level" in formatted
    assert r"*Experience:* 3 Years" in formatted
    assert r"*Deadline:* 2026\-03\-24" in formatted
    assert "*Posted Date:* 24, Feb" in formatted
    assert r"*Source:* Jobs\.ps" in formatted
    assert "[Apply Here / View Details](https://example.com/job/1)" in formatted


def test_format_job_with_no_optional_fields():
    """Test formatting a job with no optional metadata fields."""
    job = Job(
        title="DevOps Engineer",
        link="https://example.com/devops",
        description="Cloud stuff.",
        source="Jobs.ps",
    )

    formatted = JobFormatter.format_job(job)

    assert "*Title:* *DevOps Engineer*" in formatted
    assert "*Company:*" not in formatted
    assert "*Location:*" not in formatted
    assert "*Position Level:*" not in formatted
    assert "*Experience:*" not in formatted
    assert "*Deadline:*" not in formatted
    assert "*Posted Date:*" not in formatted
    assert r"*Source:* Jobs\.ps" in formatted
    assert "[Apply Here / View Details]" in formatted


def test_format_job_with_partial_fields():
    """Test formatting a job with only some optional metadata fields."""
    job = Job(
        title="SDET",
        company="Startup Inc",
        link="https://example.com/sdet",
        description="Join our QA team.",
        source="Jobs.ps",
        location="Gaza",
        experience="2 Years",
    )

    formatted = JobFormatter.format_job(job)

    assert r"*Title:* *SDET*" in formatted
    assert r"*Company:* Startup Inc" in formatted
    assert r"*Location:* Gaza" in formatted
    assert r"*Experience:* 2 Years" in formatted
    # These should NOT be present
    assert "*Position Level:*" not in formatted
    assert "*Deadline:*" not in formatted


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


def test_format_job_special_chars_in_location():
    """Test that special characters in location are escaped."""
    job = Job(
        title="Test",
        link="https://example.com/test",
        description="desc",
        source="Jobs.ps",
        location="Ramallah (West Bank)",
    )
    formatted = JobFormatter.format_job(job)
    assert r"*Location:* Ramallah \(West Bank\)" in formatted


def test_format_job_special_chars_in_deadline():
    """Test that special characters in deadline (dashes) are escaped."""
    job = Job(
        title="Test",
        link="https://example.com/test",
        description="desc",
        source="Jobs.ps",
        deadline="2026-04-15",
    )
    formatted = JobFormatter.format_job(job)
    assert r"*Deadline:* 2026\-04\-15" in formatted


def test_format_job_field_ordering():
    """Test that fields appear in the expected order in the formatted message."""
    job = Job(
        title="Software Engineer",
        company="Tech Corp",
        link="https://example.com/job/1",
        description="desc",
        source="Jobs.ps",
        position_level="Senior",
        location="Ramallah",
        deadline="2026-03-24",
        experience="5 Years",
        posted_date="24, Feb",
    )
    formatted = JobFormatter.format_job(job)

    # Find positions of each field in the output
    title_pos = formatted.index("*Title:*")
    company_pos = formatted.index("*Company:*")
    location_pos = formatted.index("*Location:*")
    level_pos = formatted.index("*Position Level:*")
    exp_pos = formatted.index("*Experience:*")
    deadline_pos = formatted.index("*Deadline:*")
    posted_date_pos = formatted.index("*Posted Date:*")
    source_pos = formatted.index("*Source:*")
    link_pos = formatted.index("[Apply Here")

    assert title_pos < company_pos < location_pos < level_pos
    assert level_pos < exp_pos < deadline_pos < posted_date_pos < source_pos < link_pos


def test_format_job_contains_emoji_header():
    """Test that formatted output starts with the rocket emoji header."""
    job = Job(
        title="Test",
        link="https://example.com/test",
        description="desc",
        source="Jobs.ps",
    )
    formatted = JobFormatter.format_job(job)
    assert formatted.startswith("\U0001f680 *New IT Job Posting*")


def test_format_job_bold_title():
    """Test that the title text itself is wrapped in bold markers."""
    job = Job(
        title="Software Engineer",
        link="https://example.com/test",
        description="desc",
        source="Jobs.ps",
    )
    formatted = JobFormatter.format_job(job)
    assert "*Title:* *Software Engineer*" in formatted


def test_format_job_empty_line_after_title():
    """Test that there is an empty line (double newline) after the title line."""
    job = Job(
        title="Software Engineer",
        company="Tech Corp",
        link="https://example.com/test",
        description="desc",
        source="Jobs.ps",
    )
    formatted = JobFormatter.format_job(job)
    # Title line should be followed by \n\n (empty line) before company
    assert "*Title:* *Software Engineer*\n\n*Company:*" in formatted


def test_format_job_posted_date_displayed():
    """Test that posted_date is shown when present."""
    job = Job(
        title="Test",
        link="https://example.com/test",
        description="desc",
        source="Jobs.ps",
        posted_date="24, Feb",
    )
    formatted = JobFormatter.format_job(job)
    assert "*Posted Date:* 24, Feb" in formatted


def test_format_job_posted_date_not_displayed_when_none():
    """Test that Posted Date line is absent when posted_date is None."""
    job = Job(
        title="Test",
        link="https://example.com/test",
        description="desc",
        source="Jobs.ps",
    )
    formatted = JobFormatter.format_job(job)
    assert "*Posted Date:*" not in formatted
