"""Registration and verification: telegram id, name, photo, 18+, consent, language."""
import logging
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardRemove, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from db.database import async_session_factory
from db.models import User
from services.user_service import get_user_by_telegram_id, get_or_create_user
from fsm.states import OnboardingState
from keyboards.common import main_menu_kb, cancel_kb, yes_no_kb
from i18n import t

logger = logging.getLogger(__name__)
router = Router(name="onboarding")

CONSENT_YES_RU = "✅ Да"
CONSENT_NO_RU = "❌ Нет"
CONSENT_YES_EN = "✅ Yes"
CONSENT_NO_EN = "❌ No"


def _consent_yes(locale: str) -> str:
    return CONSENT_YES_EN if locale == "en" else CONSENT_YES_RU


def _consent_no(locale: str) -> str:
    return CONSENT_NO_EN if locale == "en" else CONSENT_NO_RU


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    async with async_session_factory() as session:
        user = await get_or_create_user(
            session,
            message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name or "User",
        )
        locale = getattr(user, "locale", None) or "ru"
        if user.is_registered() and user.is_profile_filled():
            await message.answer(
                t("welcome_back", locale),
                reply_markup=main_menu_kb(locale),
            )
            return
        if user.is_registered() and not user.is_profile_filled():
            await message.answer(
                t("fill_profile_first", locale),
                reply_markup=main_menu_kb(locale),
            )
            return
    await message.answer(t("onboarding_welcome", "ru"))
    await state.set_state(OnboardingState.name)


@router.message(OnboardingState.name, F.text)
async def onboarding_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not name or len(name) > 100:
        await message.answer(t("onboarding_name_invalid", "ru"))
        return
    await state.update_data(name=name)
    await message.answer(t("onboarding_photo", "ru"), reply_markup=cancel_kb())
    await state.set_state(OnboardingState.photo)


@router.message(OnboardingState.photo, F.photo)
async def onboarding_photo(message: Message, state: FSMContext) -> None:
    photo = message.photo[-1]
    await state.update_data(photo_file_id=photo.file_id)
    await message.answer(
        t("onboarding_birth_date", "ru"),
        reply_markup=cancel_kb(),
    )
    await state.set_state(OnboardingState.birth_date)


@router.message(OnboardingState.birth_date, F.text)
async def onboarding_birth_date(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    try:
        dt = datetime.strptime(text, "%d.%m.%Y")
        if (datetime.now() - dt).days < 18 * 365:
            await message.answer(t("onboarding_birth_invalid", "ru"))
            return
    except ValueError:
        await message.answer(t("onboarding_birth_format", "ru"))
        return
    await state.update_data(birth_date=text)
    await message.answer(
        t("onboarding_age_confirm", "ru"),
        reply_markup=yes_no_kb(),
    )
    await state.set_state(OnboardingState.age_confirm)


@router.message(OnboardingState.age_confirm, F.text)
async def onboarding_age_confirm(message: Message, state: FSMContext) -> None:
    if message.text not in (CONSENT_YES_RU, CONSENT_YES_EN):
        await message.answer(t("onboarding_age_only", "ru"))
        return
    await message.answer(t("onboarding_rules", "ru"), reply_markup=yes_no_kb())
    await state.set_state(OnboardingState.rules_accept)


@router.message(OnboardingState.rules_accept, F.text)
async def onboarding_rules_accept(message: Message, state: FSMContext) -> None:
    if message.text not in (CONSENT_YES_RU, CONSENT_YES_EN):
        await message.answer(t("onboarding_rules_no", "ru"))
        return
    await state.update_data(rules_accepted=True)
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="Русский", callback_data="lang:ru"),
        InlineKeyboardButton(text="English", callback_data="lang:en"),
    )
    await message.answer(
        t("onboarding_language", "ru"),
        reply_markup=builder.as_markup(),
    )
    await state.set_state(OnboardingState.language)


@router.callback_query(OnboardingState.language, F.data.startswith("lang:"))
async def onboarding_language(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        return
    lang = callback.data.split(":")[1] if ":" in callback.data else "ru"
    if lang not in ("ru", "en"):
        lang = "ru"
    await callback.answer()
    data = await state.get_data()
    birth_str = data.get("birth_date", "")
    try:
        birth_date = datetime.strptime(birth_str, "%d.%m.%Y")
    except Exception:
        birth_date = None
    async with async_session_factory() as session:
        user = await get_or_create_user(
            session,
            callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name or data.get("name", "User"),
        )
        user.first_name = data.get("name", user.first_name)
        user.photo_file_id = data.get("photo_file_id")
        user.birth_date = birth_date
        user.age_confirmed_18 = True
        user.rules_accepted = True
        user.locale = lang
        await session.commit()
    await state.clear()
    await callback.message.answer(
        t("onboarding_done", lang),
        reply_markup=main_menu_kb(lang),
    )


@router.message(
    (OnboardingState.name, OnboardingState.photo, OnboardingState.birth_date, OnboardingState.age_confirm, OnboardingState.rules_accept),
    F.text == "❌ Отмена",
)
@router.message(
    (OnboardingState.name, OnboardingState.photo, OnboardingState.birth_date, OnboardingState.age_confirm, OnboardingState.rules_accept),
    F.text == "❌ No",
)
async def onboarding_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(t("onboarding_cancel", "ru"), reply_markup=ReplyKeyboardRemove())


@router.message(OnboardingState.photo, ~F.photo)
async def onboarding_photo_invalid(message: Message) -> None:
    await message.answer(t("onboarding_photo_invalid", "ru"))
