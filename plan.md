# IT Job Aggregator Bot - Project Plan

## Project Overview
A Python bot that scrapes IT job listings from public Telegram channels (starting with
`jobspsco` — a Palestinian job board), filters them by Arabic and English IT keywords,
removes duplicates via SQLite, and posts new matches to `@palestineitjobs`.

**Core Focus:** Demonstrating QA/SDET skills (test pyramid, CI/CD, production-grade testing).

## Tech Stack
- **Language:** Python 3.12 (requires >= 3.11)
- **Dependency Management:** `uv`
- **Bot Framework:** `python-telegram-bot` (async)
- **HTTP Client:** `httpx` (async)
- **HTML Parsing:** `beautifulsoup4`
- **Data Validation:** `pydantic` (Job model with `HttpUrl`)
- **Data Storage:** `sqlite3` (standard library, link-based deduplication)
- **Config:** `python-dotenv` + lazy PEP 562 `__getattr__` loading
- **Testing:** `pytest`, `pytest-asyncio`, `pytest-httpx`, `unittest.mock`
- **Build System:** `hatchling` (src-layout)
- **Deployment:** Docker + GitHub Actions (Phase 4 — not yet implemented)

---

## Phase 1: Foundation & Basic Bot ✅
**Goal:** Project structure, config, Telegram bot capable of posting messages.

### Completed:
- Scaffolded src-layout project with `uv` and `hatchling` build system
- CLI entry point: `uv run it-job-aggregator`
- `config.py` with lazy loading (PEP 562 `__getattr__`) — import doesn't crash without env vars
- `bot.py` with async message sending and exponential backoff retry logic
- `models.py` with Pydantic `Job` model (`HttpUrl` for links)
- `.env.example`, `.gitignore` (excludes `.env`, `*.db`, cache dirs)
- Unit tests for bot (success, retries, backoff, single attempt)

---

## Phase 2: Scraping & Deduplication ✅
**Goal:** Scrape job listings from Telegram channels, store in SQLite to prevent re-posting.

### Completed:
- `TelegramScraper` — scrapes `t.me/s/<channel>` web preview HTML
  - Configurable target channels via `TARGET_CHANNELS` env var
  - HTTP timeout (15s), User-Agent header, retry with exponential backoff
  - Channel name normalization (`@channel`, `t.me/channel`, bare name)
  - False-positive link filtering (`VB.NET`, `ASP.NET`, `ADO.NET` auto-linked by Telegram)
  - Fallback to message permalink when no valid external link found
  - `removeprefix("www.")` (not `lstrip`)
- `BaseScraper` ABC for future scraper implementations
- `Database` class — single persistent `sqlite3` connection, context manager, `close()`
  - Deduplication via `UNIQUE` constraint on `link` column
  - `created_at` auto-timestamp
- Tests: scraper parsing, HTTP errors, retries, false-positive links, empty pages,
  DB save/duplicate/context manager/close/timestamp

---

## Phase 3: Filtering & Formatting ✅
**Goal:** Identify IT jobs from raw scraped messages, format for Telegram posting.

### Completed:
- `JobFilter` — regex-based keyword matching (not LLM — deterministic and testable)
  - 30 English keywords (developer, engineer, qa, sdet, devops, cloud, aws, docker, etc.)
  - 13 Arabic keywords (مطور, مبرمج, برمجيات, هندسة, تكنولوجيا, etc.)
  - Unicode NFKD normalization for stylized text (𝗗𝗲𝘃𝗲𝗹𝗼𝗽𝗲𝗿 → Developer)
  - Word boundary matching for English; substring matching for Arabic
  - Avoided `"it"` keyword (massive false positives) — uses `"information technology"` instead
- `JobFormatter` — Telegram MarkdownV2 formatting
  - Escapes all required special characters (`_*[]()~\`>#+-=|{}.!\\`)
  - Description snippet (first 200 chars, truncated at word boundary)
  - Conditional company display
- `main.py` pipeline orchestrator — scrape → filter → deduplicate → format → send
  - Detailed logging counters (scraped, filtered, duplicates, posted, failed)
  - Graceful error handling (one failed send doesn't stop the pipeline)
- Tests: 36 parametrized filter cases (Arabic, English, Unicode, false positives, edge cases),
  formatter escaping/truncation/edge cases, full pipeline integration tests

### Current Test Coverage: **124 tests across 9 files, all passing**
| File | Tests | What's covered |
|------|-------|----------------|
| test_bot.py | 7 | Success, retries, backoff, empty/long messages |
| test_config.py | 16 | Lazy loading, missing env vars, comma parsing, defaults, SCRAPE_INTERVAL |
| test_db.py | 9 | CRUD, duplicates, context manager, close, timestamps |
| test_filters.py | 36 | English/Arabic/Unicode keywords, false positives, edge cases |
| test_formatter.py | 11 | Escaping, description truncation, edge cases |
| test_main.py | 16 | Pipeline integration, run_loop, graceful shutdown, CLI args |
| test_models.py | 12 | Validation, required fields, URL handling |
| test_scrapers.py | 13 | Parsing, HTTP errors, retries, false links, normalization |
| conftest.py | — | Shared fixtures, env var setup |

---

## Phase 4: CI/CD & Deployment (Next)
**Goal:** Automated quality gates, containerized deployment, linting, type checking.

### Tasks:
1. **Linting with ruff** ✅
   - Add `ruff` to dev dependencies
   - Configure rules in `pyproject.toml` (select, ignore, line-length)
   - Fix any existing violations
   - Enforce double quotes, import ordering, unused imports

2. **Type checking with mypy** ✅
   - Add `mypy` to dev dependencies
   - Configure `mypy` in `pyproject.toml` (strict mode or incremental)
   - Add type stubs if needed (`types-beautifulsoup4`)
   - Fix type errors (e.g., `HttpUrl` vs `str` in scraper)

3. **GitHub Actions CI pipeline** ✅
   - Run on push/PR to `main`
   - Steps: install with `uv`, run `ruff check`, run `mypy`, run `pytest`
   - Fail fast on any step failure
   - Badge in README

4. **Loop execution with graceful shutdown** ✅
   - `SCRAPE_INTERVAL` config (env var, default 30 min, validated > 0)
   - `argparse` CLI: `--once` (single run), `--loop` (continuous, default), `--interval N` (override)
   - `run_loop()` with `asyncio.Event` shutdown + `SIGINT`/`SIGTERM` signal handlers
   - Pipeline errors logged but don't crash the loop
   - 16 new tests (5 config + 11 main)

5. **Dockerize** ✅
   - `Dockerfile` based on `python:3.12-slim` with multi-stage dependency caching
   - Install `uv` via `COPY --from=ghcr.io/astral-sh/uv:latest`, sync deps with `--frozen`
   - Non-root `appuser` for security
   - Entry point: `uv run it-job-aggregator`
   - `.dockerignore` for `.env`, `*.db`, `.venv`, tests, docs, caches
   - `docker-compose.yml` with `.env` file, `unless-stopped` restart, named volume for DB persistence
   - Added `DB_PATH` config option (env var, default `jobs.db`) for Docker volume mount

6. **README update** (deferred)
   - Remove old PYTHONPATH references
   - Add CI badge, Docker usage, test count
   - Architecture diagram or description

---

## Phase 5: Manual Deployment
**Goal:** Deploy the bot on a home server using Docker Compose.

### Tasks:
1. Copy `docker-compose.yml` and `.env` to the home server
2. Build and start: `sudo docker compose up -d --build`
3. Enable Docker on boot: `sudo systemctl enable docker`
4. Update workflow: `git pull && sudo docker compose up -d --build`

---

## Future Ideas (Beyond Phase 5)
- Automated deployment (GHCR + Watchtower — auto-deploy on push to main)
- Additional scraper sources (other Telegram channels, job boards)
- Job categorization (frontend, backend, QA, DevOps, etc.)
- Duplicate detection improvements (fuzzy matching on title + company, not just link)
- Admin commands via Telegram bot (pause, resume, add channel)
- Metrics/stats endpoint (jobs posted per day, top keywords)
