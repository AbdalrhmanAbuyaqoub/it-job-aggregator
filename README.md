# IT Job Aggregator

[![CI](https://github.com/AbdalrhmanAbuyaqoub/it-job-aggregator/actions/workflows/ci.yml/badge.svg)](https://github.com/AbdalrhmanAbuyaqoub/it-job-aggregator/actions/workflows/ci.yml)

A Telegram bot that aggregates IT job listings from multiple Palestinian job
boards — currently [jobs.ps](https://www.jobs.ps/en/categories/it-jobs) and
[foras.ps](https://foras.ps) — deduplicates via SQLite, sorts by posted date, and
posts new matches to [@palestineitjobs](https://t.me/palestineitjobs).

Built as an **SDET portfolio project** with a strong focus on test quality, CI/CD, and
production-grade architecture. The scraper registry pattern makes adding new sources
straightforward.

## Architecture

```
    ┌──────────────────────┐     ┌──────────────────────┐
    │  jobs.ps             │     │  foras.ps            │
    │  (HTML + Playwright) │     │  (REST API + aiohttp)│
    └─────────┬────────────┘     └─────────┬────────────┘
              │                            │
              ▼                            ▼
       JobsPsScraper              ForasPsScraper
              │                            │
              └────────────┬───────────────┘
                           │
                    Scraper Registry
                    (main.py iterates
                     all registered scrapers)
                           │
                           ▼
              sort_jobs_by_posted_date
              (stable sort — dated jobs first,
               undated jobs keep position)
                           │
                           ▼
                       Database
                  (SQLite link-based dedup)
                           │
                           ▼
                     JobFormatter
              (MarkdownV2 + deadline
               normalization)
                           │
                           ▼
                   send_job_posting
              (Telegram Bot API with
               exponential backoff)
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
| Browser Automation | Playwright (async, headless Chromium — Jobs.ps) |
| Anti-Detection | playwright-stealth |
| HTTP Client | aiohttp (async — Foras.ps REST API) |
| HTML Parsing | beautifulsoup4 |
| Data Validation | Pydantic (Job model with HttpUrl) |
| Database | sqlite3 (stdlib, link-based dedup) |
| Config | python-dotenv + PEP 562 lazy loading |
| Testing | pytest, pytest-asyncio, pytest-cov |
| Linting | ruff (lint + format) |
| Type Checking | mypy (strict mode) |
| Build System | hatchling (src-layout) |
| Containerization | Docker + Docker Compose |
| CI | GitHub Actions |

## Project Structure

```
src/it_job_aggregator/
├── main.py                  # Pipeline orchestrator + scraper registry + CLI
├── config.py                # Lazy-loaded config via PEP 562 __getattr__
├── models.py                # Pydantic Job model (with posted_date)
├── db.py                    # SQLite deduplication database (URL-normalized dedup)
├── formatter.py             # Telegram MarkdownV2 formatter (+ deadline normalization)
├── bot.py                   # Telegram Bot API sender with retry + session cleanup
├── utils.py                 # Shared utilities (date parsing with year-boundary fix)
└── scrapers/
    ├── base.py              # BaseScraper ABC (_retry helper, SOURCE_NAME, constants)
    ├── jobsps_scraper.py    # Scrapes jobs.ps with Playwright + BS4
    └── forasps_scraper.py   # Scrapes foras.ps via public REST API + aiohttp
tests/
├── conftest.py              # Shared fixtures + env var setup
├── test_bot.py              # Bot send, retries, backoff, session lifecycle
├── test_config.py           # Lazy loading, validation, defaults
├── test_db.py               # CRUD, duplicates, URL normalization, migration, schema
├── test_formatter.py        # Escaping, bold title, URL escaping, deadline normalization
├── test_main.py             # Pipeline integration, sorting, error handling, loop, CLI
├── test_models.py           # Pydantic validation, required/optional fields
├── test_scrapers.py         # Listing/detail parsing, pagination, Cloudflare, retries
├── test_forasps_scraper.py  # Foras.ps API responses, pagination, retries, incremental
├── test_base_scraper.py     # BaseScraper._retry() logic, backoff, error propagation
└── test_utils.py            # Date parsing, year-boundary rollback, edge cases
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

205 tests across 10 files with **96% code coverage**:

| File | Tests | Coverage |
|---|---|---|
| test_scrapers.py | 39 | Listing/detail parsing, pagination, Cloudflare timeout, incremental scraping |
| test_forasps_scraper.py | 31 | Foras.ps API responses, pagination, retries, incremental, error handling |
| test_main.py | 28 | Pipeline integration, registry, date sorting, error handling, run_loop, CLI |
| test_formatter.py | 28 | Escaping, bold title, URL escaping, deadline normalization, optional fields |
| test_models.py | 19 | Validation, required/optional fields, URL handling |
| test_db.py | 18 | CRUD, duplicates, URL normalization, context manager, migration, schema |
| test_config.py | 14 | Lazy loading, missing env vars, defaults, DB_PATH |
| test_base_scraper.py | 12 | _retry() backoff, max attempts, error propagation, logging |
| test_utils.py | 8 | Date parsing, year-boundary rollback, edge cases |
| test_bot.py | 8 | Success, retries, backoff, session lifecycle, delegation |

| Module | Coverage |
|---|---|
| formatter.py | 100% |
| models.py | 100% |
| scrapers/\_\_init\_\_.py | 100% |
| main.py | 99% |
| base.py | 97% |
| forasps_scraper.py | 97% |
| bot.py | 96% |
| db.py | 95% |
| config.py | 94% |
| jobsps_scraper.py | 93% |
| utils.py | 89% |

```bash
uv run pytest                                # run all tests
uv run pytest -v                             # verbose output
uv run pytest -k "test_escape_markdown"      # keyword match
uv run pytest --cov=it_job_aggregator        # run with coverage report
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
