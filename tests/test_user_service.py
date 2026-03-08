"""Tests for services.user_service: get_or_create_user, restore after soft-delete."""
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from db.models import Base, User
from services.user_service import get_or_create_user, get_user_by_telegram_id


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
async def test_get_or_create_user_after_deletion_restores_and_reuses(session_factory):
    """
    When user had deleted account (soft-deleted) and presses /start again,
    get_or_create_user must restore the same row (set deleted_at=None) and return it
    instead of trying INSERT (which would raise UNIQUE constraint on telegram_id).
    """
    async with session_factory() as session:
        # Create user and "register" them
        user = User(
            telegram_id=221705938,
            username="rishatsadykov",
            first_name="Ришат",
            age_confirmed_18=True,
            rules_accepted=True,
            locale="ru",
            display_name="Rishat",
            age=25,
            profile_filled=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

        # Soft-delete (as in settings delete account)
        user.deleted_at = datetime.now(timezone.utc)
        await session.commit()

    # Simulate /start: get_or_create_user with same telegram_id must not INSERT, must restore
    async with session_factory() as session:
        restored = await get_or_create_user(
            session,
            221705938,
            username="rishatsadykov",
            first_name="Ришат",
        )

    assert restored.id == user_id
    assert restored.telegram_id == 221705938
    assert restored.deleted_at is None
    assert restored.username == "rishatsadykov"
    assert restored.first_name == "Ришат"
    # Old profile data preserved
    assert restored.locale == "ru"
    assert restored.display_name == "Rishat"
    assert restored.age == 25
    assert restored.profile_filled is True
    assert restored.age_confirmed_18 is True
    assert restored.rules_accepted is True


@pytest.mark.asyncio
async def test_get_or_create_user_new_user_creates(session_factory):
    """New telegram_id creates a new user."""
    async with session_factory() as session:
        user = await get_or_create_user(session, 999, username="new", first_name="NewUser")
    assert user.id is not None
    assert user.telegram_id == 999
    assert user.username == "new"
    assert user.first_name == "NewUser"
    assert user.deleted_at is None


@pytest.mark.asyncio
async def test_get_or_create_user_active_user_updates_name(session_factory):
    """Existing active user only gets username/first_name updated."""
    async with session_factory() as session:
        u = User(telegram_id=100, username="old", first_name="Old")
        session.add(u)
        await session.commit()
        await session.refresh(u)
        uid = u.id

    async with session_factory() as session:
        user = await get_or_create_user(session, 100, username="new_username", first_name="NewName")
    assert user.id == uid
    assert user.username == "new_username"
    assert user.first_name == "NewName"
    assert user.deleted_at is None
