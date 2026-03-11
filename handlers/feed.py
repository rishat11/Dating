"""Feed: cards by filters, like/skip, daily limit, mutual match → chat + notify; distance when geo enabled."""
import logging
from typing import Optional, List

from aiogram import Bot, F, Router
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import select, func, or_, and_, case
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import async_session_factory
from db.models import User, Like, Match, MatchStatus
from services.user_service import get_user_by_telegram_id, count_likes_today
from services.match_service import like_exists, create_match_if_mutual
from services.feed_service import haversine_km, format_distance_km, gender_emoji
from config import get_config
from keyboards.common import main_menu_kb
from keyboards.feed import feed_actions_kb
from i18n import t

logger = logging.getLogger(__name__)
router = Router(name="feed")

FEED_CANDIDATES_LIMIT = 100


def _looking_matches(looking: str, user_gender: str) -> bool:
    if not looking or looking in ("все", "all"):
        return True
    return bool(user_gender and user_gender.lower().startswith((looking or "").lower()[:1]))


async def _get_next_feed_user(
    session: AsyncSession,
    viewer_id: int,
    viewer: User,
    min_age: Optional[int] = None,
    max_age: Optional[int] = None,
    gender_filter: Optional[str] = None,
    city_filter: Optional[str] = None,
) -> Optional[tuple[User, Optional[float]]]:
    """Return (user, distance_km or None). When viewer has coords: sort by distance (with coords first).
    Exclude: active match partners and users we've liked."""
    looking = (viewer.looking_for or "все").lower()
    active_partners = await session.execute(
        select(
            case((Match.user_1_id == viewer_id, Match.user_2_id), else_=Match.user_1_id)
        ).select_from(Match).where(
            or_(Match.user_1_id == viewer_id, Match.user_2_id == viewer_id),
            Match.status == MatchStatus.ACTIVE.value,
        )
    )
    active_ids = set(active_partners.scalars().all())
    liked = await session.execute(select(Like.receiver_id).where(Like.sender_id == viewer_id))
    liked_ids = set(liked.scalars().all())
    exclude_ids = active_ids | liked_ids
    base_q = (
        select(User)
        .where(User.id != viewer_id)
        .where(User.deleted_at.is_(None))
        .where(User.profile_filled == True)
    )
    if exclude_ids:
        base_q = base_q.where(User.id.not_in(exclude_ids))
    if min_age is not None:
        base_q = base_q.where(User.age >= min_age)
    if max_age is not None:
        base_q = base_q.where(User.age <= max_age)
    if gender_filter:
        base_q = base_q.where(User.gender.ilike(f"{gender_filter}%"))
    if city_filter and (city_filter or "").lower() not in ("любой", "any"):
        base_q = base_q.where(User.city.ilike(f"%{city_filter}%"))

    viewer_has_coords = viewer.latitude is not None and viewer.longitude is not None

    if viewer_has_coords:
        # With coords: fetch users with coords first, sort by distance
        q_with = base_q.where(User.latitude.isnot(None), User.longitude.isnot(None)).limit(FEED_CANDIDATES_LIMIT)
        result = await session.execute(q_with)
        candidates: List[User] = [u for u in result.scalars().all() if _looking_matches(looking, u.gender or "")]
        if candidates:
            with_dist = [
                (u, haversine_km(viewer.latitude, viewer.longitude, u.latitude, u.longitude))
                for u in candidates
            ]
            with_dist.sort(key=lambda x: x[1])
            return with_dist[0]
        # No one with coords: fallback to users without coords (random)
        q_no = base_q.where(User.latitude.is_(None)).order_by(func.random()).limit(1)
        res = await session.execute(q_no)
        user = res.scalar_one_or_none()
        if user and _looking_matches(looking, user.gender or ""):
            return (user, None)
        return None

    # No viewer coords: random order as before
    q = base_q.order_by(func.random()).limit(1)
    result = await session.execute(q)
    user = result.scalar_one_or_none()
    if not user or not _looking_matches(looking, user.gender or ""):
        return None
    return (user, None)


def _card_text(
    user: User,
    locale: str = "ru",
    distance_km: Optional[float] = None,
    likes_today: Optional[int] = None,
    likes_limit: Optional[int] = None,
) -> str:
    em = gender_emoji(user.gender)
    parts = [f"{em} {user.display_name or user.first_name}, {user.age}"]
    if distance_km is not None:
        parts.append(format_distance_km(distance_km, locale))
    if user.city:
        parts.append(f"📍 {user.city}")
    if user.description:
        parts.append(user.description[:300] + ("…" if len(user.description) > 300 else ""))
    if likes_today is not None and likes_limit is not None:
        parts.append(t("feed_likes_today", locale, count=likes_today, limit=likes_limit))
    return "\n".join(parts)


async def _show_next_card(
    callback: CallbackQuery,
    bot: Bot,
    next_user: User,
    loc: str,
    dist: Optional[float],
    likes_today: int,
    likes_limit: int,
) -> None:
    """Show next feed card by editing the current message when possible, else send new."""
    card_text = _card_text(
        next_user, loc, dist,
        likes_today=likes_today, likes_limit=likes_limit,
    )
    kb = feed_actions_kb(next_user.id, loc).as_markup()
    chat_id = callback.message.chat.id if callback.message else 0
    message_id = callback.message.message_id if callback.message else 0
    try:
        if next_user.profile_photo_file_id:
            media = InputMediaPhoto(media=next_user.profile_photo_file_id, caption=card_text)
            await bot.edit_message_media(
                chat_id=chat_id,
                message_id=message_id,
                media=media,
                reply_markup=kb,
            )
        else:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=card_text,
                reply_markup=kb,
            )
    except (TelegramBadRequest, Exception):
        if callback.message:
            if next_user.profile_photo_file_id:
                await callback.message.answer_photo(
                    next_user.profile_photo_file_id,
                    caption=card_text,
                    reply_markup=kb,
                )
            else:
                await callback.message.answer(card_text, reply_markup=kb)


async def _send_card(
    message: Message,
    user: User,
    viewer_id: int,
    locale: str = "ru",
    distance_km: Optional[float] = None,
    likes_today: Optional[int] = None,
    likes_limit: Optional[int] = None,
) -> None:
    text = _card_text(user, locale, distance_km, likes_today, likes_limit)
    kb = feed_actions_kb(user.id, locale).as_markup()
    if user.profile_photo_file_id:
        await message.answer_photo(
            user.profile_photo_file_id,
            caption=text,
            reply_markup=kb,
        )
    else:
        await message.answer(text, reply_markup=kb)


@router.message(F.text.in_({t("menu_feed", "ru"), t("menu_feed", "en")}))
async def feed_open(message: Message, state: FSMContext) -> None:
    await state.clear()
    config = get_config()
    async with async_session_factory() as session:
        viewer = await get_user_by_telegram_id(session, message.from_user.id)
        if not viewer or not viewer.is_registered():
            await message.answer(t("feed_register_first", getattr(viewer, "locale", None) or "ru"))
            return
        if not viewer.is_profile_filled():
            await message.answer(t("feed_fill_profile", getattr(viewer, "locale", None) or "ru"))
            return
        loc = getattr(viewer, "locale", None) or "ru"
        from services.rate_limit import check_rate_limit
        wait_min = await check_rate_limit(viewer.id, "feed_open", config.feed_requests_per_minute, 60)
        if wait_min is not None:
            await message.answer(t("rate_limit", loc, min=wait_min))
            return
        pair = await _get_next_feed_user(session, viewer.id, viewer)
        today_count = await count_likes_today(session, viewer.id)
    if not pair:
        await message.answer(t("feed_empty", loc))
        return
    next_user, dist = pair
    await _send_card(
        message, next_user, viewer.id, loc, dist,
        likes_today=today_count, likes_limit=config.daily_likes_limit,
    )


@router.callback_query(F.data.startswith("like:"))
async def feed_like(callback: CallbackQuery, bot: Bot) -> None:
    if not callback.data or not callback.message:
        return
    try:
        receiver_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        async with async_session_factory() as session:
            viewer = await get_user_by_telegram_id(session, callback.from_user.id)
            loc = getattr(viewer, "locale", None) or "ru" if viewer else "ru"
        await callback.answer(t("error", loc))
        return
    await callback.answer()
    try:
        config = get_config()
        async with async_session_factory() as session:
            viewer = await get_user_by_telegram_id(session, callback.from_user.id)
            if not viewer or not viewer.is_profile_filled():
                await callback.message.answer(t("feed_fill_anketa", getattr(viewer, "locale", None) or "ru"))
                return
            loc = getattr(viewer, "locale", None) or "ru"
            from services.rate_limit import check_rate_limit
            wait_min = await check_rate_limit(viewer.id, "feed_action", config.feed_requests_per_minute, 60)
            if wait_min is not None:
                await callback.message.answer(t("rate_limit", loc, min=wait_min))
                return
            today_count = await count_likes_today(session, viewer.id)
            if today_count >= config.daily_likes_limit:
                await callback.message.answer(t("feed_likes_limit", loc, limit=config.daily_likes_limit))
                return
            match = await create_match_if_mutual(session, viewer.id, receiver_id)
            if match:
                receiver = await session.get(User, receiver_id)
                rname = (receiver.display_name or receiver.first_name) if receiver else "?"
                if receiver and receiver.telegram_id:
                    await bot.send_message(
                        receiver.telegram_id,
                        t("feed_mutual_them", loc, name=viewer.display_name or viewer.first_name),
                        reply_markup=main_menu_kb(getattr(receiver, "locale", None) or "ru"),
                    )
                await callback.message.answer(
                    t("feed_mutual_you", loc, name=rname),
                    reply_markup=main_menu_kb(loc),
                )
                return
            await callback.message.answer(t("feed_like_sent", loc))
            pair = await _get_next_feed_user(session, viewer.id, viewer)
            today_count = await count_likes_today(session, viewer.id)
            if pair:
                next_user, dist = pair
                await _show_next_card(
                    callback, bot, next_user, loc, dist,
                    likes_today=today_count, likes_limit=config.daily_likes_limit,
                )
            else:
                await callback.message.answer(t("feed_more_later", loc))
    except Exception as e:
        logger.exception("feed_like: %s", e)
        async with async_session_factory() as session:
            viewer = await get_user_by_telegram_id(session, callback.from_user.id)
            loc = getattr(viewer, "locale", None) or "ru" if viewer else "ru"
        await callback.message.answer(t("feed_error", loc))


@router.callback_query(F.data.startswith("skip:"))
async def feed_skip(callback: CallbackQuery, bot: Bot) -> None:
    if not callback.data or not callback.message:
        return
    try:
        _ = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        async with async_session_factory() as session:
            viewer = await get_user_by_telegram_id(session, callback.from_user.id)
            loc = getattr(viewer, "locale", None) or "ru" if viewer else "ru"
        await callback.answer(t("error", loc))
        return
    await callback.answer()
    config = get_config()
    async with async_session_factory() as session:
        viewer = await get_user_by_telegram_id(session, callback.from_user.id)
        if not viewer or not viewer.is_profile_filled():
            await callback.message.answer(t("feed_fill_anketa", getattr(viewer, "locale", None) or "ru"))
            return
        loc = getattr(viewer, "locale", None) or "ru"
        from services.rate_limit import check_rate_limit
        wait_min = await check_rate_limit(viewer.id, "feed_action", config.feed_requests_per_minute, 60)
        if wait_min is not None:
            await callback.message.answer(t("rate_limit", loc, min=wait_min))
            return
        pair = await _get_next_feed_user(session, viewer.id, viewer)
        today_count = await count_likes_today(session, viewer.id)
    if pair:
        next_user, dist = pair
        await _show_next_card(
            callback, bot, next_user, loc, dist,
            likes_today=today_count, likes_limit=config.daily_likes_limit,
        )
    else:
        await callback.message.answer(t("feed_more_later", loc))
