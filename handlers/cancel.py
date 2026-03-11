"""Global /cancel: clear FSM state and return to main menu."""
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from db.database import async_session_factory
from services.user_service import get_user_by_telegram_id
from keyboards.common import main_menu_kb
from i18n import t

router = Router(name="cancel")


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(session, message.from_user.id)
        locale = getattr(user, "locale", None) or "ru" if user else "ru"
    await message.answer(t("action_cancelled", locale), reply_markup=main_menu_kb(locale))
