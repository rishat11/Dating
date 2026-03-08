"""Async database session and initialization."""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import get_config
from db.models import Base
from db.migrations import run_migrations

_config = get_config()
engine = create_async_engine(
    _config.database_url,
    echo=False,
)
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await run_migrations(engine)


async def get_session() -> AsyncSession:
    async with async_session_factory() as session:
        yield session
