"""Database engine and session factory setup."""

from __future__ import annotations

import logging

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from ..config import Settings


def create_db_engine(settings: Settings, logger: logging.Logger) -> Engine:
    """Create SQLAlchemy engine for MySQL using environment-based settings."""
    logger.info("Initializing database engine")

    # Optional SSL configuration example (enable when required by your MySQL host):
    # connect_args = {
    #     "ssl": {
    #         "ca": "/path/to/ca.pem",
    #         "cert": "/path/to/client-cert.pem",
    #         "key": "/path/to/client-key.pem",
    #     }
    # }
    connect_args: dict = {}

    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_recycle=3600,
        connect_args=connect_args,
        future=True,
    )


def get_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return configured SQLAlchemy session factory."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def run_parameterized_healthcheck(session: Session) -> int:
    """Example of safe parameterized raw SQL query."""
    result = session.execute(text("SELECT :value AS value"), {"value": 1})
    row = result.first()
    return int(row.value) if row is not None else 0
