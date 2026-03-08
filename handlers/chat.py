"""Chat: list matches, context 'chat with X', forward messages (text/photo/voice/sticker)."""
import logging
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from db.database import async_session_factory
from db.models import User, Match, Message as MsgModel, MessageType
from services.user_service import get_user_by_telegram_id
from services.match_service import get_user_matches, get_match_by_id_for_user
from services.destiny_service import (
    get_or_create_destiny_index,
    format_progress_bar,
    get_level_name,
    get_next_threshold,
)
from services.destiny_queue import enqueue_destiny_recalc
from services.unlocks import get_playlist_stub, get_next_challenge
from fsm.states import ChatState
from keyboards.common import main_menu_kb
from keyboards.chat import chat_menu_kb, report_block_kb
from i18n import t
from config import get_config
from services.rate_limit import check_rate_limit
from services.contact_moderation import has_contact_markers
from services.audit import audit_block, audit_report, audit_chat_ended, audit_message_rejected_contact
from services.feed_service import gender_emoji

logger = logging.getLogger(__name__)
router = Router(name="chat")

# Порог первого разблокировки (плейлист); блок «Разблокировки» показываем только при percent >= этого значения
UNLOCK_FIRST_PERCENT = 16


def _has_unlocks(current_percent: float) -> bool:
    """Показывать ли блок «Разблокировки» в чате (хотя бы одна кнопка доступна)."""
    return current_percent >= UNLOCK_FIRST_PERCENT


async def _chat_header(
    session, match: Match, current_user_id: int, locale: str = "ru", destiny_index=None
) -> str:
    """Собирает заголовок чата (имя, прогресс, уровень). destiny_index можно передать, чтобы не дергать БД повторно."""
    partner = match.partner_of(current_user_id)
    if not partner:
        return "Чат"
    di = destiny_index if destiny_index is not None else await get_or_create_destiny_index(session, match.id)
    pct = round(di.current_percent)
    level_key = get_level_name(di.current_percent)
    level = t(level_key, locale)
    progress = format_progress_bar(di.current_percent)
    em = gender_emoji(partner.gender)
    name_with_emoji = f"{em} {partner.display_name or partner.first_name}"
    header = t("chat_header", locale, name=name_with_emoji, age=partner.age or "?", progress=progress, level=level)
    next_pct, est_msgs = get_next_threshold(di.current_percent)
    if di.current_percent < 15:
        header += "\n" + t("chat_hint_increase_compatibility", locale)
    elif next_pct <= 100 and est_msgs > 0:
        header += "\n" + t("chat_to_next_level", locale, pct=next_pct, n=est_msgs)
    return header


def _loc(user) -> str:
    return getattr(user, "locale", None) or "ru"


@router.message(F.text.in_({t("menu_chats", "ru"), t("menu_chats", "en")}))
async def chats_list(message: Message, state: FSMContext) -> None:
    await state.clear()
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(session, message.from_user.id)
        if not user or not user.is_registered():
            await message.answer(t("chat_register_first", _loc(user) if user else "ru"))
            return
        loc = _loc(user)
        matches = await get_user_matches(session, user.id)
    if not matches:
        await message.answer(t("chat_no_chats", loc), reply_markup=main_menu_kb(loc))
        return
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    for m in matches:
        partner = m.partner_of(user.id)
        if partner:
            em = gender_emoji(partner.gender)
            builder.add(
                InlineKeyboardButton(
                    text=f"💬 {em} {partner.display_name or partner.first_name} ({partner.age or '?'})",
                    callback_data=f"open_chat:{m.id}",
                )
            )
    await message.answer(t("chat_choose", loc), reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("open_chat:"))
async def chat_open(callback: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        return
    try:
        match_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer(t("error", "ru"))
        return
    await callback.answer()
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(session, callback.from_user.id)
        if not user:
            return
        match = await get_match_by_id_for_user(session, match_id, user.id)
        if not match:
            await callback.message.answer(t("chat_not_found", "ru"))
            return
        partner = match.partner_of(user.id)
        loc = _loc(user)
        di = await get_or_create_destiny_index(session, match.id)
        header = await _chat_header(session, match, user.id, loc, destiny_index=di)
    await state.update_data(active_match_id=match_id)
    await state.set_state(ChatState.in_chat)
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    if di.current_percent >= 16:
        builder.add(InlineKeyboardButton(text=t("chat_playlist", loc), callback_data=f"unlock_playlist:{match_id}"))
    if di.current_percent >= 31:
        builder.add(InlineKeyboardButton(text=t("chat_challenge", loc), callback_data=f"unlock_challenge:{match_id}"))
    if di.current_percent >= 51:
        builder.add(InlineKeyboardButton(text=t("chat_cloud", loc), callback_data=f"unlock_cloud:{match_id}"))
    has_unlocks = _has_unlocks(di.current_percent)
    caption = header + "\n\n" + t("chat_send_hint", loc)
    if partner and getattr(partner, "profile_photo_file_id", None):
        await callback.message.answer_photo(
            photo=partner.profile_photo_file_id,
            caption=caption,
            reply_markup=chat_menu_kb(loc),
        )
    else:
        await callback.message.answer(
            caption,
            reply_markup=chat_menu_kb(loc),
        )
    if has_unlocks:
        await callback.message.answer(t("chat_unlocks", loc), reply_markup=builder.as_markup())


@router.message(ChatState.in_chat, F.text)
async def chat_text(message: Message, bot: Bot, state: FSMContext) -> None:
    # «Назад к чатам» — одна сессия БД, один state.clear(), без повторного вызова chats_list
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(session, message.from_user.id)
        loc = _loc(user) if user else "ru"
        back_text = (t("back_to_chats", loc) or "").strip()
        if (message.text or "").strip() == back_text:
            await state.clear()
            if not user or not user.is_registered():
                await message.answer(t("chat_register_first", loc), reply_markup=main_menu_kb(loc))
                return
            matches = await get_user_matches(session, user.id)
            if not matches:
                await message.answer(t("chat_no_chats", loc), reply_markup=main_menu_kb(loc))
                return
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            from aiogram.types import InlineKeyboardButton
            builder = InlineKeyboardBuilder()
            for m in matches:
                partner = m.partner_of(user.id)
                if partner:
                    em = gender_emoji(partner.gender)
                    builder.add(
                        InlineKeyboardButton(
                            text=f"💬 {em} {partner.display_name or partner.first_name} ({partner.age or '?'})",
                            callback_data=f"open_chat:{m.id}",
                        )
                    )
            await message.answer(t("chats_title", loc), reply_markup=main_menu_kb(loc))
            await message.answer(t("chat_choose", loc), reply_markup=builder.as_markup())
            return

    data = await state.get_data()
    match_id = data.get("active_match_id")
    if not match_id:
        await message.answer(t("chat_choose_from_list", loc))
        return
    config = get_config()
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(session, message.from_user.id)
        if not user:
            return
        loc = _loc(user)
        wait_min = await check_rate_limit(user.id, "chat_msg", config.chat_messages_per_minute, 60)
        if wait_min is not None:
            await message.answer(t("rate_limit", loc, min=wait_min))
            return
        if has_contact_markers(message.text or ""):
            await message.answer(t("contact_warning", loc))
            audit_message_rejected_contact(match_id, user.id, length=len(message.text or ""))
            return
        match = await get_match_by_id_for_user(session, match_id, user.id)
        if not match or not match.partner_of(user.id):
            await message.answer(t("chat_not_found", loc))
            return
        partner = match.partner_of(user.id)
        msg = MsgModel(
            match_id=match.id,
            sender_id=user.id,
            type=MessageType.TEXT.value,
            length=len(message.text or ""),
            telegram_message_id=message.message_id,
        )
        session.add(msg)
        await session.commit()
        await session.refresh(msg)
        enqueue_destiny_recalc(
            match.id,
            msg.id,
            sender_id=user.id,
            text=message.text,
            msg_type=MessageType.TEXT.value,
            length=len(message.text or ""),
        )
        partner_loc = _loc(partner)
        await bot.send_message(
            partner.telegram_id,
            t("chat_from", partner_loc, name=user.display_name or user.first_name) + "\n\n" + (message.text or ""),
            reply_markup=report_block_kb(match.id, partner_loc).as_markup(),
        )
    await message.answer(t("chat_sent", loc))


@router.message(ChatState.in_chat, F.photo)
async def chat_photo(message: Message, bot: Bot, state: FSMContext) -> None:
    data = await state.get_data()
    match_id = data.get("active_match_id")
    if not match_id:
        return
    photo = message.photo[-1]
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(session, message.from_user.id)
        match = await get_match_by_id_for_user(session, match_id, user.id)
        if not match or not match.partner_of(user.id):
            return
        partner = match.partner_of(user.id)
        msg = MsgModel(
            match_id=match.id,
            sender_id=user.id,
            type=MessageType.PHOTO.value,
            file_id=photo.file_id,
            telegram_message_id=message.message_id,
        )
        session.add(msg)
        await session.commit()
        await session.refresh(msg)
        enqueue_destiny_recalc(match.id, msg.id, sender_id=user.id, msg_type=MessageType.PHOTO.value)
        partner_loc = _loc(partner)
        await bot.send_photo(
            partner.telegram_id,
            photo=photo.file_id,
            caption=t("chat_photo_from", partner_loc, name=user.display_name or user.first_name),
            reply_markup=report_block_kb(match.id, partner_loc).as_markup(),
        )
    await message.answer(t("chat_sent", _loc(user) if user else "ru"))


@router.message(ChatState.in_chat, F.voice)
async def chat_voice(message: Message, bot: Bot, state: FSMContext) -> None:
    data = await state.get_data()
    match_id = data.get("active_match_id")
    if not match_id:
        return
    voice = message.voice
    duration = voice.duration if voice else None
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(session, message.from_user.id)
        match = await get_match_by_id_for_user(session, match_id, user.id)
        if not match or not match.partner_of(user.id):
            return
        partner = match.partner_of(user.id)
        msg = MsgModel(
            match_id=match.id,
            sender_id=user.id,
            type=MessageType.VOICE.value,
            file_id=voice.file_id if voice else None,
            duration_seconds=duration,
            telegram_message_id=message.message_id,
        )
        session.add(msg)
        await session.commit()
        await session.refresh(msg)
        enqueue_destiny_recalc(
            match.id,
            msg.id,
            sender_id=user.id,
            msg_type=MessageType.VOICE.value,
            duration_seconds=duration,
        )
        partner_loc = _loc(partner)
        await bot.send_voice(
            partner.telegram_id,
            voice=voice.file_id,
            caption=t("chat_voice_from", partner_loc, name=user.display_name or user.first_name),
            reply_markup=report_block_kb(match.id, partner_loc).as_markup(),
        )
    await message.answer(t("chat_sent", _loc(user) if user else "ru"))


@router.message(ChatState.in_chat, F.sticker)
async def chat_sticker(message: Message, bot: Bot, state: FSMContext) -> None:
    data = await state.get_data()
    match_id = data.get("active_match_id")
    if not match_id:
        return
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(session, message.from_user.id)
        match = await get_match_by_id_for_user(session, match_id, user.id)
        if not match or not match.partner_of(user.id):
            return
        partner = match.partner_of(user.id)
        msg = MsgModel(
            match_id=match.id,
            sender_id=user.id,
            type=MessageType.STICKER.value,
            file_id=message.sticker.file_id if message.sticker else None,
            telegram_message_id=message.message_id,
        )
        session.add(msg)
        await session.commit()
        await session.refresh(msg)
        enqueue_destiny_recalc(match.id, msg.id, sender_id=user.id, msg_type=MessageType.STICKER.value)
        partner_loc = _loc(partner)
        await bot.send_sticker(
            partner.telegram_id,
            sticker=message.sticker.file_id,
            reply_markup=report_block_kb(match.id, partner_loc).as_markup(),
        )
    await message.answer(t("chat_sent", _loc(user) if user else "ru"))


@router.callback_query(F.data.startswith("block:"))
async def chat_block(callback: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    from datetime import datetime
    from db.models import MatchStatus
    if not callback.data:
        return
    try:
        match_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer(t("error", "ru"))
        return
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(session, callback.from_user.id)
        loc = _loc(user) if user else "ru"
    await callback.answer(t("chat_blocked", loc))
    async with async_session_factory() as session:
        match = await session.get(Match, match_id)
        u = await get_user_by_telegram_id(session, callback.from_user.id)
        if match and match.status == MatchStatus.ACTIVE.value:
            match.status = MatchStatus.BLOCKED.value
            match.blocked_by_id = u.id if u else None
            match.ended_at = datetime.utcnow()
            await session.commit()
            if u:
                audit_block(match_id, match.other_user_id(u.id), u.id)
    await callback.message.answer(t("chat_blocked", loc), reply_markup=main_menu_kb(loc))


@router.callback_query(F.data.startswith("report:"))
async def chat_report(callback: CallbackQuery) -> None:
    if not callback.data:
        return
    try:
        match_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        match_id = None
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(session, callback.from_user.id)
        loc = _loc(user) if user else "ru"
        if match_id and user:
            match = await session.get(Match, match_id)
            if match:
                audit_report(match_id, match.other_user_id(user.id), user.id)
    await callback.answer(t("chat_report_ok", loc))
    await callback.message.answer(t("chat_report_thanks", loc))


@router.callback_query(F.data.startswith("unlock_playlist:"))
async def unlock_playlist(callback: CallbackQuery) -> None:
    await callback.answer()
    stub = get_playlist_stub()
    await callback.message.answer(stub)


@router.callback_query(F.data.startswith("unlock_challenge:"))
async def unlock_challenge(callback: CallbackQuery) -> None:
    await callback.answer()
    import time
    challenge = get_next_challenge(seed=int(time.time()) // 60)
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(session, callback.from_user.id)
        loc = _loc(user) if user else "ru"
    await callback.message.answer(f"🎯 {t('chat_challenge', loc)}:\n\n{challenge}")


@router.callback_query(F.data.startswith("unlock_cloud:"))
async def unlock_cloud(callback: CallbackQuery) -> None:
    await callback.answer()
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(session, callback.from_user.id)
        loc = _loc(user) if user else "ru"
    await callback.message.answer(t("chat_cloud", loc) + " — в разработке.")


@router.callback_query(F.data.startswith("end_chat:"))
async def chat_end(callback: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    from datetime import datetime
    from db.models import MatchStatus
    if not callback.data:
        return
    try:
        match_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer(t("error", "ru"))
        return
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(session, callback.from_user.id)
        loc = _loc(user) if user else "ru"
    await callback.answer(t("chat_ended", loc))
    async with async_session_factory() as session:
        match = await session.get(Match, match_id)
        if match and match.status == MatchStatus.ACTIVE.value:
            match.status = MatchStatus.ENDED.value
            match.ended_at = datetime.utcnow()
            await session.commit()
            if user:
                audit_chat_ended(match_id, user.id)
    await callback.message.answer(t("chat_ended", loc), reply_markup=main_menu_kb(loc))
