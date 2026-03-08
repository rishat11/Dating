"""Pytest fixtures and configuration."""
import pytest


@pytest.fixture
def env_config(monkeypatch):
    """Set minimal env vars for Config.from_env (BOT_TOKEN required)."""
    monkeypatch.setenv("BOT_TOKEN", "test-token-123")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("DAILY_LIKES_LIMIT", "10")
    monkeypatch.setenv("DESTINY_INDEX_CACHE_TTL", "3600")
    monkeypatch.setenv("DESTINY_FREEZE_HOURS", "3")
    monkeypatch.setenv("SAVE_INDEX_SILENCE_HOURS", "6")
    monkeypatch.setenv("CHAT_MESSAGES_PER_MINUTE", "30")
    monkeypatch.setenv("FEED_REQUESTS_PER_MINUTE", "20")
    monkeypatch.setenv("MESSAGES_RETENTION_MONTHS", "12")
    # Clear optional so they're not from real env
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("WEBHOOK_PATH", raising=False)
    monkeypatch.delenv("WEBHOOK_HOST", raising=False)
