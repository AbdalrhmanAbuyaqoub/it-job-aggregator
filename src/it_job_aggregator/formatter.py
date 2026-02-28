import re

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
            deadline = cls.escape_markdown(job.deadline)
            message += f"*Deadline:* {deadline}\n"

        if job.posted_date:
            posted_date = cls.escape_markdown(job.posted_date)
            message += f"*Posted Date:* {posted_date}\n"

        message += f"*Source:* {source}\n\n"

        # Link URL does not need escaping inside the href part of Markdown link,
        # but the text part does. However, we'll just provide a hardcoded text.
        message += f"[Apply Here / View Details]({str(job.link)})"

        return message
