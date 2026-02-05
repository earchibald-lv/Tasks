"""
Point-in-time database backups with automatic rotation.

This module provides backup functionality to protect against data loss during
migrations or schema changes. Each backup is timestamped and stored per-profile
with automatic cleanup to maintain a maximum of 10 backups per profile.
"""

import logging
import shutil
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def get_backup_dir(profile: str) -> Path:
    """
    Get the backup directory for a profile, creating it if needed.

    Args:
        profile: Profile name (default, dev, custom, etc.)

    Returns:
        Path to the backup directory for this profile
    """
    backup_base = Path.home() / ".config" / "taskmanager" / "backups"
    backup_dir = backup_base / profile

    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.warning(f"Failed to create backup directory {backup_dir}: {e}")

    return backup_dir


def get_database_path(profile: str) -> Path | None:
    """
    Get the database path for a profile.

    Args:
        profile: Profile name

    Returns:
        Path to database file, or None if not found
    """
    config_dir = Path.home() / ".config" / "taskmanager"

    # Map profile names to database filenames
    if profile == "default":
        db_path = config_dir / "tasks.db"
    elif profile == "test":
        # Test profile uses in-memory database
        return None
    else:
        # Custom profiles
        db_path = config_dir / f"tasks-{profile}.db"

    if db_path.exists():
        return db_path

    return None


def create_backup(profile: str) -> Path | None:
    """
    Create a timestamped backup of the profile database.

    Args:
        profile: Profile name to backup

    Returns:
        Path to the created backup file, or None if backup was skipped
    """
    # Skip in-memory databases (test profile)
    if profile == "test":
        return None

    # Get database path
    db_path = get_database_path(profile)
    if db_path is None:
        logger.debug(
            f"Database for profile '{profile}' not found, skipping backup"
        )
        return None

    # Get backup directory
    backup_dir = get_backup_dir(profile)

    # Create timestamped backup filename
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    db_name = db_path.name
    backup_filename = f"{timestamp}_{db_name}"
    backup_path = backup_dir / backup_filename

    try:
        shutil.copy2(db_path, backup_path)
        logger.info(f"Backup created: {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"Failed to create backup of {db_path}: {e}")
        return None


def list_backups(profile: str) -> list[Path]:
    """
    List all backups for a profile, newest first.

    Args:
        profile: Profile name

    Returns:
        List of backup paths, sorted newest first
    """
    backup_dir = get_backup_dir(profile)

    if not backup_dir.exists():
        return []

    backups = list(backup_dir.glob("*.db"))
    # Sort by modification time, newest first
    backups.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    return backups


def cleanup_old_backups(profile: str, max_backups: int = 10) -> None:
    """
    Remove old backups when limit is exceeded.

    Keeps the N most recent backups per profile, removing oldest
    when the count exceeds max_backups.

    Args:
        profile: Profile name
        max_backups: Maximum number of backups to keep per profile (default: 10)
    """
    backups = list_backups(profile)

    if len(backups) <= max_backups:
        return

    # Remove oldest backups
    backups_to_remove = backups[max_backups:]

    for backup_path in backups_to_remove:
        try:
            backup_path.unlink()
            logger.info(f"Cleaned up old backup: {backup_path}")
        except Exception as e:
            logger.warning(f"Failed to delete backup {backup_path}: {e}")


def backup_before_migration(
    profile: str, operation: str = "migration", max_backups: int = 10
) -> bool:
    """
    Create a backup before performing a migration or schema change.

    This is the primary entry point for backup operations before critical
    operations. It creates a backup and cleans up old backups.

    Args:
        profile: Profile name to backup
        operation: Description of the operation (for logging)
        max_backups: Maximum backups to keep per profile

    Returns:
        True if backup successful or skipped (in-memory), False if backup failed
    """
    logger.debug(
        f"Creating backup before {operation} on profile '{profile}'"
    )

    # Skip in-memory databases
    if profile == "test":
        logger.debug(
            f"Profile '{profile}' uses in-memory database, skipping backup"
        )
        return True

    # Create backup
    backup_path = create_backup(profile)
    if backup_path is None:
        # Could be skipped (DB doesn't exist yet) or failed
        # If failed, an error was already logged
        return False if get_database_path(profile) else True

    # Clean up old backups
    cleanup_old_backups(profile, max_backups)

    logger.info(f"Backup complete before {operation}: {backup_path}")
    return True

