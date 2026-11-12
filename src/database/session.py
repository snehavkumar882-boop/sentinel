"""Database connection, engine configuration, and session management."""

from contextlib import contextmanager
from typing import Generator, Optional
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config.settings import get_settings
from src.database.models import Base

_engine: Optional[Engine] = None
_session_factory: Optional[sessionmaker[Session]] = None


def get_engine(database_url: Optional[str] = None) -> Engine:
    """Obtain or initialize the SQLAlchemy Engine singleton."""
    global _engine
    if _engine is None or database_url is not None:
        url = database_url or get_settings().DATABASE_URL
        # SQLite specific optimizations
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        _engine = create_engine(url, echo=False, connect_args=connect_args)
    return _engine


def get_session_factory(engine: Optional[Engine] = None) -> sessionmaker[Session]:
    """Obtain or create the sessionmaker factory bound to the engine."""
    global _session_factory
    if _session_factory is None or engine is not None:
        eng = engine or get_engine()
        _session_factory = sessionmaker(bind=eng, autoflush=False, autocommit=False)
    return _session_factory


def init_db(engine: Optional[Engine] = None) -> None:
    """Create all registered database tables if they do not already exist."""
    eng = engine or get_engine()
    Base.metadata.create_all(bind=eng)


def drop_db(engine: Optional[Engine] = None) -> None:
    """Drop all tables (used primarily in test teardowns)."""
    eng = engine or get_engine()
    Base.metadata.drop_all(bind=eng)


@contextmanager
def get_db_session(engine: Optional[Engine] = None) -> Generator[Session, None, None]:
    """Context manager for acquiring and safely committing/rolling back a database session."""
    factory = get_session_factory(engine)
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
