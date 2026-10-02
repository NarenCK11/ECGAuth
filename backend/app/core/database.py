from collections.abc import Iterator
from datetime import datetime, timezone
from functools import lru_cache

from sqlalchemy import JSON, DateTime, create_engine
from sqlalchemy.dialects import mysql
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import TypeDecorator

from app.core.config import get_settings

# Case-insensitive collation for identifiers (usernames, emails), independent of server defaults.
CI_COLLATION = "utf8mb4_unicode_ci"

JSONType = JSON


class UTCDateTime(TypeDecorator):
    """MySQL DATETIME has no timezone: store naive UTC, always hand back tz-aware UTC values."""

    impl = DateTime
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "mysql":
            return dialect.type_descriptor(mysql.DATETIME(fsp=6))  # microseconds keep event ordering stable
        return dialect.type_descriptor(DateTime())

    def process_bind_param(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value: datetime | None, dialect):
        return value.replace(tzinfo=timezone.utc) if value is not None else None


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True, pool_recycle=1800)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = get_sessionmaker()()
    try:
        yield db
    finally:
        db.close()
