"""Tests for services.match_service: get_user_matches, get_match_by_id_for_user, partner_of after session close (DetachedInstanceError/MissingGreenlet fix)."""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from db.models import Base, User, Match, MatchStatus, DestinyIndex
from services.match_service import get_user_matches, get_match_by_id_for_user


@pytest.fixture
async def session_factory():
    """In-memory SQLite engine and session factory for tests."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    yield factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_get_user_matches_partner_of_after_session_closed(session_factory):
    """
    Reproduces chats_list flow: get_user_matches() inside session, then use
    match.partner_of(user_id) and partner.display_name outside the session.
    Without eager-loading user_1/user_2 this raises DetachedInstanceError.
    """
    user_1_id: int
    user_2_id: int
    current_user_id: int

    async with session_factory() as session:
        u1 = User(
            telegram_id=100,
            username="alice",
            first_name="Alice",
            display_name="Alice",
            age=25,
            age_confirmed_18=True,
            rules_accepted=True,
        )
        u2 = User(
            telegram_id=200,
            username="bob",
            first_name="Bob",
            display_name="Bob",
            age=30,
            age_confirmed_18=True,
            rules_accepted=True,
        )
        session.add_all([u1, u2])
        await session.flush()
        user_1_id = u1.id
        user_2_id = u2.id
        match = Match(
            user_1_id=user_1_id,
            user_2_id=user_2_id,
            status=MatchStatus.ACTIVE.value,
        )
        session.add(match)
        await session.flush()
        session.add(DestinyIndex(match_id=match.id))
        await session.commit()
        current_user_id = user_1_id  # current user is u1, partner is u2

    # Simulate chats_list: load matches inside session, then exit session
    matches = []
    async with session_factory() as session:
        matches = await get_user_matches(session, current_user_id)
        assert len(matches) == 1

    # Outside session: use partner_of() and partner attributes (would raise DetachedInstanceError without selectinload)
    for m in matches:
        partner = m.partner_of(current_user_id)
        assert partner is not None
        assert partner.display_name == "Bob"
        assert partner.first_name == "Bob"
        assert partner.age == 30


@pytest.mark.asyncio
async def test_get_match_by_id_for_user_partner_of_after_session_closed(session_factory):
    """
    Reproduces chat handler flow: get_match_by_id_for_user() inside session, then use
    match.partner_of(user_id) and partner attributes outside the session.
    Without eager-loading user_1/user_2 this raises MissingGreenlet (async) or DetachedInstanceError (sync).
    """
    match_id: int
    current_user_id: int

    async with session_factory() as session:
        u1 = User(
            telegram_id=300,
            username="u3",
            first_name="User3",
            display_name="User3",
            age=22,
            age_confirmed_18=True,
            rules_accepted=True,
        )
        u2 = User(
            telegram_id=400,
            username="u4",
            first_name="User4",
            display_name="User4",
            age=28,
            age_confirmed_18=True,
            rules_accepted=True,
        )
        session.add_all([u1, u2])
        await session.flush()
        match = Match(
            user_1_id=u1.id,
            user_2_id=u2.id,
            status=MatchStatus.ACTIVE.value,
        )
        session.add(match)
        await session.flush()
        session.add(DestinyIndex(match_id=match.id))
        await session.commit()
        match_id = match.id
        current_user_id = u1.id

    # Simulate chat handler: load match inside session, then exit session
    match = None
    async with session_factory() as session:
        match = await get_match_by_id_for_user(session, match_id, current_user_id)
        assert match is not None

    # Outside session: partner_of() and partner attributes must work (no lazy load → no MissingGreenlet)
    partner = match.partner_of(current_user_id)
    assert partner is not None
    assert partner.display_name == "User4"
    assert partner.first_name == "User4"
    assert partner.age == 28
    assert partner.telegram_id == 400
