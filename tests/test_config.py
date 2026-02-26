import pytest

# NOTE: conftest.py already sets TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID,
# TARGET_CHANNELS in os.environ before any source imports. These tests use
# monkeypatch to override/remove env vars for specific scenarios.


def test_import_config_does_not_crash():
    """Test that importing config module does not raise even if env vars exist."""
    import it_job_aggregator.config  # noqa: F401

    # If we got here, import succeeded without crashing


def test_access_bot_token_returns_string():
    """Test that accessing TELEGRAM_BOT_TOKEN returns the env var value."""
    from it_job_aggregator.config import TELEGRAM_BOT_TOKEN

    assert isinstance(TELEGRAM_BOT_TOKEN, str)
    assert len(TELEGRAM_BOT_TOKEN) > 0


def test_access_channel_id_returns_string():
    """Test that accessing TELEGRAM_CHANNEL_ID returns the env var value."""
    from it_job_aggregator.config import TELEGRAM_CHANNEL_ID

    assert isinstance(TELEGRAM_CHANNEL_ID, str)
    assert len(TELEGRAM_CHANNEL_ID) > 0


def test_target_channels_returns_list():
    """Test that TARGET_CHANNELS is parsed as a list of channel names."""
    from it_job_aggregator.config import TARGET_CHANNELS

    assert isinstance(TARGET_CHANNELS, list)
    assert len(TARGET_CHANNELS) > 0
    assert all(isinstance(ch, str) for ch in TARGET_CHANNELS)


def test_target_channels_comma_separated(monkeypatch):
    """Test that comma-separated TARGET_CHANNELS are split into a list."""
    monkeypatch.setenv("TARGET_CHANNELS", "channel1, channel2, channel3")

    # Force reload of config by creating a fresh _Config instance
    from it_job_aggregator.config import _Config

    cfg = _Config()
    channels = cfg.TARGET_CHANNELS
    assert channels == ["channel1", "channel2", "channel3"]


def test_target_channels_single_value(monkeypatch):
    """Test that a single channel name without commas returns a one-element list."""
    monkeypatch.setenv("TARGET_CHANNELS", "jobspsco")

    from it_job_aggregator.config import _Config

    cfg = _Config()
    channels = cfg.TARGET_CHANNELS
    assert channels == ["jobspsco"]


def test_missing_bot_token_raises_on_access(monkeypatch):
    """Test that accessing config raises ValueError when TELEGRAM_BOT_TOKEN is missing."""
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    from it_job_aggregator.config import _Config

    cfg = _Config()
    with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
        _ = cfg.TELEGRAM_BOT_TOKEN


def test_missing_channel_id_raises_on_access(monkeypatch):
    """Test that accessing config raises ValueError when TELEGRAM_CHANNEL_ID is missing."""
    monkeypatch.delenv("TELEGRAM_CHANNEL_ID", raising=False)

    from it_job_aggregator.config import _Config

    cfg = _Config()
    with pytest.raises(ValueError, match="TELEGRAM_CHANNEL_ID"):
        _ = cfg.TELEGRAM_CHANNEL_ID


def test_config_lazy_loads_only_once(monkeypatch):
    """Test that _Config only calls get_config() once (caches result)."""
    from it_job_aggregator.config import _Config

    cfg = _Config()
    assert cfg._config is None  # Not loaded yet

    _ = cfg.TELEGRAM_BOT_TOKEN  # Triggers load
    assert cfg._config is not None  # Now loaded

    first_config = cfg._config

    _ = cfg.TELEGRAM_CHANNEL_ID  # Should reuse cached config
    assert cfg._config is first_config  # Same object, not reloaded


def test_module_getattr_unknown_attribute():
    """Test that accessing an unknown attribute on the config module raises AttributeError."""
    import it_job_aggregator.config as config_module

    with pytest.raises(AttributeError, match="NONEXISTENT"):
        _ = config_module.NONEXISTENT


def test_target_channels_default_when_unset(monkeypatch):
    """Test that TARGET_CHANNELS defaults to 'jobspsco' when env var is not set."""
    monkeypatch.delenv("TARGET_CHANNELS", raising=False)

    from it_job_aggregator.config import _Config

    cfg = _Config()
    channels = cfg.TARGET_CHANNELS
    assert channels == ["jobspsco"]
