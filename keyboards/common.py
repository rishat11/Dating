from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from i18n import t


def main_menu_kb(locale: str = "ru") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("menu_profile", locale)), KeyboardButton(text=t("menu_feed", locale))],
            [KeyboardButton(text=t("menu_chats", locale))],
            [KeyboardButton(text=t("menu_settings", locale))],
        ],
        resize_keyboard=True,
    )


def cancel_kb(locale: str = "ru") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t("cancel", locale))]],
        resize_keyboard=True,
    )


def cancel_skip_kb(locale: str = "ru") -> ReplyKeyboardMarkup:
    """Cancel + Skip for optional profile fields."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=t("cancel", locale)),
                KeyboardButton(text=t("profile_skip_btn", locale)),
            ],
        ],
        resize_keyboard=True,
    )


def yes_no_kb(locale: str = "ru") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("consent_yes", locale)), KeyboardButton(text=t("consent_no", locale))],
        ],
        resize_keyboard=True,
    )


def inline_yes_no_kb(callback_prefix: str) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="✅ Да", callback_data=f"{callback_prefix}:yes"),
        InlineKeyboardButton(text="❌ Нет", callback_data=f"{callback_prefix}:no"),
    )
    return builder


def profile_edit_menu_kb(locale: str = "ru") -> InlineKeyboardBuilder:
    """Inline keyboard: what profile field to edit + Done."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=t("profile_field_name", locale), callback_data="edit_profile:display_name"),
        InlineKeyboardButton(text=t("profile_gender", locale), callback_data="edit_profile:gender"),
    )
    builder.row(
        InlineKeyboardButton(text=t("profile_looking", locale), callback_data="edit_profile:looking_for"),
        InlineKeyboardButton(text=t("profile_city", locale), callback_data="edit_profile:city"),
    )
    builder.row(
        InlineKeyboardButton(text=t("profile_field_photo", locale), callback_data="edit_profile:photo"),
        InlineKeyboardButton(text=t("profile_about", locale), callback_data="edit_profile:description"),
    )
    builder.row(
        InlineKeyboardButton(text=t("profile_interests", locale), callback_data="edit_profile:interests"),
    )
    builder.row(
        InlineKeyboardButton(text=t("profile_movies", locale), callback_data="edit_profile:movies"),
        InlineKeyboardButton(text=t("profile_series", locale), callback_data="edit_profile:series"),
        InlineKeyboardButton(text=t("profile_music", locale), callback_data="edit_profile:music"),
    )
    builder.row(
        InlineKeyboardButton(text=t("profile_edit_done", locale), callback_data="edit_profile:done"),
    )
    return builder
