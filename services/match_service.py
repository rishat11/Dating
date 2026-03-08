"""Match and like service."""
from typing import List, Optional

from sqlalchemy import select, and_, or_
from sqlalchemy.orm import aliased, selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User, Match, Like, MatchStatus


async def get_mutual_match(session: AsyncSession, user_1_id: int, user_2_id: int) -> Optional[Match]:
    a, b = min(user_1_id, user_2_id), max(user_1_id, user_2_id)
    result = await session.execute(
        select(Match).where(
            and_(
                ((Match.user_1_id == a) & (Match.user_2_id == b)),
                Match.status == MatchStatus.ACTIVE.value,
            )
        )
    )
    return result.scalar_one_or_none()


async def like_exists(session: AsyncSession, sender_id: int, receiver_id: int) -> bool:
    result = await session.execute(
        select(Like).where(Like.sender_id == sender_id, Like.receiver_id == receiver_id)
    )
    return result.scalar_one_or_none() is not None


async def create_match_if_mutual(
    session: AsyncSession, sender_id: int, receiver_id: int
) -> Optional[Match]:
    from db.models import DestinyIndex
    if await like_exists(session, sender_id, receiver_id):
        return await get_mutual_match(session, sender_id, receiver_id)
    like = Like(sender_id=sender_id, receiver_id=receiver_id)
    session.add(like)
    await session.flush()
    reverse = await like_exists(session, receiver_id, sender_id)
    if not reverse:
        await session.commit()
        return None
    match = Match(user_1_id=min(sender_id, receiver_id), user_2_id=max(sender_id, receiver_id))
    session.add(match)
    await session.flush()
    session.add(DestinyIndex(match_id=match.id))
    await session.commit()
    await session.refresh(match)
    try:
        from services.audit import audit_match_created
        audit_match_created(match.id, match.user_1_id, match.user_2_id)
    except Exception:
        pass
    return match


async def get_user_matches(session: AsyncSession, user_id: int) -> List[Match]:
    """Active matches for user; exclude matches where partner has deleted_at set.
    Eager-loads user_1 and user_2 so partner_of() can be used after session is closed."""
    u1 = aliased(User)
    u2 = aliased(User)
    result = await session.execute(
        select(Match)
        .options(selectinload(Match.user_1), selectinload(Match.user_2))
        .join(u1, Match.user_1_id == u1.id)
        .join(u2, Match.user_2_id == u2.id)
        .where(
            (Match.user_1_id == user_id) | (Match.user_2_id == user_id),
            Match.status == MatchStatus.ACTIVE.value,
            or_(
                and_(Match.user_1_id == user_id, u2.deleted_at.is_(None)),
                and_(Match.user_2_id == user_id, u1.deleted_at.is_(None)),
            ),
        )
        .order_by(Match.created_at.desc())
    )
    return list(result.scalars().all())


async def get_match_by_id_for_user(
    session: AsyncSession, match_id: int, user_id: int
) -> Optional[Match]:
    """Load match by id for user; eager-loads user_1 and user_2 so partner_of() can be used without lazy load (avoids MissingGreenlet in async)."""
    result = await session.execute(
        select(Match)
        .options(selectinload(Match.user_1), selectinload(Match.user_2))
        .where(
            Match.id == match_id,
            (Match.user_1_id == user_id) | (Match.user_2_id == user_id),
            Match.status == MatchStatus.ACTIVE.value,
        )
    )
    return result.scalar_one_or_none()
