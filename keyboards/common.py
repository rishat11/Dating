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
