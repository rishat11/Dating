"""One-off migrations for existing databases (add new columns to users)."""
import logging
from sqlalchemy import text

logger = logging.getLogger(__name__)

# Колонки, добавленные по IMPROVEMENTS: locale, геолокация; фильмы/сериалы/музыка отдельно
USER_ADD_COLUMNS = [
    ("locale", "VARCHAR(5)", "DEFAULT 'ru'"),
    ("latitude", "FLOAT", "NULL"),
    ("longitude", "FLOAT", "NULL"),
    ("location_updated_at", "DATETIME", "NULL"),
    ("movies", "VARCHAR(1024)", "NULL"),
    ("series", "VARCHAR(1024)", "NULL"),
    ("music", "VARCHAR(1024)", "NULL"),
]


def _add_user_columns_sync(conn):
    """Sync: add missing columns to users (SQLite/Postgres compatible)."""
    is_sqlite = conn.dialect.name == "sqlite"
    if is_sqlite:
        r = conn.execute(text("PRAGMA table_info(users)"))
        existing = {row[1] for row in r}
    else:
        # PostgreSQL
        r = conn.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'users'"
        ))
        existing = {row[0] for row in r}

    for col_name, col_type, suffix in USER_ADD_COLUMNS:
        if col_name in existing:
            continue
        sql = f"ALTER TABLE users ADD COLUMN {col_name} {col_type} {suffix}"
        conn.execute(text(sql))
        logger.info("Migration: added column users.%s", col_name)


async def run_migrations(engine):
    """Run pending migrations (add new user columns if missing)."""
    async with engine.begin() as conn:
        await conn.run_sync(_add_user_columns_sync)
