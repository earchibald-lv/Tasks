"""Application configuration management.

This module provides centralized configuration using Pydantic Settings,
supporting environment variables, TOML files, and sensible defaults.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings shared by CLI and MCP server.

    Settings are loaded from:
    1. Environment variables (TASKMANAGER_* prefix)
    2. Config file (~/.taskmanager/config.toml)
    3. Defaults defined here
    """

    model_config = SettingsConfigDict(
        env_prefix="TASKMANAGER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application metadata
    app_name: str = Field(default="Task Manager", description="Application name")
    version: str = Field(default="0.1.0", description="Application version")

    # Paths
    data_dir: Path = Field(
        default_factory=lambda: Path.home() / ".taskmanager",
        description="Directory for application data",
    )

    # Database configuration
    database_url: str | None = Field(
        default=None, description="SQLite database URL (auto-generated if None)"
    )

    # MCP Server configuration
    mcp_server_name: str = Field(default="tasks_mcp", description="MCP server identification name")
    mcp_transport: str = Field(
        default="stdio", description="MCP transport protocol (stdio or streamable_http)"
    )

    # Application defaults
    default_task_limit: int = Field(
        default=20, ge=1, le=100, description="Default number of tasks in list operations"
    )
    max_task_limit: int = Field(
        default=100, ge=1, description="Maximum allowed tasks in single query"
    )

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: Path | None = Field(default=None, description="Log file path (None for no file)")

    def get_database_url(self) -> str:
        """Get the database URL, creating default if not specified.

        Returns:
            str: SQLite database URL.
        """
        if self.database_url:
            return self.database_url

        # Default to SQLite file in data directory
        db_path = self.data_dir / "tasks.db"
        return f"sqlite:///{db_path}"

    def ensure_data_dir(self) -> Path:
        """Ensure data directory exists and return path.

        Returns:
            Path: The data directory path.
        """
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir


# Singleton instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the application settings singleton.

    Returns:
        Settings: The application settings instance.
    """
    global _settings
    if _settings is None:
        _settings = Settings()
        _settings.ensure_data_dir()
    return _settings


def reset_settings() -> None:
    """Reset settings singleton (useful for testing)."""
    global _settings
    _settings = None
