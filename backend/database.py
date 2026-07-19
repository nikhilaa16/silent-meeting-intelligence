"""
Database setup using SQLAlchemy.

Supports two modes:
  - SQLite  (default): Zero config, single file, perfect for local dev/demo.
  - PostgreSQL (prod):  Set DATABASE_URL in .env for production deployments.

Switching databases requires NO code changes — just set DATABASE_URL in .env.
SQLAlchemy handles all schema mapping abstractly.

Example .env for PostgreSQL:
  DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/meetings_db
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from pathlib import Path

from .config import settings


class Base(DeclarativeBase):
    pass


def _build_engine():
    """
    Build the SQLAlchemy engine based on configuration.

    Priority:
      1. If DATABASE_URL is set in .env → use it (PostgreSQL or any other DB)
      2. Otherwise → fall back to SQLite (local file-based database)

    This single function is the ONLY place in the codebase that knows
    which database backend is being used. Everything else is abstracted.
    """
    if settings.DATABASE_URL:
        # ── PostgreSQL (or any other production DB) ──────────────────────
        print(f"[DB] Connecting to PostgreSQL: {settings.DATABASE_URL[:40]}...")
        return create_engine(
            settings.DATABASE_URL,
            pool_size=10,           # Max connections in pool
            max_overflow=20,        # Extra connections when pool is full
            pool_pre_ping=True,     # Verify connections before use (handles dropped connections)
            echo=False,             # Set True to log all SQL queries (debug only)
        )
    else:
        # ── SQLite (local development / demo) ────────────────────────────
        db_path = Path(settings.DB_PATH)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"[DB] Using SQLite: {db_path.absolute()}")
        return create_engine(
            f"sqlite:///{settings.DB_PATH}",
            connect_args={"check_same_thread": False},  # Required for SQLite + FastAPI threads
        )


engine = _build_engine()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Create all tables on startup if they don't exist."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency — yields a DB session per request, closes after."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
