from collections.abc import Generator
import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from database.models import Base
from .config import settings
from .exceptions import DatabaseUnavailableError


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True,
)


logger = logging.getLogger(__name__)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()

    try:
        yield db
    except Exception as exc:
        db.rollback()
        logger.error(
            "Database session failed",
            extra={"error_type": type(exc).__name__},
        )
        raise
    finally:
        db.close()


def check_database_connection() -> None:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        logger.error(
            "Database connectivity check failed",
            extra={"error_type": type(exc).__name__},
        )
        raise DatabaseUnavailableError() from exc
