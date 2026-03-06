import re
from datetime import datetime

from it_job_aggregator.models import Job


class JobFormatter:
    """
    Formats a Job object into a Telegram MarkdownV2 compatible string.
    """

    # Characters that must be escaped in MarkdownV2 outside of code blocks/links
    # See: https://core.telegram.org/bots/api#markdownv2-style
    ESCAPE_CHARS = r"_*[]()~`>#+-=|{}.!\\"

    @classmethod
    def escape_markdown(cls, text: str) -> str:
        """
        Escapes reserved characters in Telegram MarkdownV2.
        """
        if not text:
            return ""
        # We need to add a backslash before any character in ESCAPE_CHARS
        return re.sub(f"([{re.escape(cls.ESCAPE_CHARS)}])", r"\\\1", text)

    @staticmethod
    def escape_url(url: str) -> str:
        """
        Escapes characters in a URL for use inside MarkdownV2 inline links.

        Per the Telegram Bot API docs, inside the ``(url)`` portion of
        ``[text](url)``, only ``)`` and ``\\`` must be escaped.
        """
        return url.replace("\\", "\\\\").replace(")", "\\)")

    # Deadline formats accepted by the normalizer, tried in order.
    _DEADLINE_FORMATS = (
        "%Y-%m-%dT%H:%M:%SZ",  # ISO 8601 with Z   (e.g. "2026-03-09T00:00:00Z")
        "%Y-%m-%dT%H:%M:%S",  # ISO 8601 no Z      (e.g. "2026-03-09T14:30:00")
        "%Y-%m-%d",  # Date only           (e.g. "2026-04-03")
        "%b %d, %Y",  # Already formatted   (e.g. "Mar 09, 2026")
    )

    @classmethod
    def _format_deadline(cls, raw: str) -> str:
        """
        Normalize a deadline string into a human-readable format.

        Tries several common date formats and converts to ``"Mar 09, 2026"``
        style.  Returns the original string unchanged if none of the known
        formats match.
        """
        for fmt in cls._DEADLINE_FORMATS:
            try:
                dt = datetime.strptime(raw, fmt)
                return dt.strftime("%b %d, %Y")
            except ValueError:
                continue
        return raw

    @classmethod
    def format_job(cls, job: Job) -> str:
        """
        Formats the job into a structured Markdown message with all available fields.
        """
        title = cls.escape_markdown(job.title)
        source = cls.escape_markdown(job.source)

        message = "🚀 *New IT Job Posting*\n\n"
        message += f"*Title:* *{title}*\n\n"

        if job.company:
            company = cls.escape_markdown(job.company)
            message += f"*Company:* {company}\n"

        if job.location:
            location = cls.escape_markdown(job.location)
            message += f"*Location:* {location}\n"

        if job.position_level:
            level = cls.escape_markdown(job.position_level)
            message += f"*Position Level:* {level}\n"

        if job.experience:
            experience = cls.escape_markdown(job.experience)
            message += f"*Experience:* {experience}\n"

        if job.deadline:
            deadline = cls.escape_markdown(cls._format_deadline(job.deadline))
            message += f"*Deadline:* {deadline}\n"

        if job.posted_date:
            posted_date = cls.escape_markdown(job.posted_date)
            message += f"*Posted Date:* {posted_date}\n"

        message += f"*Source:* {source}\n\n"

        # Link URL needs only ) and \ escaped inside the href part of Markdown link.
        escaped_url = cls.escape_url(str(job.link))
        message += f"[Apply Here / View Details]({escaped_url})"

        return message
