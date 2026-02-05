"""Database initialization and management utilities.

This module provides functions for creating and managing the database,
including table creation and engine initialization.
"""

import os
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine

from taskmanager.config import create_settings_for_profile
# Import models to register them with SQLModel.metadata
from taskmanager.models import Task, TaskStatus, Attachment  # noqa: F401


def get_engine(profile: str = "default") -> Engine:
    """Get the SQLModel engine for database operations.

    Args:
        profile: Database profile to use (default, dev, test)

    Returns:
        Engine: SQLModel engine configured for the application database.
    """
    settings = create_settings_for_profile(profile)
    database_url = settings.get_database_url()

    # Configure engine with optimizations for SQLite
    engine = create_engine(
        database_url,
        echo=False,  # Set to True for SQL debugging
        connect_args={"check_same_thread": False},  # Needed for SQLite
    )
    return engine


def init_db(profile: str = "default") -> None:
    """Initialize the database by creating base tables and running Alembic migrations.

    Args:
        profile: Database profile to use (default, dev, test)

    This function:
    1. Creates base tables using SQLModel.metadata.create_all() (task, task_status, etc.)
    2. Runs all pending Alembic migrations (for schema enhancements like attachment table)
    
    Alembic migrations are applied AFTER base tables exist, allowing migrations to
    safely reference existing tables (e.g., adding the attachment table with FK to task).
    """
    engine = get_engine(profile)
    
    # Step 1: Create base tables using SQLModel (task, task_status, alembic_version)
    # This ensures the task table and core schema exist
    # We must establish a connection to trigger database file creation
    with engine.begin() as connection:
        SQLModel.metadata.create_all(connection)
    
    # Step 2: Run Alembic migrations for schema enhancements
    # These are applied AFTER base tables exist
    migrations_dir = os.path.join(os.path.dirname(__file__), '..', 'migrations')
    alembic_ini = os.path.join(os.path.dirname(__file__), '..', 'alembic.ini')
    
    if os.path.exists(alembic_ini):
        # Configure Alembic
        alembic_cfg = AlembicConfig(alembic_ini)
        alembic_cfg.set_main_option('script_location', migrations_dir)
        
        # Get the database URL for this profile
        settings = create_settings_for_profile(profile)
        alembic_cfg.set_main_option('sqlalchemy.url', settings.get_database_url())
        
        # Run migrations to the latest version (head)
        try:
            command.upgrade(alembic_cfg, 'head')
        except Exception as e:
            # Log warning but don't fail - base tables already created
            print(f"Warning: Alembic migration issue: {e}")


def get_session(profile: str = "default") -> Session:
    """Get a new database session.

    Args:
        profile: Database profile to use (default, dev, test)

    Returns:
        Session: A new SQLModel session for database operations.

    Note:
        Caller is responsible for closing the session.
    """
    engine = get_engine(profile)
    return Session(engine)
