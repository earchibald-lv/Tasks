"""Tests for configuration management."""

from pathlib import Path

from taskmanager.config import Settings, get_settings, reset_settings


class TestSettings:
    """Tests for Settings configuration."""

    def test_default_settings(self):
        """Test that default settings are properly initialized."""
        settings = Settings()

        assert settings.app_name == "Task Manager"
        assert settings.version == "0.1.0"
        assert isinstance(settings.data_dir, Path)
        assert settings.mcp_server_name == "tasks_mcp"
        assert settings.mcp_transport == "stdio"
        assert settings.default_task_limit == 20
        assert settings.max_task_limit == 100
        assert settings.log_level == "INFO"

    def test_get_database_url_default(self):
        """Test default database URL generation."""
        settings = Settings()
        db_url = settings.get_database_url()

        assert db_url.startswith("sqlite:///")
        assert "tasks.db" in db_url

    def test_get_database_url_custom(self):
        """Test custom database URL."""
        settings = Settings(database_url="sqlite:///custom.db")
        db_url = settings.get_database_url()

        assert db_url == "sqlite:///custom.db"

    def test_ensure_data_dir_creates_directory(self, tmp_path):
        """Test that ensure_data_dir creates the directory."""
        test_dir = tmp_path / "test_taskmanager"
        settings = Settings(data_dir=test_dir)

        assert not test_dir.exists()

        result = settings.ensure_data_dir()

        assert test_dir.exists()
        assert result == test_dir

    def test_get_settings_singleton(self):
        """Test that get_settings returns the same instance."""
        reset_settings()

        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2

    def test_reset_settings(self):
        """Test that reset_settings clears the singleton."""
        settings1 = get_settings()
        reset_settings()
        settings2 = get_settings()

        assert settings1 is not settings2
