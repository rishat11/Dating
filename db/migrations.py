"""One-off migrations for existing databases (add new columns to users, messages)."""
import logging
from sqlalchemy import text

logger = logging.getLogger(__name__)

# Колонки, добавленные по IMPROVEMENTS: locale, геолокация; фильмы/сериалы/музыка отдельно
# datetime_type: SQLite = DATETIME, PostgreSQL = TIMESTAMP
USER_ADD_COLUMNS = [
    ("locale", "VARCHAR(5)", "DEFAULT 'ru'"),
    ("latitude", "FLOAT", "NULL"),
    ("longitude", "FLOAT", "NULL"),
    ("location_updated_at", None, "NULL"),  # type set per dialect
    ("movies", "VARCHAR(1024)", "NULL"),
    ("series", "VARCHAR(1024)", "NULL"),
    ("music", "VARCHAR(1024)", "NULL"),
]

# Колонки для разделения чатов: хранение текста и момент доставки получателю
MESSAGES_ADD_COLUMNS = [
    ("text", "TEXT", "NULL"),
    ("recipient_delivered_at", None, "NULL"),  # type set per dialect
]


def _get_existing_columns(conn, table_name: str, is_sqlite: bool):
    if is_sqlite:
        r = conn.execute(text(f"PRAGMA table_info({table_name})"))
        return {row[1] for row in r}
    r = conn.execute(text(
        "SELECT column_name FROM information_schema.columns WHERE table_name = :t"
    ), {"t": table_name})
    return {row[0] for row in r}


def _datetime_type(is_sqlite: bool) -> str:
    return "DATETIME" if is_sqlite else "TIMESTAMP"


def _add_user_columns_sync(conn):
    """Sync: add missing columns to users (SQLite/Postgres compatible)."""
    is_sqlite = conn.dialect.name == "sqlite"
    existing = _get_existing_columns(conn, "users", is_sqlite)
    dt = _datetime_type(is_sqlite)
    for col_name, col_type, suffix in USER_ADD_COLUMNS:
        if col_name in existing:
            continue
        ctype = col_type if col_type else dt
        sql = f"ALTER TABLE users ADD COLUMN {col_name} {ctype} {suffix}"
        conn.execute(text(sql))
        logger.info("Migration: added column users.%s", col_name)


def _add_messages_columns_sync(conn):
    """Add text and recipient_delivered_at to messages (chat separation)."""
    is_sqlite = conn.dialect.name == "sqlite"
    existing = _get_existing_columns(conn, "messages", is_sqlite)
    dt = _datetime_type(is_sqlite)
    for col_name, col_type, suffix in MESSAGES_ADD_COLUMNS:
        if col_name in existing:
            continue
        ctype = col_type if col_type else dt
        sql = f"ALTER TABLE messages ADD COLUMN {col_name} {ctype} {suffix}"
        conn.execute(text(sql))
        logger.info("Migration: added column messages.%s", col_name)


async def run_migrations(engine):
    """Run pending migrations (add new columns if missing)."""
    async with engine.begin() as conn:
        await conn.run_sync(_add_user_columns_sync)
        await conn.run_sync(_add_messages_columns_sync)
