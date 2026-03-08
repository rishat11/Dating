"""Chat helpers: previous sender in match for minimal message labels."""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Message as MsgModel


async def get_previous_sender_id(
    session: AsyncSession, match_id: int, before_message_id: int
) -> Optional[int]:
    """Sender_id последнего сообщения в match с id < before_message_id, или None."""
    result = await session.execute(
        select(MsgModel.sender_id)
        .where(MsgModel.match_id == match_id, MsgModel.id < before_message_id)
        .order_by(MsgModel.id.desc())
        .limit(1)
    )
    return result.scalars().first()
