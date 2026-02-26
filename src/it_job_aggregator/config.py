import os

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def get_config() -> dict[str, str]:
    """
    Load and validate configuration from environment variables.
    Called lazily to avoid crashing on import.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    channel_id = os.getenv("TELEGRAM_CHANNEL_ID", "")

    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set in the environment variables.")
    if not channel_id:
        raise ValueError("TELEGRAM_CHANNEL_ID is not set in the environment variables.")

    return {
        "TELEGRAM_BOT_TOKEN": token,
        "TELEGRAM_CHANNEL_ID": channel_id,
        "TARGET_CHANNELS": os.getenv("TARGET_CHANNELS", "jobspsco"),
    }


class _Config:
    """Lazy configuration that only validates when values are actually accessed."""

    def __init__(self) -> None:
        self._config: dict[str, str] | None = None

    def _load(self) -> None:
        if self._config is None:
            self._config = get_config()

    @property
    def TELEGRAM_BOT_TOKEN(self) -> str:
        self._load()
        assert self._config is not None
        return self._config["TELEGRAM_BOT_TOKEN"]

    @property
    def TELEGRAM_CHANNEL_ID(self) -> str:
        self._load()
        assert self._config is not None
        return self._config["TELEGRAM_CHANNEL_ID"]

    @property
    def TARGET_CHANNELS(self) -> list[str]:
        """Comma-separated list of Telegram channel names to scrape."""
        self._load()
        assert self._config is not None
        raw = self._config["TARGET_CHANNELS"]
        return [ch.strip() for ch in raw.split(",") if ch.strip()]


_cfg = _Config()

# Module-level type declarations for mypy.
# These are NOT assigned at module load time — the actual values come from __getattr__ below.
# This pattern lets `from config import TELEGRAM_BOT_TOKEN` have the correct type.
TELEGRAM_BOT_TOKEN: str
TELEGRAM_CHANNEL_ID: str
TARGET_CHANNELS: list[str]


# Module-level lazy access using __getattr__ (PEP 562).
# Modules can still do `from it_job_aggregator.config import TELEGRAM_BOT_TOKEN`
# but the value is only resolved when first accessed, not at import time.
def __getattr__(name: str) -> str | list[str]:
    if name == "TELEGRAM_BOT_TOKEN":
        return _cfg.TELEGRAM_BOT_TOKEN
    if name == "TELEGRAM_CHANNEL_ID":
        return _cfg.TELEGRAM_CHANNEL_ID
    if name == "TARGET_CHANNELS":
        return _cfg.TARGET_CHANNELS
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
