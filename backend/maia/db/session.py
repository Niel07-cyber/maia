"""Engine and session factory. One engine per process, one session per request."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from maia.config import get_settings


@lru_cache
def get_engine() -> Engine:
    """Create the connection pool once. pool_pre_ping drops dead connections before use."""
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: open a session for one request and always close it."""
    with get_sessionmaker()() as session:
        yield session
