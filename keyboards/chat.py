from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from i18n import t


def chat_menu_kb(locale: str = "ru") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("back_to_chats", locale))],
        ],
        resize_keyboard=True,
    )


def report_block_kb(match_id: int, locale: str = "ru") -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text=t("chat_block_btn", locale), callback_data=f"block:{match_id}"),
        InlineKeyboardButton(text=t("chat_report_btn", locale), callback_data=f"report:{match_id}"),
        InlineKeyboardButton(text=t("chat_end_btn", locale), callback_data=f"end_chat:{match_id}"),
    )
    return builder
