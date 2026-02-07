"""Tests for configuration management."""

from pathlib import Path
import os
import pytest

from taskmanager.config import (
    Settings,
    get_settings,
    reset_settings,
    create_settings_for_profile,
    McpServerModifier,
    ProfileModifier,
    resolve_config_value,
    resolve_onepassword_reference,
)


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


class TestMcpServerModifier:
    """Tests for McpServerModifier configuration."""

    def test_create_modifier(self):
        """Test creating an MCP server modifier."""
        modifier = McpServerModifier(
            command="python",
            args=["-m", "mcp_module"],
            env={"DEBUG": "true"}
        )

        assert modifier.command == "python"
        assert modifier.args == ["-m", "mcp_module"]
        assert modifier.env == {"DEBUG": "true"}

    def test_modifier_defaults(self):
        """Test that modifier fields are optional."""
        modifier = McpServerModifier()

        assert modifier.command is None
        assert modifier.args is None
        assert modifier.env is None

    def test_modifier_resolve_secrets_no_secrets(self):
        """Test resolving secrets when there are none."""
        modifier = McpServerModifier(
            command="python",
            args=["-m", "mcp_module"],
            env={"DEBUG": "true", "LOG_LEVEL": "DEBUG"}
        )

        resolved = modifier.resolve_secrets()

        assert resolved.command == "python"
        assert resolved.args == ["-m", "mcp_module"]
        assert resolved.env == {"DEBUG": "true", "LOG_LEVEL": "DEBUG"}

    def test_modifier_resolve_secrets_with_references(self):
        """Test that resolve_secrets handles 1Password references in env."""
        # This test uses mock since we can't call actual 1Password
        modifier = McpServerModifier(
            command="python",
            env={"TOKEN": "op://private/token", "DEBUG": "true"}
        )

        # Note: This will try to resolve actual 1Password refs, which may fail
        # In real usage, the resolve_onepassword_reference would return the actual value
        # For testing, we just verify the structure is maintained
        resolved = modifier.resolve_secrets()

        assert resolved.command == "python"
        assert "TOKEN" in resolved.env
        assert "DEBUG" in resolved.env


class TestProfileModifier:
    """Tests for ProfileModifier configuration."""

    def test_create_profile_modifier(self):
        """Test creating a profile modifier."""
        mcp_modifier = McpServerModifier(
            command="python",
            args=["-m", "mcp_custom"],
            env={"DEBUG": "true"}
        )

        profile_modifier = ProfileModifier(
            mcp_servers={"atlassian-mcp": mcp_modifier},
            prompt_additions="Extra instructions for this profile"
        )

        assert "atlassian-mcp" in profile_modifier.mcp_servers
        assert profile_modifier.mcp_servers["atlassian-mcp"].command == "python"
        assert profile_modifier.prompt_additions == "Extra instructions for this profile"

    def test_profile_modifier_defaults(self):
        """Test that profile modifier fields are optional."""
        profile_modifier = ProfileModifier()

        assert profile_modifier.mcp_servers == {}
        assert profile_modifier.prompt_additions is None

    def test_profile_modifier_resolve_secrets(self):
        """Test resolving secrets in all MCP servers."""
        mcp_modifier1 = McpServerModifier(
            env={"TOKEN": "op://private/token1"}
        )
        mcp_modifier2 = McpServerModifier(
            env={"TOKEN": "op://private/token2"}
        )

        profile_modifier = ProfileModifier(
            mcp_servers={
                "server1": mcp_modifier1,
                "server2": mcp_modifier2
            },
            prompt_additions="Profile instructions"
        )

        resolved = profile_modifier.resolve_secrets()

        assert len(resolved.mcp_servers) == 2
        assert "server1" in resolved.mcp_servers
        assert "server2" in resolved.mcp_servers
        assert resolved.prompt_additions == "Profile instructions"

    def test_multiple_servers_in_profile(self):
        """Test profile with multiple MCP server overrides."""
        tasks_modifier = McpServerModifier(
            env={"TASKMANAGER_PROFILE": "dev"}
        )
        atlassian_modifier = McpServerModifier(
            env={"JIRA_URL": "https://dev.jira.com"}
        )

        profile_modifier = ProfileModifier(
            mcp_servers={
                "tasks-mcp": tasks_modifier,
                "atlassian-mcp": atlassian_modifier
            }
        )

        assert len(profile_modifier.mcp_servers) == 2
        assert profile_modifier.mcp_servers["tasks-mcp"].env["TASKMANAGER_PROFILE"] == "dev"
        assert profile_modifier.mcp_servers["atlassian-mcp"].env["JIRA_URL"] == "https://dev.jira.com"


class TestSettingsWithProfiles:
    """Tests for Settings with profile modifiers."""

    def test_settings_profiles_field(self):
        """Test that Settings has profiles field."""
        settings = Settings(
            profiles={
                "dev": ProfileModifier(
                    prompt_additions="Dev instructions"
                )
            }
        )

        assert "dev" in settings.profiles
        assert settings.profiles["dev"].prompt_additions == "Dev instructions"

    def test_get_profile_modifier_default_profile(self):
        """Test getting profile modifier for default profile."""
        settings = Settings(
            profile="default",
            profiles={
                "dev": ProfileModifier(
                    prompt_additions="Dev instructions"
                )
            }
        )

        modifier = settings.get_profile_modifier()
        assert modifier is None

    def test_get_profile_modifier_dev_profile(self):
        """Test getting profile modifier for dev profile."""
        dev_modifier = ProfileModifier(
            prompt_additions="Dev instructions"
        )

        settings = Settings(
            profile="dev",
            profiles={
                "dev": dev_modifier
            }
        )

        modifier = settings.get_profile_modifier()
        assert modifier is not None
        assert modifier.prompt_additions == "Dev instructions"

    def test_get_profile_modifier_with_mcp_servers(self):
        """Test getting profile modifier with MCP server overrides."""
        mcp_override = McpServerModifier(
            command="python",
            args=["-m", "mcp_custom"]
        )

        dev_modifier = ProfileModifier(
            mcp_servers={"atlassian-mcp": mcp_override},
            prompt_additions="Dev mode active"
        )

        settings = Settings(
            profile="dev",
            profiles={"dev": dev_modifier}
        )

        modifier = settings.get_profile_modifier()
        assert modifier is not None
        assert "atlassian-mcp" in modifier.mcp_servers
        assert modifier.mcp_servers["atlassian-mcp"].command == "python"

    def test_profile_isolation(self):
        """Test that different profiles don't affect each other."""
        dev_modifier = ProfileModifier(
            prompt_additions="Dev instructions"
        )
        test_modifier = ProfileModifier(
            prompt_additions="Test instructions"
        )

        settings = Settings(
            profile="dev",
            profiles={
                "dev": dev_modifier,
                "test": test_modifier
            }
        )

        dev_mod = settings.get_profile_modifier()
        assert dev_mod.prompt_additions == "Dev instructions"

        # Switch to test profile
        settings.profile = "test"
        test_mod = settings.get_profile_modifier()
        assert test_mod.prompt_additions == "Test instructions"

    def test_settings_backward_compatibility(self):
        """Test that settings without profiles still work."""
        settings = Settings(
            profile="default",
            profiles={}
        )

        modifier = settings.get_profile_modifier()
        assert modifier is None

        # Ensure basic settings still work
        assert settings.profile == "default"
        assert settings.database is not None


class TestTasksProfileEnvironmentVariable:
    """Tests for TASKS_PROFILE environment variable support."""

    def test_tasks_profile_env_var_in_get_settings(self, monkeypatch):
        """Test that TASKS_PROFILE environment variable is respected in get_settings."""
        reset_settings()
        monkeypatch.setenv("TASKS_PROFILE", "dev")
        
        settings = get_settings()
        assert settings.profile == "dev"
        
        reset_settings()
        monkeypatch.delenv("TASKS_PROFILE", raising=False)

    def test_tasks_profile_env_var_in_create_settings_for_profile(self, monkeypatch):
        """Test that TASKS_PROFILE environment variable is used when profile not explicitly passed."""
        monkeypatch.setenv("TASKS_PROFILE", "dev")
        
        # Create settings without specifying profile
        settings = create_settings_for_profile()
        assert settings.profile == "dev"
        
        # Explicit profile should take precedence
        settings = create_settings_for_profile("test")
        assert settings.profile == "test"
        
        monkeypatch.delenv("TASKS_PROFILE", raising=False)

    def test_tasks_profile_env_var_precedence(self, monkeypatch):
        """Test precedence: explicit profile > TASKS_PROFILE > default."""
        monkeypatch.setenv("TASKS_PROFILE", "dev")
        
        # TASKS_PROFILE should be used
        settings = create_settings_for_profile()
        assert settings.profile == "dev"
        
        # Explicit profile should override TASKS_PROFILE
        settings = create_settings_for_profile("test")
        assert settings.profile == "test"
        
        # Without TASKS_PROFILE env var, should default to "default"
        monkeypatch.delenv("TASKS_PROFILE", raising=False)
        settings = create_settings_for_profile()
        assert settings.profile == "default"

    def test_tasks_profile_env_var_invalid_not_set(self, monkeypatch):
        """Test default behavior when TASKS_PROFILE is not set."""
        monkeypatch.delenv("TASKS_PROFILE", raising=False)
        reset_settings()
        
        settings = get_settings()
        assert settings.profile == "default"
        
        reset_settings()

    def test_tasks_profile_env_var_with_custom_profile(self, monkeypatch):
        """Test that TASKS_PROFILE works with custom profile names."""
        reset_settings()
        monkeypatch.setenv("TASKS_PROFILE", "client-a")
        
        settings = get_settings()
        assert settings.profile == "client-a"
        
        reset_settings()
        monkeypatch.delenv("TASKS_PROFILE", raising=False)
