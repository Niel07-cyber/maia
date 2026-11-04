"""Shared test fixtures: a dedicated test database, and a session per test that is rolled
back afterwards so tests never affect each other."""

import hashlib
import math
import re
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager

import pytest
from sqlalchemy import Engine, create_engine, make_url, text
from sqlalchemy.orm import Session

from maia.config import get_settings
from maia.db import models  # noqa: F401  (registers the tables on Base.metadata)
from maia.db.base import Base
from maia.db.models import EMBEDDING_DIMENSIONS
from maia.db.seed import seed

TEST_DATABASE = "maia_test"


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    """Create the test database once per test run, with a fresh schema."""
    app_url = make_url(get_settings().database_url)

    admin = create_engine(app_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        exists = connection.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": TEST_DATABASE}
        )
        if not exists:
            connection.execute(text(f'CREATE DATABASE "{TEST_DATABASE}"'))
    admin.dispose()

    test_engine = create_engine(app_url.set(database=TEST_DATABASE))
    with test_engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    """Run each test inside a transaction that is rolled back at the end."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def depot(db_session: Session) -> Session:
    """A session with the demo depot loaded: two vehicles, their components, the parts store."""
    seed(db_session)
    db_session.flush()
    return db_session


class FakeEmbedder:
    """Offline stand-in for a real embedding model: each word is hashed to a position in the
    vector, so texts that share words end up close together. Deterministic and free."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    @staticmethod
    def _vector(text: str) -> list[float]:
        vector = [0.0] * EMBEDDING_DIMENSIONS
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            index = int(hashlib.md5(word.encode()).hexdigest(), 16) % EMBEDDING_DIMENSIONS
            vector[index] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]


@pytest.fixture
def embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture
def transaction(depot: Session) -> Callable[[], AbstractContextManager[Session]]:
    """Stand-in for maia.db.session.transaction: each tool call runs in a savepoint inside
    the test's transaction, so a failed call rolls back only its own changes."""

    @contextmanager
    def savepoint() -> Iterator[Session]:
        with depot.begin_nested():
            yield depot

    return savepoint
