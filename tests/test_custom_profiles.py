"""Tests for custom profile support.

Tests validate that:
- Custom profile names are accepted (alphanumeric, hyphens, underscores)
- Invalid profile names are rejected
- Custom profiles can have configured database paths
- Built-in profiles (default, dev, test) still work correctly
- Fallback database paths are generated for unconfigured custom profiles
"""

import pytest

from taskmanager.config import ProfileModifier, Settings


class TestProfileValidation:
    """Test profile name validation."""

    def test_builtin_profiles_valid(self):
        """Built-in profiles should be valid."""
        settings = Settings(profile="default")
        assert settings.profile == "default"

        settings = Settings(profile="dev")
        assert settings.profile == "dev"

        settings = Settings(profile="test")
        assert settings.profile == "test"

    def test_custom_profile_with_hyphens(self):
        """Custom profile names with hyphens should be valid."""
        settings = Settings(profile="client-a")
        assert settings.profile == "client-a"

        settings = Settings(profile="my-project")
        assert settings.profile == "my-project"

    def test_custom_profile_with_underscores(self):
        """Custom profile names with underscores should be valid."""
        settings = Settings(profile="client_a")
        assert settings.profile == "client_a"

        settings = Settings(profile="my_project")
        assert settings.profile == "my_project"

    def test_custom_profile_with_numbers(self):
        """Custom profile names with numbers should be valid."""
        settings = Settings(profile="client123")
        assert settings.profile == "client123"

        settings = Settings(profile="project2024")
        assert settings.profile == "project2024"

    def test_custom_profile_mixed_format(self):
        """Custom profile names with mixed alphanumeric, hyphens, underscores."""
        settings = Settings(profile="client-1_a")
        assert settings.profile == "client-1_a"

        settings = Settings(profile="my-project_2024")
        assert settings.profile == "my-project_2024"

    def test_invalid_profile_empty(self):
        """Empty profile name should fail."""
        with pytest.raises(ValueError):
            Settings(profile="")

    def test_invalid_profile_special_chars(self):
        """Profile names with special characters should fail."""
        with pytest.raises(ValueError):
            Settings(profile="client@123")

        with pytest.raises(ValueError):
            Settings(profile="my.project")

        with pytest.raises(ValueError):
            Settings(profile="project!2024")

        with pytest.raises(ValueError):
            Settings(profile="my/project")

    def test_invalid_profile_spaces(self):
        """Profile names with spaces should fail."""
        with pytest.raises(ValueError):
            Settings(profile="my project")

        with pytest.raises(ValueError):
            Settings(profile="client a")


class TestDatabaseUrlResolution:
    """Test database URL resolution for different profiles."""

    def test_builtin_default_profile_url(self):
        """Default profile should use standard database path."""
        settings = Settings(profile="default")
        db_url = settings.get_database_url()
        assert "tasks.db" in db_url
        assert "tasks-dev.db" not in db_url

    def test_builtin_dev_profile_url(self):
        """Dev profile should use dev database path."""
        settings = Settings(profile="dev")
        db_url = settings.get_database_url()
        assert "tasks-dev.db" in db_url

    def test_builtin_test_profile_url(self):
        """Test profile should use in-memory database."""
        settings = Settings(profile="test")
        db_url = settings.get_database_url()
        assert db_url == "sqlite:///:memory:"

    def test_custom_profile_with_configured_database(self):
        """Custom profile with configured database_url should use it."""
        settings = Settings(
            profile="client-a",
            profiles={
                "client-a": ProfileModifier(
                    database_url="sqlite:///{config}/taskmanager/custom-client-a.db"
                )
            }
        )
        db_url = settings.get_database_url()
        # Should expand {config} token
        assert "custom-client-a.db" in db_url
        assert settings.get_config_dir() is not None

    def test_custom_profile_without_configured_database(self):
        """Custom profile without database_url should use fallback path."""
        settings = Settings(profile="personal")
        db_url = settings.get_database_url()
        # Should generate fallback path with profile name
        assert "tasks-personal.db" in db_url

    def test_custom_profile_fallback_format(self):
        """Custom profile fallback path format should be: tasks-{profile}.db"""
        settings = Settings(profile="custom-profile")
        db_url = settings.get_database_url()
        assert "tasks-custom-profile.db" in db_url

    def test_database_url_override(self):
        """CLI database_url override should take precedence."""
        settings = Settings(profile="dev")
        settings.set_override("database_url", "sqlite:////tmp/override.db")
        db_url = settings.get_database_url()
        assert "/tmp/override.db" in db_url

    def test_direct_database_url_setting(self):
        """Direct database_url field should take precedence over profile."""
        settings = Settings(
            profile="dev",
            database_url="sqlite:///{config}/taskmanager/direct.db"
        )
        db_url = settings.get_database_url()
        assert "direct.db" in db_url


class TestProfileModifier:
    """Test ProfileModifier configuration."""

    def test_profile_modifier_database_url(self):
        """ProfileModifier should support database_url field."""
        modifier = ProfileModifier(
            database_url="sqlite:///{data}/tasks-custom.db"
        )
        assert modifier.database_url == "sqlite:///{data}/tasks-custom.db"

    def test_profile_modifier_with_all_fields(self):
        """ProfileModifier should support all customization fields."""
        modifier = ProfileModifier(
            database_url="sqlite:///{data}/tasks-custom.db",
            prompt_additions="Custom profile instructions",
            mcp_servers={}
        )
        assert modifier.database_url == "sqlite:///{data}/tasks-custom.db"
        assert modifier.prompt_additions == "Custom profile instructions"
        assert modifier.mcp_servers == {}

    def test_profile_modifier_resolve_secrets(self):
        """ProfileModifier.resolve_secrets should preserve database_url."""
        modifier = ProfileModifier(
            database_url="sqlite:///{data}/tasks-custom.db",
            prompt_additions="Test"
        )
        resolved = modifier.resolve_secrets()
        assert resolved.database_url == "sqlite:///{data}/tasks-custom.db"
        assert resolved.prompt_additions == "Test"


class TestSettingsProfileIntegration:
    """Test Settings integration with custom profiles."""

    def test_settings_with_profiles_dict(self):
        """Settings should accept profiles dictionary."""
        settings = Settings(
            profile="client-a",
            profiles={
                "client-a": ProfileModifier(
                    database_url="sqlite:///{config}/taskmanager/client-a.db"
                ),
                "personal": ProfileModifier(
                    database_url="sqlite:///{config}/taskmanager/personal.db"
                )
            }
        )
        assert "client-a" in settings.profiles
        assert "personal" in settings.profiles

    def test_get_profile_modifier(self):
        """Settings should be able to get modifier for active profile."""
        modifier = ProfileModifier(
            database_url="sqlite:///{config}/taskmanager/custom.db"
        )
        settings = Settings(
            profile="custom",
            profiles={"custom": modifier}
        )
        # Access the modifier directly
        assert settings.profiles.get("custom") == modifier

    def test_multiple_custom_profiles(self):
        """Settings should support multiple custom profiles."""
        settings = Settings(
            profiles={
                "project-1": ProfileModifier(
                    database_url="sqlite:///{config}/taskmanager/project-1.db"
                ),
                "project-2": ProfileModifier(
                    database_url="sqlite:///{config}/taskmanager/project-2.db"
                ),
                "client-a": ProfileModifier(
                    database_url="sqlite:///{config}/taskmanager/client-a.db"
                )
            }
        )
        assert len(settings.profiles) == 3
        assert "project-1" in settings.profiles
        assert "project-2" in settings.profiles
        assert "client-a" in settings.profiles
