"""Тесты просмотра своей анкеты: с фото и без."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from handlers.profile import _send_profile_view


def _make_user(
    *,
    profile_photo_file_id=None,
    display_name="TestUser",
    first_name="Test",
    age=25,
    gender="M",
    looking_for="F",
    city="Moscow",
    description=None,
    interests=None,
):
    """Минимальный объект пользователя для _send_profile_view."""
    u = MagicMock()
    u.profile_photo_file_id = profile_photo_file_id
    u.display_name = display_name
    u.first_name = first_name
    u.age = age
    u.gender = gender
    u.looking_for = looking_for
    u.city = city
    u.description = description
    u.interests = interests
    return u


@pytest.mark.asyncio
async def test_send_profile_view_with_photo_sends_photo():
    """При просмотре своей анкеты с заполненным фото отправляется answer_photo с подписью."""
    message = MagicMock()
    message.answer_photo = AsyncMock()
    message.answer = AsyncMock()

    user = _make_user(profile_photo_file_id="file_abc123", city=None)

    await _send_profile_view(message, user, "ru")

    message.answer_photo.assert_called_once()
    call_kw = message.answer_photo.call_args[1]
    assert call_kw["caption"] is not None
    assert "TestUser" in call_kw["caption"] or "Test" in call_kw["caption"]
    assert "25" in call_kw["caption"]
    # file_id передаётся первым позиционным аргументом
    assert message.answer_photo.call_args[0][0] == "file_abc123"
    message.answer.assert_not_called()


@pytest.mark.asyncio
async def test_send_profile_view_without_photo_sends_text_only():
    """При просмотре своей анкеты без фото отправляется только answer (текст)."""
    message = MagicMock()
    message.answer_photo = AsyncMock()
    message.answer = AsyncMock()

    user = _make_user(profile_photo_file_id=None, display_name="NoPhoto")

    await _send_profile_view(message, user, "ru")

    message.answer.assert_called_once()
    text = message.answer.call_args[0][0]
    assert "NoPhoto" in text
    assert "25" in text
    message.answer_photo.assert_not_called()
