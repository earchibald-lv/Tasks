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
        assert settings.profile == "default"
        assert isinstance(settings.get_config_dir(), Path)
        assert settings.mcp.server_name == "tasks_mcp"
        assert settings.mcp.transport == "stdio"
        assert settings.defaults.task_limit == 20
        assert settings.defaults.max_task_limit == 100
        assert settings.logging.level == "INFO"

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

    def test_ensure_directories_creates_directory(self, tmp_path):
        """Test that ensure_directories creates the directories."""
        # We can't easily test this with tmp_path since it uses XDG paths
        # Just test that it runs without error
        settings = Settings()
        settings.ensure_directories()
        
        # Verify config dir was created
        assert settings.get_config_dir().exists()

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
