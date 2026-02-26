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
        Formats the job into a structured Markdown message.
        """
        title = cls.escape_markdown(job.title)
        source = cls.escape_markdown(job.source)

        message = "🚀 *New IT Job Posting*\n\n"
        message += f"*Title:* {title}\n"

        if job.company:
            company = cls.escape_markdown(job.company)
            message += f"*Company:* {company}\n"

        message += f"*Source:* {source}\n\n"

        # Add a truncated description snippet if available
        if job.description:
            # Take first 200 chars, truncate at last word boundary
            desc = job.description.strip()
            if len(desc) > 200:
                desc = desc[:200].rsplit(" ", 1)[0] + "..."
            message += f"{cls.escape_markdown(desc)}\n\n"

        # Link URL does not need escaping inside the href part of Markdown link,
        # but the text part does. However, we'll just provide a hardcoded text.
        # Format: [Apply Here](URL)
        # Note: the url itself doesn't need escaping in MarkdownV2
        # format [text](url)
        # However, some Telegram clients are buggy if the URL has unescaped parentheses,
        # but standard URL characters are usually fine. We'll leave the url raw inside the ().
        message += f"[Apply Here / View Details]({str(job.link)})"

        return message
