"""Optional Redis client for queue and cache. None if REDIS_URL not set."""
import json
import logging
from typing import Optional, Any

from config import get_config

logger = logging.getLogger(__name__)
_redis = None


def get_redis():
    """Return async Redis client or None."""
    global _redis
    if _redis is not None:
        return _redis
    config = get_config()
    if not config.redis_url:
        return None
    try:
        from redis.asyncio import Redis
        _redis = Redis.from_url(config.redis_url, decode_responses=True)
    except Exception as e:
        logger.warning("Redis init failed: %s", e)
        return None
    return _redis


async def redis_lpush(key: str, value: str) -> bool:
    r = get_redis()
    if not r:
        return False
    try:
        await r.lpush(key, value)
        return True
    except Exception as e:
        logger.warning("Redis LPUSH %s: %s", key, e)
        return False


async def redis_blpop(key: str, timeout: int = 5) -> Optional[str]:
    r = get_redis()
    if not r:
        return None
    try:
        result = await r.blpop(key, timeout=timeout)
        if result:
            return result[1]
        return None
    except Exception as e:
        logger.warning("Redis BLPOP %s: %s", key, e)
        return None


async def redis_set(key: str, value: str, ttl_seconds: int) -> bool:
    r = get_redis()
    if not r:
        return False
    try:
        await r.set(key, value, ex=ttl_seconds)
        return True
    except Exception as e:
        logger.warning("Redis SET %s: %s", key, e)
        return False


async def redis_get(key: str) -> Optional[str]:
    r = get_redis()
    if not r:
        return None
    try:
        return await r.get(key)
    except Exception as e:
        logger.warning("Redis GET %s: %s", key, e)
        return None


async def redis_delete(key: str) -> bool:
    r = get_redis()
    if not r:
        return False
    try:
        await r.delete(key)
        return True
    except Exception as e:
        logger.warning("Redis DELETE %s: %s", key, e)
        return False


async def redis_incr(key: str) -> int:
    r = get_redis()
    if not r:
        return 0
    try:
        return await r.incr(key)
    except Exception as e:
        logger.warning("Redis INCR %s: %s", key, e)
        return 0


async def redis_expire(key: str, seconds: int) -> bool:
    r = get_redis()
    if not r:
        return False
    try:
        return await r.expire(key, seconds)
    except Exception as e:
        logger.warning("Redis EXPIRE %s: %s", key, e)
        return False


async def redis_ttl(key: str) -> int:
    r = get_redis()
    if not r:
        return 0
    try:
        return await r.ttl(key)
    except Exception as e:
        return 0


DESTINY_QUEUE_KEY = "destiny_queue"
DESTINY_CACHE_PREFIX = "destiny:"
DESTINY_PROCESSED_PREFIX = "destiny_processed:"
PROCESSED_TTL = 86400  # 24h
