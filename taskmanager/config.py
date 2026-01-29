"""Application configuration management.

This module provides centralized configuration using Pydantic Settings with:
- TOML configuration files (user + project)
- Environment variables
- CLI flag overrides
- Profile system (default, dev, test)
- Path token expansion ({config}, {home}, {data})
"""

import os
import subprocess
import sys
import tomllib  # Python 3.11+ standard library
from pathlib import Path
from typing import Any

import tomli_w
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseProfiles(BaseModel):
    """Database URLs for different profiles."""

    default: str = Field(
        default="sqlite:///{config}/taskmanager/tasks.db",
        description="Production database",
    )
    dev: str = Field(
        default="sqlite:///{config}/taskmanager/tasks-dev.db",
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

    # Configuration sections
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    mcp: McpConfig = Field(default_factory=McpConfig)

    # Legacy single database URL (for backward compatibility)
    database_url: str | None = Field(default=None, description="Direct database URL override")

    # Runtime overrides (set via CLI flags)
    _overrides: dict[str, Any] = {}

    @field_validator("profile")
    @classmethod
    def validate_profile(cls, v: str) -> str:
        """Validate profile name."""
        valid_profiles = {"default", "dev", "test"}
        if v not in valid_profiles:
            raise ValueError(f"Invalid profile '{v}'. Must be one of: {valid_profiles}")
        return v

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

        # Get URL from active profile
        profile_urls = {
            "default": self.database.profiles.default,
            "dev": self.database.profiles.dev,
            "test": self.database.profiles.test,
        }

        url = profile_urls.get(self.profile, self.database.profiles.default)
        return self.expand_path_tokens(url)

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
                "default": "sqlite:///{config}/taskmanager/tasks.db",
                "dev": "sqlite:///{config}/taskmanager/tasks-dev.db",
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
        for key in ["database", "defaults", "logging", "mcp"]:
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
