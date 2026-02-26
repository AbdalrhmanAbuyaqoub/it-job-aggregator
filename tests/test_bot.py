from unittest.mock import AsyncMock, patch

import pytest

from it_job_aggregator.bot import send_job_posting


@pytest.mark.asyncio
async def test_send_job_posting_success():
    """Test that send_job_posting attempts to send a message using the Telegram Bot API."""
    test_message = "Test job posting"

    with patch("it_job_aggregator.bot.Bot") as mock_bot_class:
        mock_bot_instance = AsyncMock()
        mock_bot_class.return_value = mock_bot_instance

        await send_job_posting(test_message)

        from it_job_aggregator.config import TELEGRAM_BOT_TOKEN

        mock_bot_class.assert_called_once_with(token=TELEGRAM_BOT_TOKEN)

        from telegram.constants import ParseMode

        from it_job_aggregator.config import TELEGRAM_CHANNEL_ID

        mock_bot_instance.send_message.assert_awaited_once_with(
            chat_id=TELEGRAM_CHANNEL_ID,
            text=test_message,
            parse_mode=ParseMode.MARKDOWN_V2,
        )


@pytest.mark.asyncio
async def test_send_job_posting_failure_after_retries():
    """Test that send_job_posting raises an exception after all retries are exhausted."""
    test_message = "Test job posting"

    with patch("it_job_aggregator.bot.Bot") as mock_bot_class:
        mock_bot_instance = AsyncMock()
        mock_bot_instance.send_message.side_effect = Exception("Telegram API Error")
        mock_bot_class.return_value = mock_bot_instance

        with patch("it_job_aggregator.bot.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(Exception, match="Telegram API Error"):
                await send_job_posting(test_message, max_retries=3, initial_backoff=0)

        # Should have been called 3 times (initial + 2 retries)
        assert mock_bot_instance.send_message.await_count == 3


@pytest.mark.asyncio
async def test_send_job_posting_succeeds_on_retry():
    """Test that send_job_posting succeeds after a transient failure."""
    test_message = "Test job posting"

    with patch("it_job_aggregator.bot.Bot") as mock_bot_class:
        mock_bot_instance = AsyncMock()
        # First call fails, second call succeeds
        mock_bot_instance.send_message.side_effect = [
            Exception("Connection error"),
            None,  # success
        ]
        mock_bot_class.return_value = mock_bot_instance

        with patch("it_job_aggregator.bot.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await send_job_posting(test_message, max_retries=3, initial_backoff=2)

        # Should have been called twice
        assert mock_bot_instance.send_message.await_count == 2
        # Should have slept once with initial backoff
        mock_sleep.assert_awaited_once_with(2)


@pytest.mark.asyncio
async def test_send_job_posting_exponential_backoff():
    """Test that retry backoff increases exponentially."""
    test_message = "Test job posting"

    with patch("it_job_aggregator.bot.Bot") as mock_bot_class:
        mock_bot_instance = AsyncMock()
        # Fail twice, succeed on third
        mock_bot_instance.send_message.side_effect = [
            Exception("Error 1"),
            Exception("Error 2"),
            None,  # success
        ]
        mock_bot_class.return_value = mock_bot_instance

        with patch("it_job_aggregator.bot.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await send_job_posting(test_message, max_retries=3, initial_backoff=2)

        assert mock_bot_instance.send_message.await_count == 3
        # Backoff should be: 2s (2*2^0), then 4s (2*2^1)
        assert mock_sleep.await_count == 2
        mock_sleep.assert_any_await(2)
        mock_sleep.assert_any_await(4)


@pytest.mark.asyncio
async def test_send_job_posting_single_attempt_no_retry():
    """Test with max_retries=1 (no retries, single attempt)."""
    test_message = "Test job posting"

    with patch("it_job_aggregator.bot.Bot") as mock_bot_class:
        mock_bot_instance = AsyncMock()
        mock_bot_instance.send_message.side_effect = Exception("API Error")
        mock_bot_class.return_value = mock_bot_instance

        with patch("it_job_aggregator.bot.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(Exception, match="API Error"):
                await send_job_posting(test_message, max_retries=1, initial_backoff=0)

        # Only one attempt, no retries
        assert mock_bot_instance.send_message.await_count == 1
        mock_sleep.assert_not_awaited()


# --- New tests ---


@pytest.mark.asyncio
async def test_send_job_posting_empty_message():
    """Test that an empty string message is still sent without error."""
    with patch("it_job_aggregator.bot.Bot") as mock_bot_class:
        mock_bot_instance = AsyncMock()
        mock_bot_class.return_value = mock_bot_instance

        await send_job_posting("")

        mock_bot_instance.send_message.assert_awaited_once()
        call_kwargs = mock_bot_instance.send_message.call_args.kwargs
        assert call_kwargs["text"] == ""


@pytest.mark.asyncio
async def test_send_job_posting_long_message():
    """Test that a very long message (>4096 chars) is passed through to the API as-is."""
    long_message = "x" * 5000  # Exceeds Telegram's 4096-char limit

    with patch("it_job_aggregator.bot.Bot") as mock_bot_class:
        mock_bot_instance = AsyncMock()
        mock_bot_class.return_value = mock_bot_instance

        # The bot module itself does not truncate — it sends as-is.
        # If Telegram rejects it, the retry logic handles the error.
        await send_job_posting(long_message)

        call_kwargs = mock_bot_instance.send_message.call_args.kwargs
        assert call_kwargs["text"] == long_message
        assert len(call_kwargs["text"]) == 5000
