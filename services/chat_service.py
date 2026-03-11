"""Chat helpers: previous sender, delivery to partner (with FSM check), undelivered messages."""
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from aiogram import Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Message as MsgModel, MessageType
from i18n import t

if TYPE_CHECKING:
    from aiogram.fsm.storage.base import BaseStorage
    from aiogram.fsm.storage.base import StorageKey
    from db.models import User


async def get_previous_sender_id(
    session: AsyncSession, match_id: int, before_message_id: int
) -> Optional[int]:
    """Sender_id последнего сообщения в match с id < before_message_id, или None."""
    result = await session.execute(
        select(MsgModel.sender_id)
        .where(MsgModel.match_id == match_id, MsgModel.id < before_message_id)
        .order_by(MsgModel.id.desc())
        .limit(1)
    )
    return result.scalars().first()


def _recipient_storage_key(bot: Bot, partner_telegram_id: int) -> "StorageKey":
    from aiogram.fsm.storage.base import StorageKey
    return StorageKey(
        bot_id=bot.id,
        chat_id=partner_telegram_id,
        user_id=partner_telegram_id,
    )


async def deliver_message_to_partner(
    session: AsyncSession,
    bot: Bot,
    storage: "BaseStorage",
    match_id: int,
    partner: "User",
    message_record: MsgModel,
    sender_display_name: str,
    locale: str,
) -> None:
    """
    Deliver a message to the partner: if partner's active chat is this match, send content
    and set recipient_delivered_at; otherwise send a notification with 'Open chat' button.
    """
    key = _recipient_storage_key(bot, partner.telegram_id)
    data = await storage.get_data(key)
    active_match_id = data.get("active_match_id")

    if active_match_id == match_id:
        # Partner is in this chat — send content as before (no "From name" prefix)
        if message_record.type == MessageType.TEXT.value:
            body = (message_record.text or "").strip() or "\u200b"  # Telegram requires non-empty text
            await bot.send_message(partner.telegram_id, body)
        elif message_record.type == MessageType.PHOTO.value and message_record.file_id:
            await bot.send_photo(
                partner.telegram_id,
                photo=message_record.file_id,
                caption=None,
            )
        elif message_record.type == MessageType.VOICE.value and message_record.file_id:
            await bot.send_voice(
                partner.telegram_id,
                voice=message_record.file_id,
                caption=None,
            )
        elif message_record.type == MessageType.STICKER.value and message_record.file_id:
            await bot.send_sticker(partner.telegram_id, sticker=message_record.file_id)
        elif message_record.type == MessageType.ANIMATION.value and message_record.file_id:
            await bot.send_animation(
                partner.telegram_id,
                animation=message_record.file_id,
                caption=None,
            )
        else:
            await bot.send_message(partner.telegram_id, "\u200b")
        await session.execute(
            update(MsgModel)
            .where(MsgModel.id == message_record.id)
            .values(recipient_delivered_at=datetime.utcnow())
        )
        await session.commit()
    else:
        # Partner is in another chat or not in chat — send notification only
        text = t("chat_new_message_other_chat", locale, name=sender_display_name)
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(
                text=t("chat_open_chat_btn", locale),
                callback_data=f"open_chat:{match_id}",
            )
        )
        await bot.send_message(
            partner.telegram_id,
            text,
            reply_markup=builder.as_markup(),
        )


async def get_last_message_per_match(
    session: AsyncSession, match_ids: list[int]
) -> dict[int, MsgModel]:
    """Last message (by id) per match_id. Returns dict match_id -> Message or missing key."""
    if not match_ids:
        return {}
    # Subquery: max(id) per match_id
    subq = (
        select(MsgModel.match_id, func.max(MsgModel.id).label("max_id"))
        .where(MsgModel.match_id.in_(match_ids))
        .group_by(MsgModel.match_id)
    ).subquery()
    result = await session.execute(
        select(MsgModel).join(subq, (MsgModel.match_id == subq.c.match_id) & (MsgModel.id == subq.c.max_id))
    )
    return {row.match_id: row for row in result.scalars().all()}


async def get_unread_count_per_match(
    session: AsyncSession, match_ids: list[int], recipient_user_id: int
) -> dict[int, int]:
    """Count of undelivered messages (to recipient_user_id) per match. sender_id != recipient_user_id = from partner."""
    if not match_ids:
        return {}
    result = await session.execute(
        select(MsgModel.match_id, func.count(MsgModel.id).label("cnt"))
        .where(
            MsgModel.match_id.in_(match_ids),
            MsgModel.sender_id != recipient_user_id,
            MsgModel.recipient_delivered_at.is_(None),
        )
        .group_by(MsgModel.match_id)
    )
    return {row.match_id: row.cnt for row in result.all()}


async def get_undelivered_messages(
    session: AsyncSession, match_id: int, recipient_user_id: int
):
    """Messages in this match addressed to recipient_user_id (sender != recipient) not yet delivered."""
    result = await session.execute(
        select(MsgModel)
        .where(
            MsgModel.match_id == match_id,
            MsgModel.sender_id != recipient_user_id,
            MsgModel.recipient_delivered_at.is_(None),
        )
        .order_by(MsgModel.created_at.asc())
    )
    return list(result.scalars().all())


async def send_pending_message_to_viewer(
    session: AsyncSession,
    bot: Bot,
    message_record: MsgModel,
    sender_display_name: str,
    locale: str,
    viewer_telegram_id: int,
    show_sender_name: bool = True,
) -> None:
    """
    Send one pending (undelivered) message to the viewer who opened the chat,
    then set recipient_delivered_at.
    If show_sender_name is False, content is sent without "От {name}" (only first message in a row from same sender gets it).
    """
    prefix = t("chat_from", locale, name=sender_display_name) if show_sender_name else None
    if message_record.type == MessageType.TEXT.value:
        body = (message_record.text or "").strip() or "\u200b"  # Telegram requires non-empty text
        text = f"{prefix}\n\n{body}" if prefix else body
        if not (text and text.strip()):
            text = "\u200b"
        await bot.send_message(viewer_telegram_id, text)
    elif message_record.type == MessageType.PHOTO.value and message_record.file_id:
        await bot.send_photo(
            viewer_telegram_id,
            photo=message_record.file_id,
            caption=prefix,
        )
    elif message_record.type == MessageType.VOICE.value and message_record.file_id:
        await bot.send_voice(
            viewer_telegram_id,
            voice=message_record.file_id,
            caption=prefix,
        )
    elif message_record.type == MessageType.STICKER.value and message_record.file_id:
        await bot.send_sticker(viewer_telegram_id, sticker=message_record.file_id)
    elif message_record.type == MessageType.ANIMATION.value and message_record.file_id:
        await bot.send_animation(
            viewer_telegram_id,
            animation=message_record.file_id,
            caption=prefix,
        )
    else:
        await bot.send_message(viewer_telegram_id, (prefix and prefix.strip()) or "\u200b")
    await session.execute(
        update(MsgModel)
        .where(MsgModel.id == message_record.id)
        .values(recipient_delivered_at=datetime.utcnow())
    )
    await session.commit()
