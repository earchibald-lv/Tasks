"""Application configuration management.

This module provides centralized configuration using Pydantic Settings with:
- TOML configuration files (user + project)
- Environment variables
- CLI flag overrides
- Profile system (default, dev, test)
- Path token expansion ({config}, {home}, {data})
- 1Password secret references (op://...) with runtime resolution
"""

import os
import subprocess
import sys
import tomllib  # Python 3.11+ standard library
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import tomli_w
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_system_timezone() -> str:
    """Auto-detect the system's local timezone using IANA timezone names.
    
    Returns:
        str: IANA timezone name (e.g., 'America/Los_Angeles')
    """
    try:
        import time
        
        # Map common timezone abbreviations to IANA names
        tz_map = {
            'PST': 'America/Los_Angeles',
            'PDT': 'America/Los_Angeles',
            'EST': 'America/New_York',
            'EDT': 'America/New_York',
            'CST': 'America/Chicago',
            'CDT': 'America/Chicago',
            'MST': 'America/Denver',
            'MDT': 'America/Denver',
            'GMT': 'UTC',
            'BST': 'Europe/London',
            'CET': 'Europe/Paris',
            'CEST': 'Europe/Paris',
            'UTC': 'UTC',
        }
        
        # Get local timezone abbreviation
        tz_abbr = time.tzname[time.daylight]
        
        # Return mapped IANA name or UTC as fallback
        return tz_map.get(tz_abbr, 'UTC')
        
    except Exception:
        # Fallback to UTC if detection fails
        return "UTC"


def is_onepassword_reference(value: str | None) -> bool:
    """Check if a value is a 1Password secret reference.
    
    Args:
        value: The value to check
        
    Returns:
        bool: True if value looks like op://...
    """
    return value is not None and isinstance(value, str) and value.startswith("op://")


def resolve_onepassword_reference(reference: str) -> str | None:
    """Resolve a 1Password secret reference to its actual value.
    
    Args:
        reference: The 1Password reference (e.g., op://private/jira/token)
        
    Returns:
        str | None: The resolved secret value, or None if resolution fails
    """
    if not is_onepassword_reference(reference):
        return reference
    
    try:
        result = subprocess.run(
            ["op", "read", reference, "--no-newline"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True
        )
        return result.stdout.strip() if result.stdout else None
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        # Return None if 1Password resolution fails
        # The calling code can decide how to handle this
        return None


def resolve_config_value(value: str | None) -> str | None:
    """Resolve a config value, handling 1Password references.
    
    Args:
        value: The config value (may be a 1Password reference or plain value)
        
    Returns:
        str | None: The resolved value, or the original if not a reference
    """
    if value and is_onepassword_reference(value):
        return resolve_onepassword_reference(value)
    return value


class DatabaseProfiles(BaseModel):
    """Database URLs for different profiles."""

    default: str = Field(
        default="sqlite:///{config}/tasks.db",
        description="Production database",
    )
    dev: str = Field(
        default="sqlite:///{config}/tasks-dev.db",
        description="Development database",
    )
    test: str = Field(
        default="sqlite:///:memory:",
        description="Test database (in-memory)",
    )


class DatabaseConfig(BaseModel):
    """Database configuration with profile support."""

    profiles: DatabaseProfiles = Field(default_factory=DatabaseProfiles)


class DefaultsConfig(BaseModel):
    """Application defaults."""

    task_limit: int = Field(default=20, ge=1, le=100, description="Default task list limit")
    max_task_limit: int = Field(default=100, ge=1, description="Maximum task list limit")


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = Field(default="INFO", description="Log level")
    file: str | None = Field(default=None, description="Log file path")


class McpConfig(BaseModel):
    """MCP server configuration."""

    server_name: str = Field(default="tasks_mcp", description="MCP server name")
    transport: str = Field(default="stdio", description="MCP transport protocol")


class AtlassianConfig(BaseModel):
    """Atlassian (JIRA & Confluence) integration configuration.
    
    Supports 1Password secret references for all credential fields.
    Example: jira_token = "op://private/jira/token"
    """

    jira_url: str | None = Field(default=None, description="Base JIRA URL or 1Password reference (e.g., https://jira.company.com or op://private/jira/url)")
    jira_username: str | None = Field(default=None, description="JIRA username/email or 1Password reference")
    jira_token: str | None = Field(default=None, description="JIRA personal access token or 1Password reference")
    jira_user_identifier: str | None = Field(default=None, description="JIRA user identifier for lookups (email, username, or account ID). If not set, uses jira_username.")
    jira_ssl_verify: bool = Field(default=True, description="Verify SSL certificates for JIRA")
    
    confluence_url: str | None = Field(default=None, description="Base Confluence URL or 1Password reference")
    confluence_username: str | None = Field(default=None, description="Confluence username/email or 1Password reference")
    confluence_token: str | None = Field(default=None, description="Confluence personal access token or 1Password reference")
    confluence_ssl_verify: bool = Field(default=True, description="Verify SSL certificates for Confluence")
    
    def resolve_secrets(self) -> "AtlassianConfig":
        """Resolve any 1Password secret references in this configuration.
        
        Returns:
            AtlassianConfig: A new config with all 1Password references resolved
        """
        return AtlassianConfig(
            jira_url=resolve_config_value(self.jira_url),
            jira_username=resolve_config_value(self.jira_username),
            jira_token=resolve_config_value(self.jira_token),
            jira_user_identifier=resolve_config_value(self.jira_user_identifier),
            jira_ssl_verify=self.jira_ssl_verify,
            confluence_url=resolve_config_value(self.confluence_url),
            confluence_username=resolve_config_value(self.confluence_username),
            confluence_token=resolve_config_value(self.confluence_token),
            confluence_ssl_verify=self.confluence_ssl_verify,
        )


class McpServerModifier(BaseModel):
    """Per-MCP-server customization for a profile.
    
    Allows overriding MCP server command, arguments, and environment variables
    for profile-specific configurations.
    
    Supports 1Password secret references in environment variables.
    Example:
        command = "python"
        args = ["-m", "mcp_module"]
        env = { "TOKEN" = "op://private/mcp/token" }
    """

    command: str | None = Field(default=None, description="Override server command")
    args: list[str] | None = Field(default=None, description="Override server arguments")
    env: dict[str, str] | None = Field(default=None, description="Additional/override environment variables (supports 1Password references)")
    
    def resolve_secrets(self) -> "McpServerModifier":
        """Resolve any 1Password secret references in environment variables.
        
        Returns:
            McpServerModifier: A new modifier with all 1Password references resolved
        """
        resolved_env = None
        if self.env:
            resolved_env = {}
            for key, value in self.env.items():
                resolved_value = resolve_config_value(value)
                # Only include non-None resolved values
                if resolved_value is not None:
                    resolved_env[key] = resolved_value
                else:
                    # If resolution fails, keep original value
                    resolved_env[key] = value
        
        return McpServerModifier(
            command=self.command,
            args=self.args,
            env=resolved_env,
        )


class ProfileModifier(BaseModel):
    """Profile-level customizations for MCP servers and prompts.
    
    Allows per-profile configuration including:
    - Custom database path
    - MCP server command/args/env overrides
    - Custom system prompt additions
    
    Example:
        [profiles.client-a]
        database_url = "sqlite:///{data}/tasks-client-a.db"
        
        [profiles.dev]
        prompt_additions = "You are in DEV mode. Extra caution required."
        
        [profiles.dev.mcp_servers.atlassian-mcp]
        env = { "JIRA_URL" = "op://private/dev/jira/url" }
    """

    database_url: str | None = Field(
        default=None,
        description="Custom database URL for this profile"
    )
    mcp_servers: dict[str, McpServerModifier] = Field(
        default_factory=dict,
        description="Per-server MCP overrides"
    )
    prompt_additions: str | None = Field(
        default=None,
        description="Extra system prompt text for this profile"
    )
    
    def resolve_secrets(self) -> "ProfileModifier":
        """Resolve any 1Password secret references in all MCP servers.
        
        Returns:
            ProfileModifier: A new modifier with all 1Password references resolved
        """
        resolved_servers = {
            server_name: modifier.resolve_secrets()
            for server_name, modifier in self.mcp_servers.items()
        }
        
        return ProfileModifier(
            database_url=self.database_url,
            mcp_servers=resolved_servers,
            prompt_additions=self.prompt_additions,
        )


class Settings(BaseSettings):
    """Application settings with TOML configuration support.

    Settings are loaded in priority order (highest first):
    1. CLI flags (set via set_override())
    2. Environment variables (TASKMANAGER_* prefix)
    3. Project config (./taskmanager.toml from git root)
    4. User config (~/.config/taskmanager/config.toml)
    5. Defaults
    """

    model_config = SettingsConfigDict(
        env_prefix="TASKMANAGER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application metadata
    app_name: str = Field(default="Task Manager", description="Application name")
    version: str = Field(default="0.1.0", description="Application version")

    # Profile system
    profile: str = Field(default="default", description="Active profile (default, dev, test)")
    
    # Timezone
    timezone: str = Field(default_factory=get_system_timezone, description="Local timezone for time-aware operations (auto-detected, IANA timezone name)")

    # Configuration sections
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    mcp: McpConfig = Field(default_factory=McpConfig)
    atlassian: AtlassianConfig = Field(default_factory=AtlassianConfig)
    profiles: dict[str, ProfileModifier] = Field(default_factory=dict, description="Profile-specific customizations")

    # Legacy single database URL (for backward compatibility)
    database_url: str | None = Field(default=None, description="Direct database URL override")

    # Runtime overrides (set via CLI flags)
    _overrides: dict[str, Any] = {}

    @field_validator("profile")
    @classmethod
    def validate_profile(cls, v: str) -> str:
        """Validate profile name format.
        
        Allows alphanumeric characters, hyphens, and underscores.
        Built-in profiles (default, dev, test) are always valid.
        Custom profiles can be defined in settings.
        """
        # Validate format: alphanumeric, hyphens, underscores
        if not v or not all(c.isalnum() or c in '-_' for c in v):
            raise ValueError(f"Invalid profile '{v}'. Use alphanumeric, hyphens, or underscores.")
        return v

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """Validate timezone name."""
        try:
            ZoneInfo(v)  # Try to create a ZoneInfo to validate
            return v
        except Exception as e:
            raise ValueError(f"Invalid timezone '{v}'. Must be valid IANA timezone name (e.g., UTC, America/New_York): {e}")

    def get_config_dir(self) -> Path:
        """Get the configuration directory.

        Returns:
            Path: ~/.config/taskmanager
        """
        # XDG Base Directory standard
        xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config_home:
            return Path(xdg_config_home) / "taskmanager"
        return Path.home() / ".config" / "taskmanager"

    def get_data_dir(self) -> Path:
        """Get the data directory.

        Returns:
            Path: ~/.local/share/taskmanager
        """
        xdg_data_home = os.environ.get("XDG_DATA_HOME")
        if xdg_data_home:
            return Path(xdg_data_home) / "taskmanager"
        return Path.home() / ".local" / "share" / "taskmanager"

    def expand_path_tokens(self, path: str) -> str:
        """Expand path tokens in configuration strings.

        Args:
            path: Path string potentially containing tokens

        Returns:
            str: Path with tokens expanded
        """
        config_dir = self.get_config_dir()
        home_dir = Path.home()
        data_dir = self.get_data_dir()

        path = path.replace("{config}", str(config_dir))
        path = path.replace("{home}", str(home_dir))
        path = path.replace("{data}", str(data_dir))
        return path

    def get_database_url(self) -> str:
        """Get the database URL for the active profile.
        
        Supports:
        - Built-in profiles (default, dev, test) with standard paths
        - Custom profiles with configured database_url
        - Fallback to auto-generated path for unconfigured custom profiles

        Returns:
            str: SQLite database URL
        """
        # Check for override
        if "database_url" in self._overrides:
            url = self._overrides["database_url"]
            return self.expand_path_tokens(url)

        # Check for direct database_url setting
        if self.database_url:
            return self.expand_path_tokens(self.database_url)

        # Built-in profile URLs
        builtin_urls = {
            "default": self.database.profiles.default,
            "dev": self.database.profiles.dev,
            "test": self.database.profiles.test,
        }

        # Check built-in profiles first
        if self.profile in builtin_urls:
            url = builtin_urls[self.profile]
            return self.expand_path_tokens(url)

        # Custom profile - check for configured database_url
        custom_modifier = self.profiles.get(self.profile)
        if custom_modifier and custom_modifier.database_url:
            url = custom_modifier.database_url
            return self.expand_path_tokens(url)

        # Fallback: auto-generate path for custom profiles
        # Format: sqlite:///{data}/tasks-{profile}.db
        config_dir = self.get_config_dir()
        fallback_url = f"sqlite:///{config_dir}/taskmanager/tasks-{self.profile}.db"
        return fallback_url

    def set_override(self, key: str, value: Any) -> None:
        """Set a runtime override (from CLI flags).

        Args:
            key: Configuration key
            value: Configuration value
        """
        self._overrides[key] = value

    def ensure_directories(self) -> None:
        """Ensure configuration and data directories exist."""
        self.get_config_dir().mkdir(parents=True, exist_ok=True)
        self.get_data_dir().mkdir(parents=True, exist_ok=True)

        # Also ensure database directory exists
        db_url = self.get_database_url()
        if db_url.startswith("sqlite:///"):
            db_path = Path(db_url.replace("sqlite:///", ""))
            db_path.parent.mkdir(parents=True, exist_ok=True)

    def get_profile_modifier(self) -> "ProfileModifier | None":
        """Get the ProfileModifier for the currently active profile, with secrets resolved.
        
        Returns:
            ProfileModifier | None: The resolved modifier for the active profile, or None if not configured
        """
        if self.profile not in self.profiles:
            return None
        
        modifier = self.profiles[self.profile]
        return modifier.resolve_secrets()


def find_git_root() -> Path | None:
    """Find the git repository root directory.

    Returns:
        Path | None: Git root directory or None if not in a git repo
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def find_config_files() -> list[Path]:
    """Find all config files in priority order (lowest first).

    Returns:
        list[Path]: Config file paths that exist
    """
    config_files = []

    # User config
    user_config = Path.home() / ".config" / "taskmanager" / "config.toml"
    if user_config.exists():
        config_files.append(user_config)

    # Project config (from git root)
    git_root = find_git_root()
    if git_root:
        project_config = git_root / "taskmanager.toml"
        if project_config.exists():
            config_files.append(project_config)

    return config_files


def load_toml_config() -> dict[str, Any]:
    """Load and merge TOML configuration files.

    Returns:
        dict: Merged configuration
    """
    merged_config: dict[str, Any] = {}

    for config_file in find_config_files():
        try:
            with open(config_file, "rb") as f:
                file_config = tomllib.load(f)
                # Deep merge nested dicts
                for key, value in file_config.items():
                    if isinstance(value, dict) and key in merged_config:
                        merged_config[key].update(value)
                    else:
                        merged_config[key] = value
        except Exception as e:
            print(f"Warning: Failed to load config file {config_file}: {e}", file=sys.stderr)

    return merged_config


def create_default_config(path: Path) -> None:
    """Create a default configuration file.

    Args:
        path: Path to config file to create
    """
    config = {
        "general": {
            "profile": "default",
        },
        "database": {
            "profiles": {
                "default": "sqlite:///{config}/tasks.db",
                "dev": "sqlite:///{config}/tasks-dev.db",
                "test": "sqlite:///:memory:",
            }
        },
        "defaults": {
            "task_limit": 20,
            "max_task_limit": 100,
        },
        "logging": {
            "level": "INFO",
        },
        "mcp": {
            "server_name": "tasks_mcp",
            "transport": "stdio",
        },
        "atlassian": {
            "jira_url": None,  # Set to JIRA URL or 1Password ref: "op://private/jira/url" or "https://jira.company.com"
            "jira_username": None,  # Set to username or 1Password ref: "op://private/jira/username"
            "jira_token": None,  # Set to token or 1Password ref: "op://private/jira/token"
            "jira_ssl_verify": True,  # Set to False to disable SSL verification
            "confluence_url": None,  # Set to Confluence URL or 1Password ref: "op://private/confluence/url"
            "confluence_username": None,  # Set to username or 1Password ref: "op://private/confluence/username"
            "confluence_token": None,  # Set to token or 1Password ref: "op://private/confluence/token"
            "confluence_ssl_verify": True,  # Set to False to disable SSL verification
        },
        "profiles": {
            "dev": {
                "mcp_servers": {
                    # Example: Override atlassian-mcp for dev profile
                    # "atlassian-mcp": {
                    #     "env": {
                    #         "JIRA_URL": "op://private/dev/jira/url",
                    #         "JIRA_PERSONAL_TOKEN": "op://private/dev/jira/token"
                    #     }
                    # }
                },
                # Example: Add dev-specific instructions
                # "prompt_additions": "You are in DEV profile. Extra caution required:\n- Confirm all JIRA updates with user before execution\n- Never delete issues without explicit confirmation"
            }
        },
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        tomli_w.dump(config, f)


# Singleton instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the application settings singleton.

    Returns:
        Settings: The application settings instance
    """
    global _settings
    if _settings is None:
        # Load TOML config
        toml_config = load_toml_config()

        # Flatten nested config for Pydantic
        flat_config: dict[str, Any] = {}
        
        # Handle general section
        if "general" in toml_config:
            flat_config.update(toml_config["general"])
        
        # Pass nested sections as-is
        for key in ["database", "defaults", "logging", "mcp", "atlassian", "profiles"]:
            if key in toml_config:
                flat_config[key] = toml_config[key]

        # Create settings with TOML config
        _settings = Settings(**flat_config)
        _settings.ensure_directories()

        # Auto-create user config if none exists
        user_config = Path.home() / ".config" / "taskmanager" / "config.toml"
        if not user_config.exists() and not find_config_files():
            create_default_config(user_config)

    return _settings


def reset_settings() -> None:
    """Reset settings singleton (useful for testing)."""
    global _settings
    _settings = None


def create_settings_for_profile(profile: str) -> Settings:
    """Create a new Settings instance for a specific profile.

    This bypasses the singleton pattern to allow multiple profiles
    to be used simultaneously (e.g., in MCP server with per-tool profiles).

    Args:
        profile: Database profile to use (default, dev, test)

    Returns:
        Settings: A new Settings instance configured for the profile
    """
    # Load TOML config
    toml_config = load_toml_config()

    # Flatten nested config for Pydantic
    flat_config: dict[str, Any] = {}

    # Handle general section
    if "general" in toml_config:
        flat_config.update(toml_config["general"])

    # Override profile
    flat_config["profile"] = profile

    # Pass nested sections as-is
    for key in ["database", "defaults", "logging", "mcp", "atlassian", "profiles"]:
        if key in toml_config:
            flat_config[key] = toml_config[key]

    # Create settings with TOML config
    settings = Settings(**flat_config)
    settings.ensure_directories()

    return settings


def get_user_config_path() -> Path:
    """Get the user configuration file path.

    Returns:
        Path: User config file path
    """
    return Path.home() / ".config" / "taskmanager" / "config.toml"


def get_project_config_path() -> Path | None:
    """Get the project configuration file path.

    Returns:
        Path | None: Project config path or None if not in git repo
    """
    git_root = find_git_root()
    if git_root:
        return git_root / "taskmanager.toml"
    return None
