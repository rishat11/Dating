"""Profile/anketa: edit, required and optional fields."""
import logging

from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command

from db.database import async_session_factory
from db.models import age_from_birth_date, zodiac_from_birth_date
from services.user_service import get_user_by_telegram_id
from fsm.states import ProfileState
from keyboards.common import main_menu_kb, cancel_kb, cancel_skip_kb, profile_edit_menu_kb, profile_edit_about_kb, gender_choice_kb, looking_choice_kb
from i18n import t
from services.feed_service import gender_emoji

logger = logging.getLogger(__name__)
router = Router(name="profile")


def _cancel_texts():
    return (t("cancel", "ru"), t("cancel", "en"))


def _skip_texts():
    return (t("profile_skip_btn", "ru"), t("profile_skip_btn", "en"))


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
    await state.update_data(locale=loc)
    await message.answer(t("profile_name_prompt", loc), reply_markup=cancel_kb(loc))
    await state.set_state(ProfileState.display_name)


@router.message(Command("edit_profile"))
async def profile_edit_start(message: Message, state: FSMContext) -> None:
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(session, message.from_user.id)
        if not user or not user.is_registered():
            await message.answer(t("profile_register_first", _locale(user) if user else "ru"))
            return
        loc = _locale(user)
        if user.is_profile_filled():
            await state.clear()
            await state.update_data(edit_mode=True)
            await state.set_state(ProfileState.choose_field)
            await message.answer(
                t("profile_edit_choose", loc),
                reply_markup=profile_edit_menu_kb(loc).as_markup(),
            )
            return
    await state.clear()
    await state.update_data(locale=loc)
    await message.answer(t("profile_name_prompt", loc), reply_markup=cancel_kb(loc))
    await state.set_state(ProfileState.display_name)


async def _send_edit_menu(target: Message, loc: str, state: FSMContext) -> None:
    """Send 'What do you want to edit?' and inline menu; set state to choose_field."""
    await state.set_state(ProfileState.choose_field)
    await state.update_data(edit_mode=True)
    await target.answer(
        t("profile_edit_choose", loc),
        reply_markup=profile_edit_menu_kb(loc).as_markup(),
    )


# Field name -> (state, prompt_i18n_key, get_current_value from user)
_EDIT_FIELD_CONFIG = {
    "display_name": (ProfileState.display_name, "profile_name_prompt", lambda u: u.display_name or ""),
    "gender": (ProfileState.gender, "profile_gender_prompt", lambda u: u.gender or ""),
    "looking_for": (ProfileState.looking_for, "profile_looking_prompt", lambda u: u.looking_for or ""),
    "city": (ProfileState.city, "profile_city_prompt", lambda u: u.city or ""),
    "photo": (ProfileState.photo, "profile_photo_prompt", lambda u: ""),
    "description": (ProfileState.description, "profile_description_prompt", lambda u: u.description or ""),
    "interests": (ProfileState.interests, "profile_interests_prompt", lambda u: u.interests or ""),
    "movies": (ProfileState.movies, "profile_movies_prompt", lambda u: u.movies or ""),
    "series": (ProfileState.series, "profile_series_prompt", lambda u: u.series or ""),
    "music": (ProfileState.music, "profile_music_prompt", lambda u: u.music or ""),
}


@router.callback_query(F.data.startswith("edit_profile:"))
async def profile_edit_choose_field(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        return
    part = callback.data.split(":", 1)[1]
    if part == "done":
        await callback.answer()
        await state.clear()
        async with async_session_factory() as session:
            user = await get_user_by_telegram_id(session, callback.from_user.id)
            loc = _locale(user) if user else "ru"
        await callback.message.answer(t("profile_edit_done", loc), reply_markup=main_menu_kb(loc))
        return
    if part == "more":
        await callback.answer()
        async with async_session_factory() as session:
            user = await get_user_by_telegram_id(session, callback.from_user.id)
            loc = _locale(user) if user else "ru"
        await callback.message.answer(
            t("profile_edit_about_section", loc),
            reply_markup=profile_edit_about_kb(loc).as_markup(),
        )
        return
    if part not in _EDIT_FIELD_CONFIG:
        await callback.answer()
        return
    await callback.answer()
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(session, callback.from_user.id)
        if not user:
            return
        loc = _locale(user)
    config = _EDIT_FIELD_CONFIG[part]
    field_state, prompt_key, get_current = config
    current = get_current(user)
    await state.update_data(edit_mode=True, editing_field=part)
    await state.set_state(field_state)
    na = t("profile_na", loc)
    current_str = current if current else na
    text = f"{t(prompt_key, loc)}\n{t('profile_edit_current', loc, value=current_str)}"
    if part == "photo":
        text = t(prompt_key, loc)
    skip_fields = ("description", "interests", "movies", "series", "music")
    if part == "gender":
        reply_markup = gender_choice_kb(loc).as_markup()
    elif part == "looking_for":
        reply_markup = looking_choice_kb(loc).as_markup()
    else:
        reply_markup = cancel_skip_kb(loc) if part in skip_fields else cancel_kb(loc)
    await callback.message.answer(text, reply_markup=reply_markup)


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
    data = await state.get_data()
    loc = data.get("locale", "ru")
    if not name or len(name) > 100:
        await message.answer(t("profile_name_invalid", loc))
        return
    if data.get("edit_mode"):
        async with async_session_factory() as session:
            user = await get_user_by_telegram_id(session, message.from_user.id)
            if user:
                user.display_name = name
                user.zodiac = zodiac_from_birth_date(user.birth_date)
                await session.commit()
            loc = _locale(user) if user else "ru"
        await state.update_data(editing_field=None)
        await _send_edit_menu(message, loc, state)
        return
    await state.update_data(display_name=name)
    await message.answer(
        t("profile_gender_prompt", loc),
        reply_markup=gender_choice_kb(loc).as_markup(),
    )
    await state.set_state(ProfileState.gender)


def _normalize_gender(value: str) -> str:
    """Callback value M/F/other -> stored value (M, F, other)."""
    v = (value or "").strip().lower()
    if v in ("m", "м"):
        return "M"
    if v in ("f", "ж"):
        return "F"
    if v == "other" or v == "другой":
        return "other"
    return value or ""


@router.callback_query(F.data.startswith("profile_gender:"), ProfileState.gender)
async def profile_gender_callback(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        return
    _, value = callback.data.split(":", 1)
    g = _normalize_gender(value)
    if not g:
        await callback.answer()
        return
    await callback.answer()
    data = await state.get_data()
    if data.get("edit_mode"):
        async with async_session_factory() as session:
            user = await get_user_by_telegram_id(session, callback.from_user.id)
            if user:
                user.gender = g
                user.zodiac = zodiac_from_birth_date(user.birth_date)
                await session.commit()
            loc = _locale(user) if user else "ru"
        await state.update_data(editing_field=None)
        await callback.message.answer(t("profile_edit_field_saved", loc))
        await _send_edit_menu(callback.message, loc, state)
        return
    await state.update_data(gender=g)
    loc = data.get("locale", "ru")
    await callback.message.answer(
        t("profile_looking_prompt", loc),
        reply_markup=looking_choice_kb(loc).as_markup(),
    )
    await state.set_state(ProfileState.looking_for)


@router.message(ProfileState.gender, F.text)
async def profile_gender_message(message: Message, state: FSMContext) -> None:
    """Обработка только отмены; выбор пола — по кнопкам."""
    data = await state.get_data()
    loc = data.get("locale", "ru")
    if message.text and message.text.strip() in _cancel_texts():
        await state.clear()
        async with async_session_factory() as session:
            user = await get_user_by_telegram_id(session, message.from_user.id)
            loc = _locale(user) if user else "ru"
        await message.answer(t("profile_cancelled", loc), reply_markup=main_menu_kb(loc))
        return
    await message.answer(t("profile_gender_prompt", loc), reply_markup=gender_choice_kb(loc).as_markup())


def _normalize_looking(value: str) -> str:
    """Callback value m/f/all -> stored value (m, f, all)."""
    v = (value or "").strip().lower()
    if v in ("m", "м"):
        return "m"
    if v in ("f", "ж"):
        return "f"
    if v in ("all", "все"):
        return "all"
    return value or ""


@router.callback_query(F.data.startswith("profile_looking:"), ProfileState.looking_for)
async def profile_looking_callback(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        return
    _, value = callback.data.split(":", 1)
    lf = _normalize_looking(value)
    if lf not in ("m", "f", "all"):
        await callback.answer()
        return
    await callback.answer()
    data = await state.get_data()
    if data.get("edit_mode"):
        async with async_session_factory() as session:
            user = await get_user_by_telegram_id(session, callback.from_user.id)
            if user:
                user.looking_for = lf
                user.zodiac = zodiac_from_birth_date(user.birth_date)
                await session.commit()
            loc = _locale(user) if user else "ru"
        await state.update_data(editing_field=None)
        await callback.message.answer(t("profile_edit_field_saved", loc))
        await _send_edit_menu(callback.message, loc, state)
        return
    await state.update_data(looking_for=lf)
    loc = data.get("locale", "ru")
    await callback.message.answer(t("profile_city_prompt", loc))
    await state.set_state(ProfileState.city)


@router.message(ProfileState.looking_for, F.text)
async def profile_looking_message(message: Message, state: FSMContext) -> None:
    """Обработка только отмены; выбор «Ищу» — по кнопкам."""
    data = await state.get_data()
    loc = data.get("locale", "ru")
    if message.text and message.text.strip() in _cancel_texts():
        await state.clear()
        async with async_session_factory() as session:
            user = await get_user_by_telegram_id(session, message.from_user.id)
            loc = _locale(user) if user else "ru"
        await message.answer(t("profile_cancelled", loc), reply_markup=main_menu_kb(loc))
        return
    await message.answer(
        t("profile_looking_prompt", loc),
        reply_markup=looking_choice_kb(loc).as_markup(),
    )


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
    data = await state.get_data()
    if data.get("edit_mode"):
        async with async_session_factory() as session:
            user = await get_user_by_telegram_id(session, message.from_user.id)
            if user:
                user.city = city
                user.zodiac = zodiac_from_birth_date(user.birth_date)
                await session.commit()
            loc = _locale(user) if user else "ru"
        await state.update_data(editing_field=None)
        await _send_edit_menu(message, loc, state)
        return
    await state.update_data(city=city)
    loc = data.get("locale", "ru")
    await message.answer(t("profile_photo_prompt", loc))
    await state.set_state(ProfileState.photo)


@router.message(ProfileState.photo, F.photo)
async def profile_photo(message: Message, state: FSMContext) -> None:
    photo = message.photo[-1]
    data = await state.get_data()
    if data.get("edit_mode"):
        async with async_session_factory() as session:
            user = await get_user_by_telegram_id(session, message.from_user.id)
            if user:
                user.profile_photo_file_id = photo.file_id
                user.zodiac = zodiac_from_birth_date(user.birth_date)
                await session.commit()
            loc = _locale(user) if user else "ru"
        await state.update_data(editing_field=None)
        await _send_edit_menu(message, loc, state)
        return
    await state.update_data(profile_photo_file_id=photo.file_id)
    loc = data.get("locale", "ru")
    await message.answer(
        t("profile_description_prompt", loc),
        reply_markup=cancel_skip_kb(loc),
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
    if desc == "-" or (message.text and message.text.strip() in _skip_texts()):
        desc = ""
    data = await state.get_data()
    if data.get("edit_mode"):
        async with async_session_factory() as session:
            user = await get_user_by_telegram_id(session, message.from_user.id)
            if user:
                user.description = desc or None
                user.zodiac = zodiac_from_birth_date(user.birth_date)
                await session.commit()
            loc = _locale(user) if user else "ru"
        await state.update_data(editing_field=None)
        await _send_edit_menu(message, loc, state)
        return
    await state.update_data(description=desc or None)
    loc = data.get("locale", "ru")
    await message.answer(t("profile_interests_prompt", loc), reply_markup=cancel_skip_kb(loc))
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
    if interests == "-" or (message.text and message.text.strip() in _skip_texts()):
        interests = ""
    data = await state.get_data()
    if data.get("edit_mode"):
        async with async_session_factory() as session:
            user = await get_user_by_telegram_id(session, message.from_user.id)
            if user:
                user.interests = interests or None
                user.zodiac = zodiac_from_birth_date(user.birth_date)
                await session.commit()
            loc = _locale(user) if user else "ru"
        await state.update_data(editing_field=None)
        await _send_edit_menu(message, loc, state)
        return
    await state.update_data(interests=interests or None)
    loc = data.get("locale", "ru")
    await message.answer(t("profile_movies_prompt", loc), reply_markup=cancel_skip_kb(loc))
    await state.set_state(ProfileState.movies)


@router.message(ProfileState.movies, F.text)
async def profile_movies(message: Message, state: FSMContext) -> None:
    if message.text and message.text.strip() in _cancel_texts():
        await state.clear()
        async with async_session_factory() as session:
            user = await get_user_by_telegram_id(session, message.from_user.id)
            loc = _locale(user) if user else "ru"
        await message.answer(t("profile_cancelled", loc), reply_markup=main_menu_kb(loc))
        return
    val = (message.text or "").strip()[:1024] if message.text else ""
    if val == "-" or (message.text and message.text.strip() in _skip_texts()):
        val = ""
    data = await state.get_data()
    if data.get("edit_mode"):
        async with async_session_factory() as session:
            user = await get_user_by_telegram_id(session, message.from_user.id)
            if user:
                user.movies = val or None
                user.zodiac = zodiac_from_birth_date(user.birth_date)
                await session.commit()
            loc = _locale(user) if user else "ru"
        await state.update_data(editing_field=None)
        await _send_edit_menu(message, loc, state)
        return
    await state.update_data(movies=val or None)
    loc = data.get("locale", "ru")
    await message.answer(t("profile_series_prompt", loc), reply_markup=cancel_skip_kb(loc))
    await state.set_state(ProfileState.series)


@router.message(ProfileState.series, F.text)
async def profile_series(message: Message, state: FSMContext) -> None:
    if message.text and message.text.strip() in _cancel_texts():
        await state.clear()
        async with async_session_factory() as session:
            user = await get_user_by_telegram_id(session, message.from_user.id)
            loc = _locale(user) if user else "ru"
        await message.answer(t("profile_cancelled", loc), reply_markup=main_menu_kb(loc))
        return
    val = (message.text or "").strip()[:1024] if message.text else ""
    if val == "-" or (message.text and message.text.strip() in _skip_texts()):
        val = ""
    data = await state.get_data()
    if data.get("edit_mode"):
        async with async_session_factory() as session:
            user = await get_user_by_telegram_id(session, message.from_user.id)
            if user:
                user.series = val or None
                user.zodiac = zodiac_from_birth_date(user.birth_date)
                await session.commit()
            loc = _locale(user) if user else "ru"
        await state.update_data(editing_field=None)
        await _send_edit_menu(message, loc, state)
        return
    await state.update_data(series=val or None)
    loc = data.get("locale", "ru")
    await message.answer(t("profile_music_prompt", loc), reply_markup=cancel_skip_kb(loc))
    await state.set_state(ProfileState.music)


@router.message(ProfileState.music, F.text)
async def profile_music(message: Message, state: FSMContext) -> None:
    if message.text and message.text.strip() in _cancel_texts():
        await state.clear()
        async with async_session_factory() as session:
            user = await get_user_by_telegram_id(session, message.from_user.id)
            loc = _locale(user) if user else "ru"
        await message.answer(t("profile_cancelled", loc), reply_markup=main_menu_kb(loc))
        return
    val = (message.text or "").strip()[:1024] if message.text else ""
    if val == "-" or (message.text and message.text.strip() in _skip_texts()):
        val = ""
    data = await state.get_data()
    if data.get("edit_mode"):
        async with async_session_factory() as session:
            user = await get_user_by_telegram_id(session, message.from_user.id)
            if user:
                user.music = val or None
                user.zodiac = zodiac_from_birth_date(user.birth_date)
                await session.commit()
            loc = _locale(user) if user else "ru"
        await state.update_data(editing_field=None)
        await _send_edit_menu(message, loc, state)
        return
    await state.update_data(music=val or None)
    data = await state.get_data()
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(session, message.from_user.id)
        if not user:
            await message.answer("Ошибка: пользователь не найден.")
            await state.clear()
            return
        loc = _locale(user)
        user.display_name = data.get("display_name")
        computed_age = age_from_birth_date(user.birth_date)
        user.age = computed_age if computed_age is not None else user.age
        user.gender = data.get("gender")
        user.looking_for = data.get("looking_for")
        user.city = data.get("city")
        user.profile_photo_file_id = data.get("profile_photo_file_id")
        user.description = data.get("description") or None
        user.interests = data.get("interests") or None
        user.movies = data.get("movies") or None
        user.series = data.get("series") or None
        user.music = data.get("music") or None
        user.zodiac = zodiac_from_birth_date(user.birth_date)
        user.profile_filled = True
        await session.commit()
        await session.refresh(user)
    await state.clear()
    await message.answer(t("profile_saved", loc), reply_markup=main_menu_kb(loc))


async def _send_profile_view(message: Message, user, locale: str) -> None:
    na = t("profile_na", locale)
    em = gender_emoji(user.gender)
    parts = [
        f"{em} {user.display_name or user.first_name}, {user.age}",
        f"{t('profile_looking', locale)}: {user.looking_for}",
        f"{t('profile_city', locale)}: {user.city or na}",
    ]
    if user.description:
        parts.append(f"{t('profile_about', locale)}: {user.description[:200]}{'…' if len(user.description) > 200 else ''}")
    if user.interests:
        parts.append(f"{t('profile_interests', locale)}: {user.interests[:150]}…" if len(user.interests) > 150 else f"{t('profile_interests', locale)}: {user.interests}")
    # Показываем фильмы/сериалы/музыку (новые поля или старый movies_music в одну строку)
    _movies = user.movies or (user.movies_music if not (user.movies or user.series or user.music) else None)
    if _movies:
        parts.append(f"{t('profile_movies', locale)}: {_movies[:150]}{'…' if len(_movies) > 150 else ''}")
    if user.series:
        parts.append(f"{t('profile_series', locale)}: {user.series[:150]}{'…' if len(user.series) > 150 else ''}")
    if user.music:
        parts.append(f"{t('profile_music', locale)}: {user.music[:150]}{'…' if len(user.music) > 150 else ''}")
    if user.zodiac:
        zkey = "zodiac_" + user.zodiac
        zstr = t(zkey, locale)
        if zstr == zkey:
            zstr = user.zodiac
        parts.append(f"{t('profile_field_zodiac', locale)}: {zstr}")
    text = "\n".join(parts)
    if user.profile_photo_file_id:
        await message.answer_photo(user.profile_photo_file_id, caption=text)
    else:
        await message.answer(text)
