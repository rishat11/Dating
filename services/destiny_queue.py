"""Queue for destiny index recalculation (in-memory or Redis). Idempotent by message_id."""
import asyncio
import json
import logging
from typing import Optional, Set

from config import get_config
from i18n import t
from services.redis_client import (
    get_redis,
    redis_lpush,
    redis_blpop,
    redis_set,
    redis_delete,
    DESTINY_QUEUE_KEY,
    DESTINY_CACHE_PREFIX,
    DESTINY_PROCESSED_PREFIX,
    PROCESSED_TTL,
)

logger = logging.getLogger(__name__)

# In-memory fallback
_processed_message_ids: Set[int] = set()
_queue: asyncio.Queue = asyncio.Queue()
_queue_worker_started = False
_bot = None


def set_destiny_bot(bot):
    global _bot
    _bot = bot


def _use_redis() -> bool:
    return get_redis() is not None


def enqueue_destiny_recalc(
    match_id: int,
    message_id: int,
    *,
    sender_id: Optional[int] = None,
    text: Optional[str] = None,
    msg_type: Optional[str] = None,
    length: int = 0,
    duration_seconds: Optional[int] = None,
) -> None:
    """Enqueue recalc. With Redis: push to list and invalidate cache. Worker will skip if message_id already processed."""
    item = {
        "match_id": match_id,
        "message_id": message_id,
        "sender_id": sender_id,
        "text": text,
        "type": msg_type,
        "length": length,
        "duration_seconds": duration_seconds,
    }
    if _use_redis():
        asyncio.create_task(_redis_enqueue(match_id, item))
    else:
        _queue.put_nowait(item)


async def _redis_enqueue(match_id: int, item: dict) -> None:
    try:
        await redis_delete(DESTINY_CACHE_PREFIX + str(match_id))
        await redis_lpush(DESTINY_QUEUE_KEY, json.dumps(item, default=str))
    except Exception as e:
        logger.warning("Redis enqueue: %s", e)
        _queue.put_nowait(item)


def _mark_processed(message_id: int) -> None:
    _processed_message_ids.add(message_id)
    if len(_processed_message_ids) > 10000:
        _processed_message_ids.clear()


def _was_processed(message_id: int) -> bool:
    return message_id in _processed_message_ids


async def _redis_was_processed(message_id: int) -> bool:
    from services.redis_client import redis_get
    v = await redis_get(DESTINY_PROCESSED_PREFIX + str(message_id))
    return v is not None


async def _redis_mark_processed(message_id: int) -> None:
    await redis_set(DESTINY_PROCESSED_PREFIX + str(message_id), "1", PROCESSED_TTL)


async def _process_one(item: dict) -> None:
    from datetime import datetime, timedelta
    from sqlalchemy import select
    from db.database import async_session_factory
    from db.models import Match, Message as MsgModel, User
    from services.destiny_service import recalc_destiny_index_for_match
    from config import get_config
    config = get_config()
    mid = item.get("message_id")
    if mid is not None:
        if _use_redis():
            if await _redis_was_processed(mid):
                return
        elif _was_processed(mid):
            return
    match_id = item["match_id"]
    sender_id = item.get("sender_id")
    try:
        async with async_session_factory() as session:
            from db.models import DestinyIndex
            match = await session.get(Match, match_id)
            if not match:
                return
            r = await session.execute(select(DestinyIndex).where(DestinyIndex.match_id == match_id))
            row_before = r.scalar_one_or_none()
            di_before = row_before.current_percent if row_before else None
            new_pct, reason, level_up = await recalc_destiny_index_for_match(
                session,
                match_id,
                new_message_id=mid,
                new_text=item.get("text"),
                new_type=item.get("type"),
                new_length=item.get("length", 0),
                new_duration_seconds=item.get("duration_seconds"),
            )
            if mid is not None:
                if _use_redis():
                    await _redis_mark_processed(mid)
                else:
                    _mark_processed(mid)
            # Redis cache: write current percent
            if _use_redis():
                await redis_set(DESTINY_CACHE_PREFIX + str(match_id), str(new_pct), config.destiny_index_cache_ttl)
            # Notify conflict (freeze)
            if _bot and reason and ("Конфликт" in reason or "заморожен" in reason):
                match = await session.get(Match, match_id)
                u1 = await session.get(User, match.user_1_id)
                u2 = await session.get(User, match.user_2_id)
                freeze_hours = config.destiny_freeze_hours
                for u in (u1, u2):
                    if u and u.telegram_id:
                        try:
                            loc = (u.locale or "ru").lower()
                            conflict_msg = t("index_freeze_message", loc, hours=freeze_hours)
                            await _bot.send_message(u.telegram_id, conflict_msg)
                        except Exception as e:
                            logger.warning("Conflict notify: %s", e)
            # "Спасите индекс": if partner was silent > 6h, notify partner
            if _bot and sender_id and match:
                partner_id = match.other_user_id(sender_id)
                last_from_partner = await session.execute(
                    select(MsgModel)
                    .where(MsgModel.match_id == match_id, MsgModel.sender_id == partner_id)
                    .order_by(MsgModel.created_at.desc())
                    .limit(1)
                )
                last_msg = last_from_partner.scalar_one_or_none()
                if last_msg:
                    silence_h = (datetime.utcnow() - last_msg.created_at).total_seconds() / 3600
                    if silence_h >= config.save_index_silence_hours:
                        partner = await session.get(User, partner_id)
                        writer = await session.get(User, sender_id)
                        if partner and partner.telegram_id and writer:
                            try:
                                loc = (partner.locale or "ru").lower()
                                writer_name = writer.display_name or writer.first_name
                                msg = t(
                                    "index_may_drop",
                                    loc,
                                    writer_name=writer_name,
                                    hours=int(silence_h),
                                )
                                await _bot.send_message(partner.telegram_id, msg)
                            except Exception as e:
                                logger.warning("Save index notify: %s", e)
    except Exception as e:
        logger.exception("Destiny recalc error for match_id=%s: %s", match_id, e)


async def _worker() -> None:
    if _use_redis():
        while True:
            try:
                raw = await redis_blpop(DESTINY_QUEUE_KEY, timeout=5)
                if raw:
                    try:
                        item = json.loads(raw)
                        await _process_one(item)
                    except json.JSONDecodeError as e:
                        logger.warning("Destiny queue invalid JSON: %s", e)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Destiny queue worker: %s", e)
    else:
        while True:
            try:
                item = await _queue.get()
                await _process_one(item)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Destiny queue worker: %s", e)


def start_destiny_worker() -> asyncio.Task:
    """Start background worker for destiny queue. With Redis uses BLPOP; else in-memory queue. Call from main."""
    global _queue_worker_started
    if _queue_worker_started:
        return asyncio.create_task(asyncio.sleep(0))
    _queue_worker_started = True
    return asyncio.create_task(_worker())
