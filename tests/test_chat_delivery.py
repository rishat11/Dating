"""Тесты доставки сообщений по чатам: импорт в handlers и сервис chat_service."""
import pytest

from services.chat_service import (
    deliver_message_to_partner,
    get_undelivered_messages,
    send_pending_message_to_viewer,
    get_previous_sender_id,
)


def test_chat_service_delivery_functions_importable():
    """Функции доставки должны быть импортируемы из services.chat_service."""
    assert callable(deliver_message_to_partner)
    assert callable(get_undelivered_messages)
    assert callable(send_pending_message_to_viewer)
    assert callable(get_previous_sender_id)


def test_handlers_chat_uses_delivery_functions():
    """handlers.chat должен импортировать deliver_message_to_partner и др., иначе NameError при вызове хендлеров."""
    import handlers.chat as chat_handlers
    assert hasattr(chat_handlers, "deliver_message_to_partner"), (
        "handlers.chat must import deliver_message_to_partner so chat_animation_fallback and others can call it"
    )
    assert hasattr(chat_handlers, "get_undelivered_messages")
    assert hasattr(chat_handlers, "send_pending_message_to_viewer")
    assert callable(chat_handlers.deliver_message_to_partner)
