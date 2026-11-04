"""Database engine for the shop API."""

import os
from collections.abc import Iterator
from pathlib import Path

from sqlmodel import Session, create_engine

DEMO_SHOP_ID = "demo-shop"
engine = None


def init_engine(database_url: str | None = None):
    """Open SQLite or the DATABASE_URL and remember it for requests."""
    global engine
    url = database_url or os.getenv("DATABASE_URL", "sqlite:///./.local/app.db")
    if url.startswith("sqlite") and ":memory:" not in url:
        Path(".local").mkdir(exist_ok=True)
        engine = create_engine(url, connect_args={"check_same_thread": False})
    else:
        engine = create_engine(url)
    return engine


def get_session() -> Iterator[Session]:
    """Yield one database session for a request."""
    if engine is None:
        raise RuntimeError("The database is not ready")
    with Session(engine) as session:
        yield session
