from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from i18n import t


def feed_actions_kb(profile_user_id: int, locale: str = "ru") -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text=t("feed_skip", locale), callback_data=f"skip:{profile_user_id}"),
        InlineKeyboardButton(text=t("feed_like", locale), callback_data=f"like:{profile_user_id}"),
    )
    return builder
