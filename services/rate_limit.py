"""Rate limiting: Redis or in-memory with TTL. Key per user+action, count per window."""
import logging
import time
from typing import Optional

from config import get_config
from services.redis_client import (
    get_redis,
    redis_incr,
    redis_expire,
    redis_ttl,
)

logger = logging.getLogger(__name__)

# In-memory fallback: key -> (count, window_start)
_memory: dict[str, tuple[int, float]] = {}
_MEMORY_WINDOW = 60


def _memory_clean() -> None:
    now = time.monotonic()
    to_del = [k for k, (_, start) in _memory.items() if now - start > _MEMORY_WINDOW]
    for k in to_del:
        del _memory[k]


async def check_rate_limit(user_id: int, action: str, limit: int, window_seconds: int = 60) -> Optional[int]:
    """
    Increment counter for user_id+action. If over limit, return minutes to wait; else return None.
    """
    key = f"rate:{action}:{user_id}"
    if get_redis():
        try:
            count = await redis_incr(key)
            if count == 1:
                await redis_expire(key, window_seconds)
            if count > limit:
                ttl = await redis_ttl(key)
                return max(1, (ttl + 59) // 60)
            return None
        except Exception as e:
            logger.warning("Rate limit Redis: %s", e)
    # In-memory
    now = time.monotonic()
    if len(_memory) > 10000:
        _memory_clean()
    if key not in _memory:
        _memory[key] = (0, now)
    cnt, start = _memory[key]
    if now - start >= window_seconds:
        _memory[key] = (0, now)
        cnt, start = 0, now
    cnt += 1
    _memory[key] = (cnt, start)
    if cnt > limit:
        return max(1, int((window_seconds - (now - start) + 59) / 60))
    return None
