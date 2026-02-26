import os

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def get_config() -> dict:
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

    def __init__(self):
        self._config = None

    def _load(self):
        if self._config is None:
            self._config = get_config()

    @property
    def TELEGRAM_BOT_TOKEN(self) -> str:
        self._load()
        return self._config["TELEGRAM_BOT_TOKEN"]

    @property
    def TELEGRAM_CHANNEL_ID(self) -> str:
        self._load()
        return self._config["TELEGRAM_CHANNEL_ID"]

    @property
    def TARGET_CHANNELS(self) -> list[str]:
        """Comma-separated list of Telegram channel names to scrape."""
        self._load()
        raw = self._config["TARGET_CHANNELS"]
        return [ch.strip() for ch in raw.split(",") if ch.strip()]


_cfg = _Config()


# Module-level lazy access using __getattr__ (PEP 562).
# Modules can still do `from it_job_aggregator.config import TELEGRAM_BOT_TOKEN`
# but the value is only resolved when first accessed, not at import time.
def __getattr__(name: str):
    if name == "TELEGRAM_BOT_TOKEN":
        return _cfg.TELEGRAM_BOT_TOKEN
    if name == "TELEGRAM_CHANNEL_ID":
        return _cfg.TELEGRAM_CHANNEL_ID
    if name == "TARGET_CHANNELS":
        return _cfg.TARGET_CHANNELS
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
