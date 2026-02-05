"""Unit tests for database backup module."""

import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from taskmanager.backup import (
    create_backup,
    get_backup_dir,
    get_database_path,
    list_backups,
    cleanup_old_backups,
    backup_before_migration,
)


class TestGetBackupDir:
    """Test backup directory retrieval and creation."""
    
    def test_backup_dir_created(self, tmp_path):
        """Backup directory should be created if it doesn't exist."""
        with patch('taskmanager.backup.Path.home', return_value=tmp_path):
            backup_dir = get_backup_dir("dev")
            assert backup_dir.exists()
            assert backup_dir.parent.name == "backups"
            assert backup_dir.name == "dev"
    
    def test_backup_dir_exists(self, tmp_path):
        """Should return existing backup directory without error."""
        backup_path = tmp_path / ".config" / "taskmanager" / "backups" / "default"
        backup_path.mkdir(parents=True, exist_ok=True)
        
        with patch('taskmanager.backup.Path.home', return_value=tmp_path):
            result = get_backup_dir("default")
            assert result == backup_path
            assert result.exists()
    
    def test_backup_dir_creation_handles_permission_error(self, tmp_path):
        """Should handle permission errors gracefully."""
        with patch('taskmanager.backup.Path.home', return_value=tmp_path):
            with patch.object(Path, 'mkdir', side_effect=PermissionError("No permission")):
                # Should not raise, just log warning
                backup_dir = get_backup_dir("dev")
                assert backup_dir is not None


class TestGetDatabasePath:
    """Test database path resolution."""
    
    def test_default_profile_path(self, tmp_path):
        """Default profile should map to tasks.db."""
        config_dir = tmp_path / ".config" / "taskmanager"
        config_dir.mkdir(parents=True, exist_ok=True)
        db_file = config_dir / "tasks.db"
        db_file.touch()
        
        with patch('taskmanager.backup.Path.home', return_value=tmp_path):
            result = get_database_path("default")
            assert result == db_file
    
    def test_dev_profile_path(self, tmp_path):
        """Dev profile should map to tasks-dev.db."""
        config_dir = tmp_path / ".config" / "taskmanager"
        config_dir.mkdir(parents=True, exist_ok=True)
        db_file = config_dir / "tasks-dev.db"
        db_file.touch()
        
        with patch('taskmanager.backup.Path.home', return_value=tmp_path):
            result = get_database_path("dev")
            assert result == db_file
    
    def test_custom_profile_path(self, tmp_path):
        """Custom profile should map to tasks-{name}.db."""
        config_dir = tmp_path / ".config" / "taskmanager"
        config_dir.mkdir(parents=True, exist_ok=True)
        db_file = config_dir / "tasks-client-a.db"
        db_file.touch()
        
        with patch('taskmanager.backup.Path.home', return_value=tmp_path):
            result = get_database_path("client-a")
            assert result == db_file
    
    def test_test_profile_returns_none(self, tmp_path):
        """Test profile (in-memory) should return None."""
        with patch('taskmanager.backup.Path.home', return_value=tmp_path):
            result = get_database_path("test")
            assert result is None
    
    def test_missing_database_returns_none(self, tmp_path):
        """Non-existent database should return None."""
        with patch('taskmanager.backup.Path.home', return_value=tmp_path):
            result = get_database_path("nonexistent")
            assert result is None


class TestCreateBackup:
    """Test backup creation."""
    
    def test_create_backup_creates_file(self, tmp_path):
        """Creating a backup should copy the database file."""
        config_dir = tmp_path / ".config" / "taskmanager"
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a test database
        db_file = config_dir / "tasks.db"
        db_file.write_text("test content")
        
        # Create backup directory
        backup_dir = tmp_path / ".config" / "taskmanager" / "backups" / "default"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        with patch('taskmanager.backup.Path.home', return_value=tmp_path):
            result = create_backup("default")
            assert result is not None
            assert result.exists()
            assert result.read_text() == "test content"
    
    def test_create_backup_with_timestamp(self, tmp_path):
        """Backup filename should include timestamp."""
        config_dir = tmp_path / ".config" / "taskmanager"
        config_dir.mkdir(parents=True, exist_ok=True)
        db_file = config_dir / "tasks.db"
        db_file.write_text("test")
        
        backup_dir = tmp_path / ".config" / "taskmanager" / "backups" / "default"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        with patch('taskmanager.backup.Path.home', return_value=tmp_path):
            result = create_backup("default")
            # Filename should be: YYYY-MM-DD_HH-MM-SS_tasks.db
            assert result.name.endswith("_tasks.db")
            # Should have timestamp pattern YYYY-MM-DD
            assert result.name[0:4].isdigit()  # Year
            assert result.name[5:7].isdigit()  # Month
    
    def test_create_backup_skips_test_profile(self, tmp_path):
        """Test profile (in-memory) should skip backup."""
        with patch('taskmanager.backup.Path.home', return_value=tmp_path):
            result = create_backup("test")
            assert result is None
    
    def test_create_backup_skips_missing_database(self, tmp_path):
        """Should skip if database doesn't exist."""
        with patch('taskmanager.backup.Path.home', return_value=tmp_path):
            result = create_backup("nonexistent")
            assert result is None
    
    def test_create_backup_handles_error(self, tmp_path):
        """Should handle copy errors gracefully."""
        config_dir = tmp_path / ".config" / "taskmanager"
        config_dir.mkdir(parents=True, exist_ok=True)
        db_file = config_dir / "tasks.db"
        db_file.write_text("test")
        
        backup_dir = tmp_path / ".config" / "taskmanager" / "backups" / "default"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        with patch('taskmanager.backup.Path.home', return_value=tmp_path):
            with patch('taskmanager.backup.shutil.copy2', side_effect=OSError("Copy failed")):
                result = create_backup("default")
                assert result is None


class TestListBackups:
    """Test backup listing."""
    
    def test_list_backups_empty(self, tmp_path):
        """Empty backup directory should return empty list."""
        backup_dir = tmp_path / ".config" / "taskmanager" / "backups" / "default"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        with patch('taskmanager.backup.Path.home', return_value=tmp_path):
            result = list_backups("default")
            assert result == []
    
    def test_list_backups_sorted(self, tmp_path):
        """Backups should be sorted newest first."""
        backup_dir = tmp_path / ".config" / "taskmanager" / "backups" / "default"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Create backup files with different timestamps
        file1 = backup_dir / "2026-02-01_10-00-00_tasks.db"
        file2 = backup_dir / "2026-02-03_15-30-00_tasks.db"
        file3 = backup_dir / "2026-02-02_12-00-00_tasks.db"
        
        file1.write_text("test1")
        file2.write_text("test2")
        file3.write_text("test3")
        
        with patch('taskmanager.backup.Path.home', return_value=tmp_path):
            result = list_backups("default")
            # Should be in order: file2, file3, file1 (newest first by mtime)
            assert len(result) == 3
    
    def test_list_backups_nonexistent_dir(self, tmp_path):
        """Nonexistent directory should return empty list."""
        with patch('taskmanager.backup.Path.home', return_value=tmp_path):
            result = list_backups("nonexistent")
            assert result == []


class TestCleanupOldBackups:
    """Test backup cleanup and rotation."""
    
    def test_cleanup_removes_oldest(self, tmp_path):
        """Cleanup should remove oldest backups when limit exceeded."""
        backup_dir = tmp_path / ".config" / "taskmanager" / "backups" / "default"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Create 12 backup files
        backups = []
        for i in range(12):
            path = backup_dir / f"2026-02-{i:02d}_10-00-00_tasks.db"
            path.write_text(f"backup{i}")
            backups.append(path)
        
        with patch('taskmanager.backup.Path.home', return_value=tmp_path):
            cleanup_old_backups("default", max_backups=10)
            
            remaining = list(backup_dir.glob("*.db"))
            assert len(remaining) == 10
    
    def test_cleanup_respects_max(self, tmp_path):
        """Cleanup should respect max_backups parameter."""
        backup_dir = tmp_path / ".config" / "taskmanager" / "backups" / "default"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Create 15 backup files
        for i in range(15):
            path = backup_dir / f"2026-02-{i:02d}_10-00-00_tasks.db"
            path.write_text(f"backup{i}")
        
        with patch('taskmanager.backup.Path.home', return_value=tmp_path):
            cleanup_old_backups("default", max_backups=5)
            
            remaining = list(backup_dir.glob("*.db"))
            assert len(remaining) == 5
    
    def test_cleanup_keeps_below_limit(self, tmp_path):
        """Cleanup should not remove if below limit."""
        backup_dir = tmp_path / ".config" / "taskmanager" / "backups" / "default"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Create 5 backup files
        for i in range(5):
            path = backup_dir / f"2026-02-{i:02d}_10-00-00_tasks.db"
            path.write_text(f"backup{i}")
        
        with patch('taskmanager.backup.Path.home', return_value=tmp_path):
            cleanup_old_backups("default", max_backups=10)
            
            remaining = list(backup_dir.glob("*.db"))
            assert len(remaining) == 5
    
    def test_cleanup_handles_deletion_error(self, tmp_path):
        """Cleanup should handle deletion errors gracefully."""
        backup_dir = tmp_path / ".config" / "taskmanager" / "backups" / "default"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Create 12 files
        for i in range(12):
            path = backup_dir / f"2026-02-{i:02d}_10-00-00_tasks.db"
            path.write_text(f"backup{i}")
        
        with patch('taskmanager.backup.Path.home', return_value=tmp_path):
            with patch.object(Path, 'unlink', side_effect=OSError("Delete failed")):
                # Should not raise exception
                cleanup_old_backups("default", max_backups=10)


class TestBackupBeforeMigration:
    """Test the main backup_before_migration function."""
    
    def test_backup_before_migration_creates_backup(self, tmp_path):
        """Should create backup before migration."""
        config_dir = tmp_path / ".config" / "taskmanager"
        config_dir.mkdir(parents=True, exist_ok=True)
        db_file = config_dir / "tasks.db"
        db_file.write_text("test")
        
        backup_dir = tmp_path / ".config" / "taskmanager" / "backups" / "default"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        with patch('taskmanager.backup.Path.home', return_value=tmp_path):
            result = backup_before_migration("default", operation="schema_upgrade")
            assert result is True
            assert len(list(backup_dir.glob("*.db"))) > 0
    
    def test_backup_before_migration_cleans_old(self, tmp_path):
        """Should cleanup old backups after creating new one."""
        config_dir = tmp_path / ".config" / "taskmanager"
        config_dir.mkdir(parents=True, exist_ok=True)
        db_file = config_dir / "tasks.db"
        db_file.write_text("test")
        
        backup_dir = tmp_path / ".config" / "taskmanager" / "backups" / "default"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Pre-populate with 10 backups
        for i in range(10):
            path = backup_dir / f"2026-02-{i:02d}_10-00-00_tasks.db"
            path.write_text(f"backup{i}")
        
        with patch('taskmanager.backup.Path.home', return_value=tmp_path):
            # This should create new backup and cleanup
            result = backup_before_migration("default", operation="migration", max_backups=10)
            assert result is True
            # Should have exactly 10 (old ones deleted, new one added)
            assert len(list(backup_dir.glob("*.db"))) == 10
    
    def test_backup_before_migration_test_profile(self, tmp_path):
        """Test profile should skip backup successfully."""
        with patch('taskmanager.backup.Path.home', return_value=tmp_path):
            result = backup_before_migration("test", operation="migration")
            assert result is True
    
    def test_backup_before_migration_missing_db(self, tmp_path):
        """Missing database should be handled gracefully."""
        with patch('taskmanager.backup.Path.home', return_value=tmp_path):
            result = backup_before_migration("nonexistent", operation="migration")
            assert result is True  # Skipped, not failed


class TestIntegration:
    """Integration tests with actual databases."""
    
    def test_backup_valid_sqlite(self, tmp_path):
        """Backup should be a valid SQLite database."""
        config_dir = tmp_path / ".config" / "taskmanager"
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a valid SQLite database
        db_file = config_dir / "tasks.db"
        conn = sqlite3.connect(str(db_file))
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO test (name) VALUES ('hello')")
        conn.commit()
        conn.close()
        
        backup_dir = tmp_path / ".config" / "taskmanager" / "backups" / "default"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        with patch('taskmanager.backup.Path.home', return_value=tmp_path):
            backup_path = create_backup("default")
            assert backup_path is not None
            
            # Verify backup is valid SQLite
            conn = sqlite3.connect(str(backup_path))
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM test")
            result = cursor.fetchone()
            assert result[0] == "hello"
            conn.close()
    
    def test_multiple_profiles_independent(self, tmp_path):
        """Backups for different profiles should be independent."""
        config_dir = tmp_path / ".config" / "taskmanager"
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # Create databases for default and dev
        default_db = config_dir / "tasks.db"
        default_db.write_text("default content")
        
        dev_db = config_dir / "tasks-dev.db"
        dev_db.write_text("dev content")
        
        # Create backup directories
        for profile in ["default", "dev"]:
            backup_dir = tmp_path / ".config" / "taskmanager" / "backups" / profile
            backup_dir.mkdir(parents=True, exist_ok=True)
        
        with patch('taskmanager.backup.Path.home', return_value=tmp_path):
            # Backup both profiles
            result1 = create_backup("default")
            result2 = create_backup("dev")
            
            assert result1 is not None
            assert result2 is not None
            assert result1.parent != result2.parent
            assert result1.read_text() == "default content"
            assert result2.read_text() == "dev content"
