"""
Database engine/session setup (SQLite for the prototype; swap
DATABASE_URL in .env to point at Postgres later with no code changes).
"""

from __future__ import annotations

import logging
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from common.config import DATABASE_URL
from personalization_layer.models import Base

logger = logging.getLogger(__name__)

_engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
)

_SessionLocal = sessionmaker(
    bind=_engine,
    expire_on_commit=False,
)


def init_db() -> None:
    """Create all tables if they don't already exist."""

    Base.metadata.create_all(_engine)

    logger.info(
        "Database initialised at %s",
        DATABASE_URL,
    )


@contextmanager
def get_session():
    """Context-managed session: `with get_session() as session: ...`"""

    session: Session = _SessionLocal()

    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()