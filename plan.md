# IT Job Aggregator Bot - Project Plan

## Project Overview
A Python bot that scrapes IT job listings from multiple sources (LinkedIn, Indeed, Glassdoor, Telegram channels, company career pages), filters them by keywords and seniority level, removes duplicates, and posts them to a Telegram channel.

**Core Focus:** Demonstrating QA/SDET skills (Test Pyramid, CI/CD, production-grade testing practices).

## Tech Stack
- **Language:** Python 3.11+
- **Dependency Management & Tooling:** `uv`
- **Bot Framework:** `python-telegram-bot` (async)
- **Testing:** `pytest`, `pytest-asyncio`, `unittest.mock`
- **Data Storage:** SQLite (for deduplication - Phase 2+)
- **Deployment:** Docker (Phase 3+)

---

## Phase 1: Foundation & Basic Bot
**Goal:** Set up the project structure following modern best practices and create a working Telegram bot capable of posting messages to a channel.

### Steps Completed:
1. **Initialize Project:** Scaffolded the project structure using `uv`.
2. **Add Dependencies:** Added `python-telegram-bot`, `python-dotenv`, `pytest`, `pytest-asyncio`.
3. **Environment Configuration:** Created `.env.example` and `config.py` for environment variables.
4. **Core Bot Logic:** Created `bot.py` to send async messages to a Telegram channel.
5. **Testing:** Created unit tests in `test_bot.py` using `pytest` and `unittest.mock`.
6. **Documentation:** Created this plan and the `README.md`.

---

## Future Phases (High-Level)

### Phase 2: Scraping & Deduplication
- Implement scrapers for initial sources (e.g., specific Telegram channels or an easy web source).
- Set up SQLite database for storing seen jobs.
- Implement deduplication logic based on job title, company, and link.
- **Testing Focus:** Integration tests with a test SQLite database, unit tests for parsing logic.

### Phase 3: Filtering & Formatting
- Implement keyword and seniority level filtering.
- Create a standard Markdown template for Telegram messages.
- **Testing Focus:** Unit tests for filtering logic and message formatting.

### Phase 4: CI/CD & Deployment
- Dockerize the application.
- Set up GitHub Actions for running `pytest`, linting (`ruff`), and type checking (`mypy`) on every push.
- **Testing Focus:** E2E testing (running the bot in a containerized environment).