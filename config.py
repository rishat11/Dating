"""Configuration from environment."""
import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    """Bot and app configuration."""

    bot_token: str
    database_url: str
    redis_url: Optional[str]
    deepseek_api_key: Optional[str]

    # Limits
    daily_likes_limit: int
    destiny_index_cache_ttl: int
    destiny_freeze_hours: int
    save_index_silence_hours: int
    # Rate limiting (per user)
    chat_messages_per_minute: int
    feed_requests_per_minute: int
    # Message retention (months)
    messages_retention_months: int

    # Webhook (optional, for production)
    webhook_path: Optional[str] = None
    webhook_host: Optional[str] = None

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            bot_token=os.environ["BOT_TOKEN"],
            database_url=os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./dating.db"),
            redis_url=os.environ.get("REDIS_URL") or None,
            deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY") or None,
            daily_likes_limit=int(os.environ.get("DAILY_LIKES_LIMIT", "10")),
            destiny_index_cache_ttl=int(os.environ.get("DESTINY_INDEX_CACHE_TTL", "3600")),
            destiny_freeze_hours=int(os.environ.get("DESTINY_FREEZE_HOURS", "3")),
            save_index_silence_hours=int(os.environ.get("SAVE_INDEX_SILENCE_HOURS", "6")),
            chat_messages_per_minute=int(os.environ.get("CHAT_MESSAGES_PER_MINUTE", "30")),
            feed_requests_per_minute=int(os.environ.get("FEED_REQUESTS_PER_MINUTE", "20")),
            messages_retention_months=int(os.environ.get("MESSAGES_RETENTION_MONTHS", "12")),
            webhook_path=os.environ.get("WEBHOOK_PATH"),
            webhook_host=os.environ.get("WEBHOOK_HOST"),
        )


def get_config() -> Config:
    return Config.from_env()
