import asyncio
import logging

from telegram import Bot
from telegram.constants import ParseMode

from it_job_aggregator.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
INITIAL_BACKOFF = 2  # seconds


async def send_job_posting(
    message: str,
    max_retries: int = MAX_RETRIES,
    initial_backoff: float = INITIAL_BACKOFF,
) -> None:
    """
    Send a message to the configured Telegram channel with retry logic.

    Retries on transient errors (connection errors, timeouts, server errors)
    using exponential backoff.
    """
    bot = Bot(token=TELEGRAM_BOT_TOKEN)

    for attempt in range(1, max_retries + 1):
        try:
            await bot.send_message(
                chat_id=TELEGRAM_CHANNEL_ID,
                text=message,
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            logger.info("Message sent successfully.")
            return
        except Exception as e:
            if attempt == max_retries:
                logger.error(f"Failed to send message after {max_retries} attempts: {e}")
                raise
            backoff = initial_backoff * (2 ** (attempt - 1))
            logger.warning(
                f"Attempt {attempt}/{max_retries} failed: {e}. Retrying in {backoff}s..."
            )
            await asyncio.sleep(backoff)


async def main():
    """
    Main entry point for testing the bot manually.
    """
    test_message = "🚀 *Test Message*\\n\\nThis is a test message from the IT Job Aggregator Bot\\."
    await send_job_posting(test_message)


if __name__ == "__main__":
    asyncio.run(main())
