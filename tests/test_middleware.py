"""Tests for bot.IdempotencyMiddleware."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from aiogram.types import Update
from bot.middleware import IdempotencyMiddleware


@pytest.fixture
def middleware():
    return IdempotencyMiddleware()


@pytest.fixture
def handler():
    return AsyncMock(return_value="ok")


@pytest.fixture
def update():
    u = MagicMock(spec=Update)
    u.update_id = 12345
    return u


@pytest.mark.asyncio
async def test_non_update_passes_through(middleware, handler):
    data = {}
    event = MagicMock()  # not Update
    result = await middleware(handler, event, data)
    assert result == "ok"
    handler.assert_awaited_once_with(event, data)


@pytest.mark.asyncio
async def test_first_update_calls_handler(middleware, handler, update):
    data = {}
    result = await middleware(handler, update, data)
    assert result == "ok"
    handler.assert_awaited_once_with(update, data)


@pytest.mark.asyncio
async def test_duplicate_update_id_skipped(middleware, handler):
    """Use a unique update_id so the first call is not already in cache from other tests."""
    data = {}
    u = MagicMock(spec=Update)
    u.update_id = 98765
    r1 = await middleware(handler, u, data)
    assert r1 == "ok"
    r2 = await middleware(handler, u, data)
    assert r2 is None
    assert handler.await_count == 1
