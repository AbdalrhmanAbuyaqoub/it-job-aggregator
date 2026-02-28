# IT Job Aggregator

[![CI](https://github.com/AbdalrhmanAbuyaqoub/it-job-aggregator/actions/workflows/ci.yml/badge.svg)](https://github.com/AbdalrhmanAbuyaqoub/it-job-aggregator/actions/workflows/ci.yml)

A Telegram bot that scrapes IT job listings from
[jobs.ps](https://www.jobs.ps/en/categories/it-jobs), deduplicates via SQLite, sorts by
posted date, and posts new matches to [@palestineitjobs](https://t.me/palestineitjobs).

Built as an **SDET portfolio project** with a strong focus on test quality, CI/CD, and
production-grade architecture.

## Architecture

```
jobs.ps/en/categories/it-jobs
        │
        ▼
   JobsPsScraper ────── Playwright headless browser + BeautifulSoup parsing
        │
        ▼
   sort_jobs_by_posted_date ── earliest posted date first
        │
        ▼
     Database ────────── SQLite deduplication (link-based)
        │
        ▼
    JobFormatter ─────── Telegram MarkdownV2 escaping + bold title
        │
        ▼
   send_job_posting ──── Telegram Bot API with exponential backoff
        │
        ▼
   @palestineitjobs
```

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 (requires >= 3.11) |
| Package Manager | [uv](https://github.com/astral-sh/uv) |
| Bot Framework | python-telegram-bot (async) |
| HTTP Client | httpx (async) |
| Browser Automation | Playwright (async, headless Chromium) |
| Anti-Detection | playwright-stealth |
| HTML Parsing | beautifulsoup4 |
| Data Validation | Pydantic (Job model with HttpUrl) |
| Database | sqlite3 (stdlib, link-based dedup) |
| Config | python-dotenv + PEP 562 lazy loading |
| Testing | pytest, pytest-asyncio, pytest-httpx |
| Linting | ruff (lint + format) |
| Type Checking | mypy (strict mode) |
| Build System | hatchling (src-layout) |
| Containerization | Docker + Docker Compose |
| CI | GitHub Actions |

## Project Structure

```
src/it_job_aggregator/
├── main.py                  # Pipeline orchestrator + CLI entry point
├── config.py                # Lazy-loaded config via PEP 562 __getattr__
├── models.py                # Pydantic Job model (with posted_date)
├── db.py                    # SQLite deduplication database
├── formatter.py             # Telegram MarkdownV2 formatter
├── bot.py                   # Telegram Bot API sender with retry
└── scrapers/
    ├── base.py              # BaseScraper ABC
    └── jobsps_scraper.py    # Scrapes jobs.ps with Playwright + BS4
tests/
├── conftest.py              # Shared fixtures + env var setup
├── test_bot.py              # Bot send, retries, backoff
├── test_config.py           # Lazy loading, validation, defaults
├── test_db.py               # CRUD, duplicates, migration, schema
├── test_formatter.py        # Escaping, bold title, posted date, field ordering
├── test_main.py             # Pipeline integration, sorting, loop, CLI
├── test_models.py           # Pydantic validation, optional fields
└── test_scrapers.py         # Listing/detail parsing, pagination, retries
```

## Setup

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv)

### Install

```bash
git clone https://github.com/AbdalrhmanAbuyaqoub/it-job-aggregator.git
cd it-job-aggregator
uv sync
```

### Configure

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Yes | Obtain from [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHANNEL_ID` | Yes | Channel `@username` or numeric ID. Bot must be a channel admin. |
| `SCRAPE_INTERVAL` | No | Minutes between scrape cycles (default: `30`) |
| `DB_PATH` | No | SQLite database file path (default: `jobs.db`) |

## Usage

### Run locally

```bash
# Continuous loop (default — scrapes every SCRAPE_INTERVAL minutes)
uv run it-job-aggregator

# Single run and exit
uv run it-job-aggregator --once

# Override interval to 15 minutes
uv run it-job-aggregator --interval 15
```

### Run with Docker

```bash
# Build and start in background
docker compose up -d --build

# View logs
docker compose logs -f

# Stop
docker compose down
```

The SQLite database is persisted in a Docker named volume (`bot-data`).

## Testing

124 tests across 8 files:

| File | Tests | Coverage |
|---|---|---|
| test_bot.py | 7 | Success, retries, backoff, empty/long messages |
| test_config.py | 14 | Lazy loading, missing env vars, defaults, DB_PATH |
| test_db.py | 12 | CRUD, duplicates, context manager, migration, schema |
| test_formatter.py | 18 | Escaping, bold title, empty line, posted date, field ordering |
| test_main.py | 23 | Pipeline integration, date sorting, run_loop, CLI |
| test_models.py | 19 | Validation, required/optional fields, URL handling |
| test_scrapers.py | 31 | Listing/detail parsing, pagination, retries, Cloudflare |

```bash
uv run pytest              # run all tests
uv run pytest -v           # verbose output
uv run pytest -k "test_escape_markdown"   # keyword match
```

## Code Quality

```bash
uv run ruff check src/ tests/    # lint
uv run ruff format src/ tests/   # auto-format
uv run mypy src/                 # strict type checking
```

All three checks run automatically on every push/PR via GitHub Actions.

## License

This project is for educational and portfolio purposes.
