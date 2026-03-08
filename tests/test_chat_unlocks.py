"""Тесты видимости блока «Разблокировки» в чате с мэтчем (по проценту совместимости)."""
import pytest

from handlers.chat import _has_unlocks, UNLOCK_FIRST_PERCENT


@pytest.mark.parametrize("percent", [0, 1, 15, 15.9])
def test_has_unlocks_false_when_below_threshold(percent):
    """При 0% и ниже порога (16%) блок «Разблокировки» не показывается."""
    assert _has_unlocks(percent) is False


@pytest.mark.parametrize("percent", [16, 16.0, 30, 31, 50, 51, 100])
def test_has_unlocks_true_when_at_or_above_threshold(percent):
    """При 16% и выше блок «Разблокировки» показывается."""
    assert _has_unlocks(percent) is True


def test_unlock_first_percent_constant():
    """Порог первого разблокировки — 16% (плейлист)."""
    assert UNLOCK_FIRST_PERCENT == 16
