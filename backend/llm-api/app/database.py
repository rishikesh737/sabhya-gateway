import os
import time
import structlog
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.models import Base

log = structlog.get_logger()

# Default to PostgreSQL, fallback to SQLite for local dev
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://vectal:***REMOVED***@localhost:5432/vectal_db"
)

# SQLite-specific connection args
connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}

def wait_for_db(max_retries=15, delay=1):
    """Wait for database to be ready (critical for container startup race condition)."""
    for attempt in range(max_retries):
        try:
            temp_engine = create_engine(DATABASE_URL, connect_args=connect_args)
            with temp_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            log.info("database_connected", url=DATABASE_URL[:30] + "...")
            return temp_engine
        except Exception as e:
            log.warning("database_not_ready", attempt=attempt+1, error=str(e)[:50])
            time.sleep(delay)
    raise RuntimeError(f"Database not available after {max_retries} attempts")

engine = wait_for_db()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Create all tables defined in models.py"""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Dependency injection for FastAPI routes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
