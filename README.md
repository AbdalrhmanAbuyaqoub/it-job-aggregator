# IT Job Aggregator

[![CI](https://github.com/AbdalrhmanAbuyaqoub/it-job-aggregator/actions/workflows/ci.yml/badge.svg)](https://github.com/AbdalrhmanAbuyaqoub/it-job-aggregator/actions/workflows/ci.yml)

An IT job aggregator bot that scrapes job listings from multiple sources, filters them, removes duplicates, and posts them to a Telegram channel. 

This project is built with a strong focus on QA/SDET practices, including comprehensive testing (unit, integration, E2E), CI/CD, and production-grade architecture.

## Current Progress: Phase 3 (Filtering & Formatting)

Currently, the project has established the core structure, SQLite deduplication, and a Telegram scraper. Phase 3 added:
- **Keyword Filtering:** `JobFilter` accurately detects English and Arabic IT job postings while ignoring unrelated jobs using regex pattern matching.
- **MarkdownV2 Formatting:** `JobFormatter` correctly escapes reserved Telegram MarkdownV2 characters to present jobs cleanly and safely in the channel.
- **Orchestration:** A `main.py` entry point that runs the full pipeline: Scrape -> Filter -> Deduplicate -> Format -> Send to Telegram.

## Setup Instructions

1. **Prerequisites:** 
   - Python 3.11+
   - [uv](https://github.com/astral-sh/uv) (Extremely fast Python package installer and resolver)

2. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd it_job_aggregator
   ```

3. **Install dependencies:**
   `uv` will automatically create the virtual environment and install everything based on `pyproject.toml`.
   ```bash
   uv sync
   ```

4. **Environment Variables:**
   Create a `.env` file in the root directory based on `.env.example`:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and fill in your actual Telegram Bot Token and Channel ID.
   - `TELEGRAM_BOT_TOKEN`: Obtain from [@BotFather](https://t.me/BotFather) on Telegram.
   - `TELEGRAM_CHANNEL_ID`: The `@username` of your public channel, or the ID of your private channel (e.g., `-1001234567890`). Make sure to add the bot as an administrator to the channel.

## Running the Bot Manually

To test the bot manually and send a test message to your configured channel:

```bash
PYTHONPATH=src uv run python -m it_job_aggregator.bot
```

## Running Tests

Tests are written using `pytest` and use `unittest.mock` to avoid making actual network requests to the Telegram API during testing.

```bash
uv run pytest
```
