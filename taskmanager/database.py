"""Database initialization and management utilities.

This module provides functions for creating and managing the database,
including table creation and engine initialization.
"""

from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine

from taskmanager.config import get_settings


def get_engine() -> Engine:
    """Get the SQLModel engine for database operations.

    Returns:
        Engine: SQLModel engine configured for the application database.
    """
    settings = get_settings()
    database_url = settings.get_database_url()

    # Configure engine with optimizations for SQLite
    engine = create_engine(
        database_url,
        echo=False,  # Set to True for SQL debugging
        connect_args={"check_same_thread": False},  # Needed for SQLite
    )
    return engine


def init_db() -> None:
    """Initialize the database by creating all tables.

    This function should be called once during application setup
    to ensure all required tables exist.
    """
    engine = get_engine()
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    """Get a new database session.

    Returns:
        Session: A new SQLModel session for database operations.

    Note:
        Caller is responsible for closing the session.
    """
    engine = get_engine()
    return Session(engine)
