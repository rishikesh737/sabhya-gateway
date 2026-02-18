"""
Sabhya AI - Database Connection Manager

Provides SQLAlchemy engine, session factory, and database utilities.
Uses lazy initialization to avoid startup failures when DB is unavailable.
"""

import os
import time
from typing import Generator

import structlog
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base

log = structlog.get_logger()

# Database URL from environment
# Note: psycopg (v3) requires "postgresql+psycopg://" scheme
_raw_url = os.getenv(
    "DATABASE_URL", "postgresql://sabhya:***REMOVED***@localhost:5432/sabhya_db"
)

# Convert to psycopg3 driver URL if using postgres
if _raw_url.startswith("postgresql://"):
    DATABASE_URL = _raw_url.replace("postgresql://", "postgresql+psycopg://", 1)
elif _raw_url.startswith("postgres://"):
    DATABASE_URL = _raw_url.replace("postgres://", "postgresql+psycopg://", 1)
else:
    DATABASE_URL = _raw_url

# SQLite-specific connection args
connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}

# Lazy initialization - engine created on first use
_engine = None
_SessionLocal = None


def get_engine():
    """
    Get or create the database engine (lazy initialization).
    This avoids startup failures when the database is unavailable.
    """
    global _engine
    if _engine is None:
        _engine = create_engine(
            DATABASE_URL,
            connect_args=connect_args,
            pool_pre_ping=True,  # Check connection health before use
            pool_recycle=300,  # Recycle connections after 5 minutes
        )
        log.info("database_engine_created", url=DATABASE_URL[:30] + "...")
    return _engine


def wait_for_db(max_retries: int = 15, delay: int = 1) -> bool:
    """
    Wait for database to be ready.
    Returns True if connected, False if timeout.
    """
    for attempt in range(max_retries):
        try:
            engine = get_engine()
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            log.info("database_connected", attempt=attempt + 1)
            return True
        except Exception as e:
            log.warning("database_not_ready", attempt=attempt + 1, error=str(e)[:50])
            time.sleep(delay)
    return False


def get_session_factory():
    """Get or create the session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=get_engine()
        )
    return _SessionLocal


def init_db():
    """Create all tables defined in models.py."""
    try:
        engine = get_engine()
        Base.metadata.create_all(bind=engine)
        log.info("database_tables_created")
    except Exception as e:
        log.error("database_init_failed", error=str(e))
        raise


def get_db() -> Generator[Session, None, None]:
    """
    Dependency injection for FastAPI routes.

    Usage:
        @app.get("/endpoint")
        async def endpoint(db: Session = Depends(get_db)):
            ...
    """
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_health() -> dict:
    """
    Check database health for health endpoints.

    Returns:
        {'healthy': bool, 'message': str}
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"healthy": True, "message": "Connected"}
    except Exception as e:
        return {"healthy": False, "message": str(e)[:100]}


# For backward compatibility - don't auto-connect on import
SessionLocal = None  # Will be set lazily


def _init_on_first_use():
    """Initialize session factory on first use (backward compat helper)."""
    global SessionLocal
    if SessionLocal is None:
        SessionLocal = get_session_factory()
    return SessionLocal
