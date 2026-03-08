"""Message retention: delete or anonymize messages older than N months."""
import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import async_session_factory
from db.models import Message

logger = logging.getLogger(__name__)


async def run_retention(months: int) -> int:
    """Delete messages older than months. Returns count deleted."""
    if months <= 0:
        return 0
    cutoff = datetime.utcnow() - timedelta(days=months * 30)
    async with async_session_factory() as session:
        result = await session.execute(delete(Message).where(Message.created_at < cutoff))
        await session.commit()
        count = result.rowcount if result.rowcount is not None else 0
    logger.info("Message retention: deleted %s messages older than %s months", count, months)
    return count


async def retention_loop(months: int, interval_seconds: int = 86400) -> None:
    """Background loop: run retention every interval_seconds (default 24h)."""
    while True:
        try:
            await run_retention(months)
        except Exception as e:
            logger.exception("Retention job: %s", e)
        await asyncio.sleep(interval_seconds)
