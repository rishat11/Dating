"""User and profile service."""
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> Optional[User]:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id, User.deleted_at.is_(None)))
    return result.scalar_one_or_none()


async def get_user_by_telegram_id_include_deleted(session: AsyncSession, telegram_id: int) -> Optional[User]:
    """Return user by telegram_id even if soft-deleted (deleted_at set). Used for restore on /start."""
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
) -> User:
    user = await get_user_by_telegram_id(session, telegram_id)
    if user:
        if username is not None:
            user.username = username
        if first_name is not None:
            user.first_name = first_name
        await session.commit()
        await session.refresh(user)
        return user
    # User may be soft-deleted: restore and reuse instead of INSERT (avoids UNIQUE on telegram_id)
    user = await get_user_by_telegram_id_include_deleted(session, telegram_id)
    if user:
        user.deleted_at = None
        if username is not None:
            user.username = username
        if first_name is not None:
            user.first_name = first_name
        await session.commit()
        await session.refresh(user)
        return user
    user = User(
        telegram_id=telegram_id,
        username=username or "",
        first_name=first_name or "User",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def count_likes_today(session: AsyncSession, user_id: int) -> int:
    from sqlalchemy import func
    from db.models import Like
    from datetime import date
    today = date.today()
    result = await session.execute(
        select(func.count(Like.id)).where(
            Like.sender_id == user_id,
            func.date(Like.created_at) == today,
        )
    )
    return result.scalar() or 0
