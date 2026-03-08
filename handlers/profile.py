"""Profile/anketa: edit, required and optional fields."""
import logging

from aiogram import F, Router
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command

from db.database import async_session_factory
from services.user_service import get_user_by_telegram_id
from fsm.states import ProfileState
from keyboards.common import main_menu_kb, cancel_kb
from i18n import t

logger = logging.getLogger(__name__)
router = Router(name="profile")


def _cancel_texts():
    return (t("cancel", "ru"), t("cancel", "en"))


def _locale(user) -> str:
    return getattr(user, "locale", None) or "ru"


@router.message(F.text.in_({t("menu_profile", "ru"), t("menu_profile", "en")}))
@router.message(Command("profile"))
async def profile_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(session, message.from_user.id)
        if not user or not user.is_registered():
            await message.answer(t("profile_register_first", _locale(user) if user else "ru"))
            return
        loc = _locale(user)
        if user.is_profile_filled():
            await _send_profile_view(message, user, loc)
            await message.answer(t("profile_edit_cmd", loc))
            return
    await message.answer(t("profile_name_prompt", "ru"), reply_markup=cancel_kb("ru"))
    await state.set_state(ProfileState.display_name)


@router.message(Command("edit_profile"))
async def profile_edit_start(message: Message, state: FSMContext) -> None:
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(session, message.from_user.id)
        if not user or not user.is_registered():
            await message.answer(t("profile_register_first", _locale(user) if user else "ru"))
            return
        loc = _locale(user)
    await state.clear()
    await message.answer(t("profile_name_prompt", loc), reply_markup=cancel_kb(loc))
    await state.set_state(ProfileState.display_name)


@router.message(ProfileState.display_name, F.text)
async def profile_display_name(message: Message, state: FSMContext) -> None:
    if message.text and message.text.strip() in _cancel_texts():
        await state.clear()
        async with async_session_factory() as session:
            user = await get_user_by_telegram_id(session, message.from_user.id)
            loc = _locale(user) if user else "ru"
        await message.answer(t("profile_cancelled", loc), reply_markup=main_menu_kb(loc))
        return
    name = (message.text or "").strip() if message.text else ""
    if not name or len(name) > 100:
        await message.answer(t("profile_name_invalid", "ru"))
        return
    await state.update_data(display_name=name)
    await message.answer(t("profile_age_prompt", "ru"))
    await state.set_state(ProfileState.age)


@router.message(ProfileState.age, F.text)
async def profile_age(message: Message, state: FSMContext) -> None:
    if message.text and message.text.strip() in _cancel_texts():
        await state.clear()
        async with async_session_factory() as session:
            user = await get_user_by_telegram_id(session, message.from_user.id)
            loc = _locale(user) if user else "ru"
        await message.answer(t("profile_cancelled", loc), reply_markup=main_menu_kb(loc))
        return
    try:
        age = int((message.text or "").strip())
        if age < 18 or age > 120:
            await message.answer(t("profile_age_invalid", "ru"))
            return
    except ValueError:
        await message.answer(t("profile_age_number", "ru"))
        return
    await state.update_data(age=age)
    await message.answer(t("profile_gender_prompt", "ru"))
    await state.set_state(ProfileState.gender)


@router.message(ProfileState.gender, F.text)
async def profile_gender(message: Message, state: FSMContext) -> None:
    if message.text and message.text.strip() in _cancel_texts():
        await state.clear()
        async with async_session_factory() as session:
            user = await get_user_by_telegram_id(session, message.from_user.id)
            loc = _locale(user) if user else "ru"
        await message.answer(t("profile_cancelled", loc), reply_markup=main_menu_kb(loc))
        return
    g = (message.text or "").strip()[:20]
    await state.update_data(gender=g)
    await message.answer(t("profile_looking_prompt", "ru"))
    await state.set_state(ProfileState.looking_for)


@router.message(ProfileState.looking_for, F.text)
async def profile_looking_for(message: Message, state: FSMContext) -> None:
    if message.text and message.text.strip() in _cancel_texts():
        await state.clear()
        async with async_session_factory() as session:
            user = await get_user_by_telegram_id(session, message.from_user.id)
            loc = _locale(user) if user else "ru"
        await message.answer(t("profile_cancelled", loc), reply_markup=main_menu_kb(loc))
        return
    lf = (message.text or "").strip().lower()[:10]
    if lf not in ("м", "ж", "все", "m", "f", "all"):
        await message.answer(t("profile_looking_invalid", "ru"))
        return
    await state.update_data(looking_for=lf)
    await message.answer(t("profile_city_prompt", "ru"))
    await state.set_state(ProfileState.city)


@router.message(ProfileState.city, F.text)
async def profile_city(message: Message, state: FSMContext) -> None:
    if message.text and message.text.strip() in _cancel_texts():
        await state.clear()
        async with async_session_factory() as session:
            user = await get_user_by_telegram_id(session, message.from_user.id)
            loc = _locale(user) if user else "ru"
        await message.answer(t("profile_cancelled", loc), reply_markup=main_menu_kb(loc))
        return
    city = (message.text or "").strip()[:255]
    if city.lower() in ("не указывать", "нет", "-", "not specified"):
        city = "Не указывать" if (await state.get_data()).get("locale", "ru") == "ru" else "Not specified"
    await state.update_data(city=city)
    await message.answer(t("profile_photo_prompt", "ru"))
    await state.set_state(ProfileState.photo)


@router.message(ProfileState.photo, F.photo)
async def profile_photo(message: Message, state: FSMContext) -> None:
    photo = message.photo[-1]
    await state.update_data(profile_photo_file_id=photo.file_id)
    await message.answer(
        t("profile_description_prompt", "ru"),
        reply_markup=cancel_kb("ru"),
    )
    await state.set_state(ProfileState.description)


@router.message(ProfileState.description, F.text)
async def profile_description(message: Message, state: FSMContext) -> None:
    if message.text and message.text.strip() in _cancel_texts():
        await state.clear()
        async with async_session_factory() as session:
            user = await get_user_by_telegram_id(session, message.from_user.id)
            loc = _locale(user) if user else "ru"
        await message.answer(t("profile_cancelled", loc), reply_markup=main_menu_kb(loc))
        return
    desc = (message.text or "").strip()[:500] if message.text else ""
    if desc == "-" or (message.text and message.text.strip().lower() in ("пропустить", "skip")):
        desc = ""
    await state.update_data(description=desc or None)
    await message.answer(t("profile_interests_prompt", "ru"))
    await state.set_state(ProfileState.interests)


@router.message(ProfileState.interests, F.text)
async def profile_interests(message: Message, state: FSMContext) -> None:
    if message.text and message.text.strip() in _cancel_texts():
        await state.clear()
        async with async_session_factory() as session:
            user = await get_user_by_telegram_id(session, message.from_user.id)
            loc = _locale(user) if user else "ru"
        await message.answer(t("profile_cancelled", loc), reply_markup=main_menu_kb(loc))
        return
    interests = (message.text or "").strip()[:1024] if message.text else ""
    if interests == "-":
        interests = ""
    await state.update_data(interests=interests or None)
    await message.answer(t("profile_movies_prompt", "ru"))
    await state.set_state(ProfileState.movies_music)


@router.message(ProfileState.movies_music, F.text)
async def profile_movies_music(message: Message, state: FSMContext) -> None:
    if message.text and message.text.strip() in _cancel_texts():
        await state.clear()
        async with async_session_factory() as session:
            user = await get_user_by_telegram_id(session, message.from_user.id)
            loc = _locale(user) if user else "ru"
        await message.answer(t("profile_cancelled", loc), reply_markup=main_menu_kb(loc))
        return
    mm = (message.text or "").strip()[:1024] if message.text else ""
    if mm == "-":
        mm = ""
    await state.update_data(movies_music=mm or None)
    await message.answer(t("profile_zodiac_prompt", "ru"))
    await state.set_state(ProfileState.zodiac)


@router.message(ProfileState.zodiac, F.text)
async def profile_zodiac(message: Message, state: FSMContext) -> None:
    if message.text and message.text.strip() in _cancel_texts():
        await state.clear()
        async with async_session_factory() as session:
            user = await get_user_by_telegram_id(session, message.from_user.id)
            loc = _locale(user) if user else "ru"
        await message.answer(t("profile_cancelled", loc), reply_markup=main_menu_kb(loc))
        return
    zodiac = (message.text or "").strip()[:50] if message.text else ""
    if zodiac == "-":
        zodiac = ""
    await state.update_data(zodiac=zodiac or None)
    data = await state.get_data()
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(session, message.from_user.id)
        if not user:
            await message.answer("Ошибка: пользователь не найден.")
            await state.clear()
            return
        loc = _locale(user)
        user.display_name = data.get("display_name")
        user.age = data.get("age")
        user.gender = data.get("gender")
        user.looking_for = data.get("looking_for")
        user.city = data.get("city")
        user.profile_photo_file_id = data.get("profile_photo_file_id")
        user.description = data.get("description") or None
        user.interests = data.get("interests") or None
        user.movies_music = data.get("movies_music") or None
        user.zodiac = data.get("zodiac") or None
        user.profile_filled = True
        await session.commit()
        await session.refresh(user)
    await state.clear()
    await message.answer(t("profile_saved", loc), reply_markup=main_menu_kb(loc))


async def _send_profile_view(message: Message, user, locale: str) -> None:
    na = t("profile_na", locale)
    parts = [
        f"👤 {user.display_name or user.first_name}, {user.age}",
        f"{t('profile_gender', locale)}: {user.gender}, {t('profile_looking', locale)}: {user.looking_for}",
        f"{t('profile_city', locale)}: {user.city or na}",
    ]
    if user.description:
        parts.append(f"{t('profile_about', locale)}: {user.description[:200]}{'…' if len(user.description) > 200 else ''}")
    if user.interests:
        parts.append(f"{t('profile_interests', locale)}: {user.interests[:150]}…" if len(user.interests) > 150 else f"{t('profile_interests', locale)}: {user.interests}")
    await message.answer("\n".join(parts))
