"""Destiny Index calculation (MVP: keywords, length, time, emoji)."""
from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Match, Message, DestinyIndex, DestinyEvent, MessageType
from services.destiny_keywords import calc_lexical_bonus

# Эмодзи позитив/негатив (упрощённо)
POSITIVE_EMOJI = {"❤", "🔥", "😍", "💕", "😊", "🤗", "👍", "✨", "💖", "😘", "🥰", "💋"}
NEGATIVE_EMOJI = {"😠", "👿", "😡", "💔", "😞", "😢", "👎"}
# Мат-маркеры для заморозки (короткий список)
NEGATIVE_WORDS = {"мат", "дурак", "идиот", "отстань", "надоел", "ненавижу"}


def _emoji_bonus(text: str) -> float:
    pos = sum(1 for c in text if c in POSITIVE_EMOJI or c in "❤️🔥😍💕😊🤗👍✨💖😘🥰💋")
    neg = sum(1 for c in text if c in NEGATIVE_EMOJI or c in "😠👿😡💔😞😢👎")
    return min(2.0, pos * 0.5) - min(2.0, neg * 0.5)


def _length_bonus(length: int) -> float:
    if length >= 100:
        return 1.0
    if length >= 50:
        return 0.5
    if length <= 3:
        return -0.3
    return 0.0


def _has_negative(text: str) -> bool:
    t = text.lower()
    return any(w in t for w in NEGATIVE_WORDS)


def get_level_name(percent: float) -> str:
    """Return i18n key for level (use with t(key, locale))."""
    if percent <= 15:
        return "level_strangers"
    if percent <= 30:
        return "level_acquaintances"
    if percent <= 50:
        return "level_kindred"
    if percent <= 70:
        return "level_potential"
    if percent <= 90:
        return "level_half"
    return "level_destiny"


def format_progress_bar(percent: float, width: int = 10) -> str:
    filled = int(percent / 100 * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {round(percent)}%"


# Thresholds for levels (percent boundaries)
_THRESHOLDS = (15, 30, 50, 70, 90, 100)


def get_next_threshold(percent: float) -> Tuple[int, int]:
    """Return (next_threshold_percent, estimated_messages_to_reach). E.g. at 47% -> (50, 2)."""
    for t in _THRESHOLDS:
        if percent < t:
            delta = t - percent
            # Heuristic: ~2-3% per "good" message -> messages ~ ceil(delta / 2.5)
            est = max(1, round(delta / 2.5))
            return (t, est)
    return (100, 0)


async def get_or_create_destiny_index(session: AsyncSession, match_id: int) -> DestinyIndex:
    result = await session.execute(select(DestinyIndex).where(DestinyIndex.match_id == match_id))
    row = result.scalar_one_or_none()
    if row:
        return row
    row = DestinyIndex(match_id=match_id)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def recalc_destiny_index_for_match(
    session: AsyncSession,
    match_id: int,
    *,
    new_message_id: Optional[int] = None,
    new_text: Optional[str] = None,
    new_type: Optional[str] = None,
    new_length: int = 0,
    new_duration_seconds: Optional[int] = None,
) -> Tuple[float, Optional[str], bool]:
    """
    Recalculate destiny index for match (MVP logic).
    Returns (new_percent, reason_for_change, level_increased).
    Idempotent: if new_message_id was already processed, skip (caller should track by message_id).
    """
    from config import get_config
    from db.models import MatchStatus
    config = get_config()
    match = await session.get(Match, match_id)
    if not match or match.status != MatchStatus.ACTIVE.value:
        return 0.0, None, False
    di = await get_or_create_destiny_index(session, match_id)
    if di.frozen_until and di.frozen_until > datetime.utcnow():
        return di.current_percent, None, False

    # Last N messages for context (e.g. 50)
    result = await session.execute(
        select(Message)
        .where(Message.match_id == match_id)
        .order_by(Message.created_at.desc())
        .limit(50)
    )
    messages = list(reversed(result.scalars().all()))

    delta = 0.0
    reason = None

    # New message contribution (if provided)
    if new_text is not None:
        if _has_negative(new_text):
            di.frozen_until = datetime.utcnow() + timedelta(hours=config.destiny_freeze_hours)
            await session.commit()
            await session.refresh(di)
            return di.current_percent, "Конфликт: индекс заморожен на 3 часа.", False
        delta += calc_lexical_bonus(new_text)
        delta += _emoji_bonus(new_text)
        delta += _length_bonus(new_length)
        if reason is None and delta != 0:
            reason = f"Новое сообщение: +{round(delta, 1)}%"
    if new_type == MessageType.VOICE.value:
        delta += 5.0
        if new_duration_seconds and new_duration_seconds >= 60:
            delta += 2.0
        if reason is None:
            reason = "Голосовое сообщение +5%"

    # Behavioral: fast replies (<2 min) — bonus once per hour; silence penalty
    for i in range(1, len(messages)):
        prev, curr = messages[i - 1], messages[i]
        if curr.sender_id == prev.sender_id:
            continue
        diff = (curr.created_at - prev.created_at).total_seconds()
        if diff <= 120:
            delta += 0.5
            if reason is None:
                reason = "Быстрый ответ"
            break
        if diff >= 24 * 3600:
            delta -= 0.5 * (diff / 3600)
            if reason is None:
                reason = "Долгое молчание"

    new_percent = max(0.0, min(100.0, di.current_percent + delta))
    level_before = get_level_name(di.current_percent)
    level_after = get_level_name(new_percent)
    level_increased = (level_after != level_before) or (new_percent > di.current_percent)

    di.current_percent = new_percent
    di.updated_at = datetime.utcnow()
    if new_percent >= 16:
        di.flag_playlist = True
    if new_percent >= 31:
        di.flag_challenges = True
    if new_percent >= 51:
        di.flag_cloud = True
    if new_percent >= 90:
        di.flag_voting = True
    if new_percent >= 100:
        di.flag_pdf = True

    session.add(DestinyEvent(match_id=match_id, delta=delta, reason=reason))
    await session.commit()
    await session.refresh(di)
    return new_percent, reason, level_increased
