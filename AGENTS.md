# AGENTS.md — Coding Agent Guidelines

## Project Overview

IT Job Aggregator: a Telegram bot that scrapes IT job listings from public Telegram channels,
filters by IT keywords (Arabic + English), deduplicates via SQLite, and posts to `@palestineitjobs`.
This is an **SDET portfolio project** — test quality and coverage are first-class concerns.

## Build & Run Commands

Package manager is **`uv`** (not pip/venv). All commands run from the project root.

```bash
uv sync                                          # install/sync deps (creates .venv)
uv run it-job-aggregator                         # run in continuous loop (default)
uv run it-job-aggregator --once                  # run pipeline once and exit
uv run it-job-aggregator --loop                  # run in continuous loop (explicit)
uv run it-job-aggregator --interval 15           # override interval to 15 minutes
uv run python -m it_job_aggregator.main          # alternative

uv run pytest                                    # run all tests
uv run pytest -v                                 # verbose output
uv run pytest tests/test_db.py                   # single file
uv run pytest tests/test_db.py::test_save_job_success  # single test
uv run pytest -k "test_escape_markdown"          # keyword match
uv run pytest -s                                 # show stdout

uv run ruff check src/ tests/                    # lint check
uv run ruff format src/ tests/                   # auto-format
uv run mypy src/                                 # strict type checking
```

## Project Structure

```
src/it_job_aggregator/       # Source package (src-layout, hatchling build)
├── main.py                  # Pipeline orchestrator + CLI entry point
├── config.py                # Lazy-loaded config via PEP 562 __getattr__
├── models.py                # Pydantic Job model
├── db.py                    # SQLite deduplication database
├── filters.py               # Keyword/regex IT job filter
├── formatter.py             # Telegram MarkdownV2 formatter
├── bot.py                   # Telegram Bot API sender with retry
└── scrapers/
    ├── base.py              # BaseScraper ABC
    └── telegram_scraper.py  # Scrapes t.me/s/<channel> web preview
tests/                       # pytest test suite (mirrors src structure)
├── conftest.py              # Shared fixtures + env var setup (runs before all imports)
├── test_db.py
├── test_filters.py
├── test_formatter.py
├── test_scrapers.py
├── test_models.py
└── test_bot.py
└── test_main.py
```

## Code Style

### Formatting
- 4-space indentation, no tabs. Max line length ~100 chars (soft).
- **Double quotes** for all strings — no single quotes anywhere.
- Linter: **ruff** (configured in `pyproject.toml`, enforced in CI).

### Imports
- Three groups separated by blank lines: **stdlib → third-party → local**.
- Local imports use the full package path: `from it_job_aggregator.models import Job`.
- Top-level imports only (no function-level imports unless avoiding circular deps).
- Relative imports only in `__init__.py` files (e.g., `from .telegram_scraper import TelegramScraper`).

### Type Annotations
- Type hints on all function signatures (parameters and return types).
- New code: `str | None` union syntax, `list[str]` lowercase builtins.
- Pydantic model fields: `Optional[str]` (Pydantic convention).
- Existing code may use `List` from `typing` — don't mix styles within a file.

### Naming Conventions
- Classes: `PascalCase` (`JobFilter`, `TelegramScraper`, `Database`).
- Functions/methods: `snake_case` (`save_job`, `is_it_job`, `format_job`).
- Constants: `UPPER_SNAKE_CASE` (`MAX_RETRIES`, `HTTP_TIMEOUT`, `FALSE_POSITIVE_DOMAINS`).
- Private: single underscore prefix (`_parse_message`, `_find_best_link`, `_conn`, `_Config`).
- Tests: `test_<what_is_being_tested>` — descriptive names, no `test_1` numbering.

### Error Handling
- Catch specific exceptions first (`sqlite3.IntegrityError`, `httpx.HTTPError`), then broad `Exception`.
- Log via `logging.getLogger(__name__)` — **never `print()`**.
- All log messages use **f-strings**: `logger.info(f"Scraped {count} jobs")`.
- `logging.basicConfig()` is called **only once** in `main.py`.
- Retry logic: exponential backoff `backoff = initial_backoff * (2 ** (attempt - 1))`.

### Async
- Scraping and bot operations are async (`async def`, `await`).
- Use `httpx.AsyncClient` for HTTP (not `requests`).
- Use `asyncio.sleep()` (never `time.sleep()` in async code).
- Entry point: `cli()` parses args, then `asyncio.run(run_pipeline())` or `asyncio.run(run_loop())`.

### Database
- `sqlite3` standard library only (not SQLAlchemy).
- `Database` class uses a single persistent `self._conn` connection.
- Supports context manager: `with Database() as db:`.
- In-memory databases use `":memory:"` — same persistent connection rule applies.

### Data Validation
- All job data flows through the `Job` Pydantic model.
- `HttpUrl` type for links — always cast with `str(job.link)` for SQLite or string comparisons.
- Pydantic `HttpUrl` may append a trailing `/` to bare domains — use `.rstrip("/")` when comparing.

### Configuration
- Environment variables loaded via `python-dotenv`.
- `config.py` uses PEP 562 lazy `__getattr__` — importing the module does NOT crash; accessing a value does.
- Never hardcode secrets. `.env` is gitignored.

## Testing Conventions

### Framework & Plugins
- **pytest** + **pytest-asyncio** (auto mode) + **pytest-httpx**.
- `asyncio_mode = "auto"` in `pyproject.toml`.
- Async tests use `@pytest.mark.asyncio` decorator for clarity (even though auto mode makes it optional).

### Test Organization
- `conftest.py` sets env vars (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`, `TARGET_CHANNELS`) **before** any source imports, with `# noqa: E402` on the post-env import.
- Shared fixtures (`sample_job`, `sample_job_no_company`) live in `conftest.py`.
- Each test file has a local fixture for its SUT (e.g., `db` fixture yields an in-memory `Database`).
- All tests are module-level functions — no test classes.
- `# --- New tests ---` comment separates original tests from later additions.

### Mocking Patterns
- HTTP: `httpx_mock` fixture from pytest-httpx (`httpx_mock.add_response()`).
- Telegram Bot: `patch("it_job_aggregator.bot.Bot")` with `AsyncMock`.
- Sleep/backoff: `patch("...asyncio.sleep", new_callable=AsyncMock)`.
- Config: `os.environ` in conftest, or `monkeypatch.setenv()` / `monkeypatch.delenv()`.
- Always use full module path in `patch()` targets.
- Use `patch` as context manager (not decorator).

### Assertions
- Boolean returns: `assert db.save_job(job) is True` / `is False` (identity, not truthiness).
- HttpUrl comparisons: `str(job.link)` or `.rstrip("/")`.
- Errors: `pytest.raises(ExceptionType, match="...")`.
- Multiple inputs: `@pytest.mark.parametrize` (see `test_filters.py`).
- Async mocks: `assert_awaited_once_with`, `assert_any_await`, `await_count`.

### Test Docstrings
- Every test function **must** have a one-line docstring explaining what it verifies.

### HTML Test Fixtures
- Defined as module-level `SAMPLE_HTML` constants in `test_scrapers.py`.
- Separate constants for each scenario (`SAMPLE_HTML`, `SAMPLE_HTML_FALSE_LINK`, etc.).

## Important Gotchas

1. **`sqlite3.connect(":memory:")`** creates a new DB each call — use a persistent `self._conn`.
2. **`lstrip("www.")`** strips characters, not a prefix — use `removeprefix("www.")`.
3. **Telegram MarkdownV2** requires escaping `` _*[]()~`>#+-=|{}.!\ `` but NOT forward slashes.
4. **Unicode stylized text** (𝗗𝗲𝘃𝗲𝗹𝗼𝗽𝗲𝗿) needs `unicodedata.normalize("NFKD", text)` before regex.
5. **The keyword `"it"`** causes massive false positives — use `"information technology"` instead.
6. **Telegram auto-links** `VB.NET`, `ASP.NET`, `ADO.NET` as URLs — filter in `_is_valid_job_link()`.
7. **`config.py` imports** must not trigger validation — the lazy `__getattr__` pattern prevents this.
8. **Pydantic `HttpUrl`** may add trailing `/` — always use `str(job.link)` and `.rstrip("/")` in tests.
