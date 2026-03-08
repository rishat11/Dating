"""Idempotency by update_id; optional DB session injection."""
import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

logger = logging.getLogger(__name__)

# Processed update_ids (in-memory; for Redis use redis set with TTL)
_processed_updates: set[int] = set()
_MAX_CACHE = 50000


class IdempotencyMiddleware(BaseMiddleware):
    """Skip duplicate updates by update_id (Telegram may redeliver)."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if not isinstance(event, Update):
            return await handler(event, data)
        uid = event.update_id
        if uid in _processed_updates:
            logger.debug("Skip duplicate update_id=%s", uid)
            return None
        _processed_updates.add(uid)
        if len(_processed_updates) > _MAX_CACHE:
            _processed_updates.clear()
        return await handler(event, data)
