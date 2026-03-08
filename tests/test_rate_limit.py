"""Tests for services.rate_limit (in-memory path with mocked Redis)."""
from unittest.mock import patch

import pytest

from services import rate_limit


@pytest.fixture(autouse=True)
def no_redis():
    """Force in-memory rate limiting (no Redis)."""
    with patch.object(rate_limit, "get_redis", return_value=None):
        yield


@pytest.mark.asyncio
async def test_under_limit_returns_none():
    # Use unique key per run to avoid cross-test pollution
    user_id = 99991
    action = "test_under"
    limit = 3
    for _ in range(limit):
        result = await rate_limit.check_rate_limit(user_id, action, limit=limit, window_seconds=60)
        assert result is None


@pytest.mark.asyncio
async def test_over_limit_returns_minutes():
    user_id = 99992
    action = "test_over"
    limit = 2
    window_seconds = 60
    await rate_limit.check_rate_limit(user_id, action, limit=limit, window_seconds=window_seconds)
    await rate_limit.check_rate_limit(user_id, action, limit=limit, window_seconds=window_seconds)
    result = await rate_limit.check_rate_limit(user_id, action, limit=limit, window_seconds=window_seconds)
    assert result is not None
    assert result >= 1


@pytest.mark.asyncio
async def test_different_users_independent():
    limit = 1
    await rate_limit.check_rate_limit(88881, "act_a", limit=limit, window_seconds=60)
    over1 = await rate_limit.check_rate_limit(88881, "act_a", limit=limit, window_seconds=60)
    assert over1 is not None
    # Other user still under limit
    under = await rate_limit.check_rate_limit(88882, "act_a", limit=limit, window_seconds=60)
    assert under is None


@pytest.mark.asyncio
async def test_different_actions_independent():
    user_id = 77771
    limit = 1
    await rate_limit.check_rate_limit(user_id, "action_1", limit=limit, window_seconds=60)
    over1 = await rate_limit.check_rate_limit(user_id, "action_1", limit=limit, window_seconds=60)
    assert over1 is not None
    under = await rate_limit.check_rate_limit(user_id, "action_2", limit=limit, window_seconds=60)
    assert under is None
