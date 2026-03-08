"""Permanent cleanup of accounts past recovery period (e.g. 30 days after deleted_at)."""
import logging
from datetime import datetime, timedelta

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import async_session_factory
from db.models import User

logger = logging.getLogger(__name__)
DEFAULT_RECOVERY_DAYS = 30


async def cleanup_deleted_accounts(recovery_days: int = DEFAULT_RECOVERY_DAYS) -> int:
    """Anonymize users with deleted_at older than recovery_days. Returns count."""
    if recovery_days <= 0:
        return 0
    cutoff = datetime.utcnow() - timedelta(days=recovery_days)
    async with async_session_factory() as session:
        result = await session.execute(
            update(User)
            .where(User.deleted_at.isnot(None), User.deleted_at < cutoff)
            .values(
                first_name="Deleted",
                username=None,
                photo_file_id=None,
                display_name=None,
                age=None,
                gender=None,
                looking_for=None,
                city=None,
                profile_photo_file_id=None,
                description=None,
                interests=None,
                movies_music=None,
                zodiac=None,
                profile_filled=False,
                latitude=None,
                longitude=None,
                location_updated_at=None,
            )
        )
        await session.commit()
        count = result.rowcount if result.rowcount is not None else 0
    logger.info("Deleted accounts cleanup: anonymized %s users older than %s days", count, recovery_days)
    return count


async def cleanup_loop(recovery_days: int = DEFAULT_RECOVERY_DAYS, interval_seconds: int = 86400) -> None:
    """Background loop: run cleanup every interval_seconds (default 24h)."""
    import asyncio
    while True:
        try:
            await cleanup_deleted_accounts(recovery_days)
        except Exception as e:
            logger.exception("Deleted cleanup job: %s", e)
        await asyncio.sleep(interval_seconds)
