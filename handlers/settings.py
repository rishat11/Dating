"""Settings: language, geolocation, delete account, privacy link."""
import logging
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.types import Message, CallbackQuery, KeyboardButton, ReplyKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from db.database import async_session_factory
from db.models import User, Match, MatchStatus
from services.user_service import get_user_by_telegram_id
from services.match_service import get_user_matches
from keyboards.common import main_menu_kb
from i18n import t

logger = logging.getLogger(__name__)
router = Router(name="settings")

# Privacy policy URL (config or constant)
PRIVACY_URL = "https://example.com/privacy"  # TODO: set in config


def _locale_display(locale: str) -> str:
    return t("settings_lang_ru", "ru") if locale == "ru" else t("settings_lang_en", "en")


@router.message(F.text.in_({"⚙️ Настройки", "⚙️ Settings"}))
async def settings_open(message: Message, state: FSMContext) -> None:
    await state.clear()
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(session, message.from_user.id)
        if not user or not user.is_registered():
            await message.answer(t("profile_register_first", "ru"))
            return
        locale = getattr(user, "locale", None) or "ru"
        has_geo = user.latitude is not None and user.longitude is not None

    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(
            text=t("settings_language", locale) + f" — {_locale_display(locale)}",
            callback_data="settings:lang",
        )
    )
    builder.adjust(1)
    builder.row(
        InlineKeyboardButton(
            text=t("settings_share_location", locale) if not has_geo else t("settings_disable_geo", locale),
            callback_data="settings:geo_toggle",
        )
    )
    builder.row(
        InlineKeyboardButton(text=t("settings_delete_account", locale), callback_data="settings:delete"),
    )
    builder.row(
        InlineKeyboardButton(text=t("settings_privacy", locale), url=PRIVACY_URL),
    )

    text = (
        t("settings_title", locale) + "\n\n"
        + t("settings_language_current", locale, lang=_locale_display(locale)) + "\n"
        + t("settings_geo", locale) + ": "
        + (t("settings_geo_on", locale) if has_geo else t("settings_geo_off", locale))
    )
    await message.answer(text, reply_markup=builder.as_markup())


@router.callback_query(F.data == "settings:lang")
async def settings_lang_open(callback: CallbackQuery) -> None:
    if not callback.message:
        return
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(session, callback.from_user.id)
        locale = getattr(user, "locale", None) or "ru" if user else "ru"
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="Русский", callback_data="setlang:ru"),
        InlineKeyboardButton(text="English", callback_data="setlang:en"),
    )
    await callback.answer()
    await callback.message.answer(t("onboarding_language", locale), reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("setlang:"))
async def settings_lang_set(callback: CallbackQuery) -> None:
    if not callback.data or not callback.message:
        return
    lang = callback.data.split(":")[1] if ":" in callback.data else "ru"
    if lang not in ("ru", "en"):
        await callback.answer()
        return
    await callback.answer()
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(session, callback.from_user.id)
        if user:
            user.locale = lang
            await session.commit()
    await callback.message.answer(t("settings_saved", lang) + " " + t("settings_language_current", lang, lang=_locale_display(lang)))
    await callback.message.answer(t("settings_title", lang), reply_markup=main_menu_kb(lang))


@router.callback_query(F.data == "settings:geo_toggle")
async def settings_geo_toggle(callback: CallbackQuery) -> None:
    """Show request location or disable: actual location is handled in message.location handler."""
    if not callback.message:
        return
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(session, callback.from_user.id)
        if not user:
            await callback.answer()
            return
        locale = getattr(user, "locale", None) or "ru"
        has_geo = user.latitude is not None and user.longitude is not None

    if has_geo:
        # Disable: clear coords
        async with async_session_factory() as session:
            user = await get_user_by_telegram_id(session, callback.from_user.id)
            if user:
                user.latitude = None
                user.longitude = None
                user.location_updated_at = None
                await session.commit()
        await callback.answer(t("settings_geo_off", locale))
        await callback.message.answer(t("settings_geo_off", locale))
    else:
        # Ask to share location
        from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
        kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=t("settings_share_location", locale), request_location=True)]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        await callback.answer()
        await callback.message.answer(
            t("settings_geo", locale) + ": " + t("settings_share_location", locale) + " (кнопка ниже)",
            reply_markup=kb,
        )


@router.message(F.location)
async def settings_location_received(message: Message) -> None:
    """Save location when user sends it (from Settings or Profile)."""
    loc = message.location
    if not loc:
        return
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(session, message.from_user.id)
        if not user:
            return
        user.latitude = loc.latitude
        user.longitude = loc.longitude
        user.location_updated_at = datetime.utcnow()
        await session.commit()
        locale = getattr(user, "locale", None) or "ru"
    from aiogram.types import ReplyKeyboardRemove
    await message.answer(
        t("settings_geo_on", locale),
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer(t("settings_title", locale), reply_markup=main_menu_kb(locale))


@router.callback_query(F.data == "settings:delete")
async def settings_delete_confirm(callback: CallbackQuery) -> None:
    if not callback.message:
        return
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(session, callback.from_user.id)
        locale = getattr(user, "locale", None) or "ru" if user else "ru"
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text=t("delete_yes", locale), callback_data="delete_confirm:yes"),
        InlineKeyboardButton(text=t("delete_no", locale), callback_data="delete_confirm:no"),
    )
    await callback.answer()
    await callback.message.answer(t("delete_confirm", locale), reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("delete_confirm:"))
async def settings_delete_do(callback: CallbackQuery, bot: Bot) -> None:
    if not callback.data or not callback.message:
        return
    if callback.data != "delete_confirm:yes":
        await callback.answer()
        await callback.message.answer(t("settings_saved", "ru"))  # no change
        return
    await callback.answer()
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(session, callback.from_user.id)
        if not user:
            return
        locale = getattr(user, "locale", None) or "ru"
        user.deleted_at = datetime.utcnow()
        await session.commit()
        await session.refresh(user)
        # Notify partners in active chats
        matches = await get_user_matches(session, user.id)
        partner_msg = t("partner_deleted", "ru")  # partner may have any locale
        for m in matches:
            partner = m.partner_of(user.id)
            if partner and partner.telegram_id and partner.deleted_at is None:
                try:
                    await bot.send_message(partner.telegram_id, partner_msg)
                except Exception as e:
                    logger.warning("Notify partner on delete: %s", e)
    await callback.message.answer(t("delete_done", locale))
    # Remove reply keyboard
    from aiogram.types import ReplyKeyboardRemove
    await callback.message.answer("/start", reply_markup=ReplyKeyboardRemove())


# Include settings router so "Settings" menu opens settings
def _settings_menu_texts():
    return [t("menu_settings", "ru"), t("menu_settings", "en")]
