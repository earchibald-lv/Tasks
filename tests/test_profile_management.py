"""Unit tests for profile management functionality.

Tests for list_profiles, audit_profile, and delete_profile service methods,
as well as their CLI handlers.
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from taskmanager.config import Settings
from taskmanager.service import TaskService


class TestListProfiles:
    """Tests for list_profiles() service method."""

    def test_list_profiles_with_multiple_databases(self):
        """Test listing multiple profile databases."""
        # Setup mock repository
        mock_repo = Mock()

        # Create temporary database files
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)

            # Create mock database files
            (config_dir / "tasks.db").touch()
            (config_dir / "tasks-dev.db").touch()
            (config_dir / "tasks-personal.db").touch()

            # Create mock config
            mock_config = Mock(spec=Settings)
            mock_config.get_config_dir.return_value = config_dir
            mock_config.profiles = {}

            # Create service with mock config
            service = TaskService(mock_repo, config=mock_config)

            # Mock task counting
            with patch.object(service, "_count_tasks_in_profile", return_value=5):
                profiles = service.list_profiles()

            # Assert
            assert len(profiles) == 3
            profile_names = {p.name for p in profiles}
            assert "default" in profile_names
            assert "dev" in profile_names
            assert "personal" in profile_names
            assert all(p.exists for p in profiles)
            assert all(p.task_count == 5 for p in profiles)

    def test_list_profiles_with_no_databases(self):
        """Test listing profiles when no databases exist."""
        mock_repo = Mock()

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_config = Mock(spec=Settings)
            mock_config.get_config_dir.return_value = Path(tmpdir)
            mock_config.profiles = {}

            service = TaskService(mock_repo, config=mock_config)
            profiles = service.list_profiles()

            assert len(profiles) == 0

    def test_list_profiles_configured_flag(self):
        """Test that configured flag is set correctly."""
        mock_repo = Mock()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            (config_dir / "tasks.db").touch()  # default - always configured
            (config_dir / "tasks-dev.db").touch()  # dev - always configured
            (config_dir / "tasks-custom.db").touch()  # custom - not configured

            mock_config = Mock(spec=Settings)
            mock_config.get_config_dir.return_value = config_dir
            mock_config.profiles = {}  # custom not in profiles

            service = TaskService(mock_repo, config=mock_config)

            with patch.object(service, "_count_tasks_in_profile", return_value=0):
                profiles = service.list_profiles()

            # Find profiles by name
            profile_dict = {p.name: p for p in profiles}
            assert profile_dict["default"].configured is True
            assert profile_dict["dev"].configured is True
            assert profile_dict["custom"].configured is False


class TestAuditProfile:
    """Tests for audit_profile() service method."""

    def test_audit_profile_not_found(self):
        """Test auditing a non-existent profile."""
        mock_repo = Mock()

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_config = Mock(spec=Settings)
            mock_config.get_config_dir.return_value = Path(tmpdir)

            service = TaskService(mock_repo, config=mock_config)

            with pytest.raises(ValueError) as exc_info:
                service.audit_profile("nonexistent")

            assert "not found" in str(exc_info.value).lower()


class TestDeleteProfile:
    """Tests for delete_profile() service method."""

    def test_delete_profile_removes_database(self):
        """Test that delete_profile removes the database file."""
        mock_repo = Mock()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create database file
            db_path = Path(tmpdir) / "tasks-todelete.db"
            db_path.touch()
            assert db_path.exists()

            # Mock config
            mock_config = Mock(spec=Settings)
            mock_config.get_config_dir.return_value = Path(tmpdir)
            mock_config.profiles = {}

            service = TaskService(mock_repo, config=mock_config)

            # Mock config path (no settings.toml)
            with patch("taskmanager.config.get_user_config_path") as mock_get_path:
                mock_get_path.return_value = Path(tmpdir) / "config.toml"
                service.delete_profile("todelete")

            # Assert database is gone
            assert not db_path.exists()

    def test_delete_profile_protects_builtin_profiles(self):
        """Test that built-in profiles cannot be deleted."""
        mock_repo = Mock()
        mock_config = Mock(spec=Settings)

        service = TaskService(mock_repo, config=mock_config)

        for builtin in ["default", "dev", "test"]:
            with pytest.raises(ValueError) as exc_info:
                service.delete_profile(builtin)
            assert "cannot delete" in str(exc_info.value).lower()
            assert builtin in str(exc_info.value).lower()


class TestCountTasksInProfile:
    """Tests for _count_tasks_in_profile() helper method."""

    def test_count_tasks_returns_zero_on_error(self):
        """Test that count_tasks returns 0 on database error."""
        mock_repo = Mock()
        mock_config = Mock(spec=Settings)

        service = TaskService(mock_repo, config=mock_config)

        # Mock database engine to raise exception
        with patch("taskmanager.database.get_engine") as mock_get_engine:
            mock_get_engine.side_effect = Exception("Database error")
            count = service._count_tasks_in_profile("test")

        assert count == 0
