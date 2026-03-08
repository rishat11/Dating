"""Tests for config.Config and get_config."""
import pytest

from config import Config, get_config


def test_from_env_defaults(env_config):
    cfg = Config.from_env()
    assert cfg.bot_token == "test-token-123"
    assert cfg.database_url == "sqlite+aiosqlite:///:memory:"
    assert cfg.redis_url is None
    assert cfg.deepseek_api_key is None
    assert cfg.daily_likes_limit == 10
    assert cfg.destiny_index_cache_ttl == 3600
    assert cfg.destiny_freeze_hours == 3
    assert cfg.save_index_silence_hours == 6
    assert cfg.chat_messages_per_minute == 30
    assert cfg.feed_requests_per_minute == 20
    assert cfg.messages_retention_months == 12
    assert cfg.webhook_path is None
    assert cfg.webhook_host is None


def test_from_env_custom(env_config, monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost/1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-secret")
    monkeypatch.setenv("DAILY_LIKES_LIMIT", "20")
    monkeypatch.setenv("WEBHOOK_PATH", "/webhook")
    monkeypatch.setenv("WEBHOOK_HOST", "https://example.com")
    cfg = Config.from_env()
    assert cfg.redis_url == "redis://localhost/1"
    assert cfg.deepseek_api_key == "sk-secret"
    assert cfg.daily_likes_limit == 20
    assert cfg.webhook_path == "/webhook"
    assert cfg.webhook_host == "https://example.com"


def test_config_frozen(env_config):
    from dataclasses import FrozenInstanceError
    cfg = Config.from_env()
    with pytest.raises(FrozenInstanceError):
        cfg.bot_token = "other"


def test_get_config(env_config):
    cfg = get_config()
    assert isinstance(cfg, Config)
    assert cfg.bot_token == "test-token-123"
