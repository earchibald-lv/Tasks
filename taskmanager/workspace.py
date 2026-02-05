"""Workspace management for LLM agent persistence.

This module handles persistent workspaces for tasks, allowing LLM agents
to store context, code, logs, and other artifacts in task-specific directories.
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import TypedDict


class WorkspaceMetadata(TypedDict):
    """Metadata for a task workspace."""

    task_id: int
    workspace_path: str
    created_at: str
    git_initialized: bool
    last_accessed: str | None


class WorkspaceManager:
    """Manages persistent workspaces for task-specific LLM agent work."""

    def __init__(self, base_dir: Path | None = None):
        """Initialize workspace manager.

        Args:
            base_dir: Base directory for workspaces. If None, uses default.
        """
        if base_dir is None:
            base_dir = self._get_default_base_dir()

        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _get_default_base_dir() -> Path:
        """Get the default base directory for workspaces.

        Returns:
            Path: ~/.taskmanager/workspaces
        """
        return Path.home() / ".taskmanager" / "workspaces"

    def get_workspace_path(self, task_id: int) -> Path:
        """Get the workspace directory path for a specific task.

        Args:
            task_id: The task ID

        Returns:
            Path to the task's workspace directory
        """
        return self.base_dir / f"task_{task_id}"

    def create_workspace(
        self,
        task_id: int,
        initialize_git: bool = True
    ) -> WorkspaceMetadata:
        """Create a new workspace for a task.

        Args:
            task_id: The task ID
            initialize_git: Whether to initialize a git repository

        Returns:
            Metadata for the created workspace

        Raises:
            ValueError: If workspace already exists
        """
        workspace_path = self.get_workspace_path(task_id)

        if workspace_path.exists():
            raise ValueError(f"Workspace already exists for task #{task_id}")

        # Create workspace directory structure
        workspace_path.mkdir(parents=True, exist_ok=False)

        # Create standard subdirectories
        (workspace_path / "notes").mkdir(exist_ok=True)
        (workspace_path / "code").mkdir(exist_ok=True)
        (workspace_path / "logs").mkdir(exist_ok=True)
        (workspace_path / "tmp").mkdir(exist_ok=True)

        # Create README
        readme_content = f"""# Workspace for Task #{task_id}

This directory is a persistent workspace for LLM agent work on this task.

## Directory Structure

- `notes/` - Documentation, notes, and context files
- `code/` - Code snippets and experiments
- `logs/` - Execution logs and debugging output
- `tmp/` - Temporary files (can be cleared)

## Usage

This workspace is scoped to task #{task_id} and provides a sandboxed
environment for agent operations.

Created: {datetime.now().isoformat()}
"""
        (workspace_path / "README.md").write_text(readme_content)

        # Initialize git if requested
        git_initialized = False
        if initialize_git:
            git_initialized = self._init_git(workspace_path)

        # Create metadata
        metadata: WorkspaceMetadata = {
            "task_id": task_id,
            "workspace_path": str(workspace_path),
            "created_at": datetime.now().isoformat(),
            "git_initialized": git_initialized,
            "last_accessed": None
        }

        # Write metadata file
        self._write_metadata(workspace_path, metadata)

        return metadata

    def _init_git(self, workspace_path: Path) -> bool:
        """Initialize a git repository in the workspace.

        Args:
            workspace_path: Path to the workspace directory

        Returns:
            bool: True if git was initialized successfully
        """
        try:
            # Initialize git repo
            subprocess.run(
                ["git", "init"],
                cwd=workspace_path,
                capture_output=True,
                check=True
            )

            # Create .gitignore
            gitignore_content = """# Temporary files
tmp/
*.tmp
*.log

# System files
.DS_Store
Thumbs.db
"""
            (workspace_path / ".gitignore").write_text(gitignore_content)

            # Initial commit
            subprocess.run(
                ["git", "add", "."],
                cwd=workspace_path,
                capture_output=True,
                check=True
            )
            subprocess.run(
                ["git", "commit", "-m", "Initial workspace setup"],
                cwd=workspace_path,
                capture_output=True,
                check=True
            )

            return True

        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _write_metadata(self, workspace_path: Path, metadata: WorkspaceMetadata) -> None:
        """Write workspace metadata to file.

        Args:
            workspace_path: Path to the workspace directory
            metadata: Metadata to write
        """
        metadata_path = workspace_path / ".workspace.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

    def _read_metadata(self, workspace_path: Path) -> WorkspaceMetadata | None:
        """Read workspace metadata from file.

        Args:
            workspace_path: Path to the workspace directory

        Returns:
            Metadata if found, None otherwise
        """
        metadata_path = workspace_path / ".workspace.json"
        if not metadata_path.exists():
            return None

        try:
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
            return metadata
        except (json.JSONDecodeError, OSError):
            return None

    def workspace_exists(self, task_id: int) -> bool:
        """Check if a workspace exists for a task.

        Args:
            task_id: The task ID

        Returns:
            bool: True if workspace exists
        """
        workspace_path = self.get_workspace_path(task_id)
        return workspace_path.exists() and workspace_path.is_dir()

    def get_workspace_metadata(self, task_id: int) -> WorkspaceMetadata | None:
        """Get metadata for a task's workspace.

        Args:
            task_id: The task ID

        Returns:
            Workspace metadata if found, None otherwise
        """
        if not self.workspace_exists(task_id):
            return None

        workspace_path = self.get_workspace_path(task_id)
        metadata = self._read_metadata(workspace_path)

        if metadata:
            # Update last accessed time
            metadata["last_accessed"] = datetime.now().isoformat()
            self._write_metadata(workspace_path, metadata)

        return metadata

    def delete_workspace(self, task_id: int) -> bool:
        """Delete a workspace and all its contents.

        Args:
            task_id: The task ID

        Returns:
            bool: True if workspace was deleted, False if not found
        """
        workspace_path = self.get_workspace_path(task_id)

        if not workspace_path.exists():
            return False

        # Recursively delete the workspace
        import shutil
        shutil.rmtree(workspace_path)

        return True

    def list_workspaces(self) -> list[int]:
        """List all task IDs that have workspaces.

        Returns:
            List of task IDs with workspaces
        """
        if not self.base_dir.exists():
            return []

        task_ids = []
        for item in self.base_dir.iterdir():
            if item.is_dir() and item.name.startswith("task_"):
                try:
                    task_id = int(item.name.split("_")[1])
                    task_ids.append(task_id)
                except (ValueError, IndexError):
                    continue

        return sorted(task_ids)

    def cleanup_tmp(self, task_id: int) -> int:
        """Clean up temporary files in a workspace.

        Args:
            task_id: The task ID

        Returns:
            Number of files removed
        """
        workspace_path = self.get_workspace_path(task_id)
        tmp_dir = workspace_path / "tmp"

        if not tmp_dir.exists():
            return 0

        count = 0
        import shutil
        for item in tmp_dir.iterdir():
            if item.is_file():
                item.unlink()
                count += 1
            elif item.is_dir():
                shutil.rmtree(item)
                count += 1

        return count
