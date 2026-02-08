"""Business logic layer for task management.

This module provides the service layer that sits between the interface
layer (CLI, MCP) and the repository layer, implementing core business
logic and validation rules.
"""

import tomllib
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING

try:
    import tomli_w
except ImportError:
    tomli_w = None

from sqlmodel import Session

from taskmanager.attachments import (
    AttachmentManager,
    AttachmentMetadata,
    parse_attachments,
    serialize_attachments,
)
from taskmanager.config import Settings, get_settings
from taskmanager.models import Attachment, Priority, Task, TaskStatus
from taskmanager.repository import TaskRepository
from taskmanager.workspace import WorkspaceManager, WorkspaceMetadata

if TYPE_CHECKING:
    from taskmanager.services.search import SemanticSearchService


@dataclass
class ProfileInfo:
    """Information about a profile database."""

    name: str
    database_path: str
    exists: bool
    size_bytes: int
    task_count: int
    configured: bool  # Is it in settings.toml?
    last_modified: datetime | None
    created: datetime | None


@dataclass
class ProfileAudit:
    """Audit information for a profile before deletion."""

    name: str
    location: str
    size_bytes: int
    task_count: int
    configured: bool
    last_modified: datetime | None
    oldest_task: Task | None
    newest_task: Task | None


class TaskService:
    """Service layer for task management business logic.

    This class encapsulates all business logic for task operations,
    ensuring consistency across CLI and MCP server interfaces.
    """

    def __init__(
        self,
        repository: TaskRepository,
        session: Session | None = None,
        enable_semantic_search: bool = True,
    ) -> None:
        """Initialize the task service.

        Args:
            repository: TaskRepository implementation for data access.
            session: Optional SQLModel Session for database operations on attachments.
            enable_semantic_search: Whether to enable semantic search indexing (default: True).
        """
        self.repository = repository
        self.session = session
        self.attachment_manager = AttachmentManager()
        self.workspace_manager = WorkspaceManager()
        self._config = None
        self._enable_semantic_search = enable_semantic_search
        self._search_service = None

    @property
    def config(self) -> "Settings":
        """Get the Settings instance, using cached or freshly loaded."""
        if self._config is None:
            self._config = get_settings()
        return self._config

    def _get_search_service(self) -> "SemanticSearchService | None":
        """Get the semantic search service (lazy initialization).

        Returns:
            SemanticSearchService if enabled and available, None otherwise.
        """
        if not self._enable_semantic_search:
            return None

        if self._search_service is None:
            try:
                from taskmanager.services.search import SemanticSearchService

                db_url = self.config.get_database_url()
                # Extract path from sqlite:/// URL
                if db_url.startswith("sqlite:///"):
                    db_path = db_url[10:]
                else:
                    db_path = db_url
                self._search_service = SemanticSearchService(db_path)
            except Exception:
                # Semantic search not available, continue without it
                self._enable_semantic_search = False
                return None

        return self._search_service

    def _index_task(self, task: Task) -> None:
        """Index a task for semantic search (if enabled).

        Args:
            task: The task to index.
        """
        search_service = self._get_search_service()
        if search_service:
            try:
                search_service.index_task(task)
            except Exception:
                pass  # Non-critical, don't fail the operation

    def _remove_task_from_index(self, task_id: int) -> None:
        """Remove a task from the semantic search index.

        Args:
            task_id: The ID of the task to remove.
        """
        search_service = self._get_search_service()
        if search_service:
            try:
                search_service.remove_task(task_id)
            except Exception:
                pass  # Non-critical, don't fail the operation

    def create_task(
        self,
        title: str,
        description: str | None = None,
        priority: Priority = Priority.MEDIUM,
        due_date: date | None = None,
        status: TaskStatus = TaskStatus.PENDING,
        jira_issues: str | None = None,
        tags: str | None = None,
    ) -> Task:
        """Create a new task with validation.

        Args:
            title: Task title (required, will be stripped).
            description: Optional task description.
            priority: Task priority level (default: MEDIUM).
            due_date: Optional due date.
            status: Initial task status (default: PENDING).
            jira_issues: Comma-separated JIRA issue keys (e.g., "SRE-1234,DEVOPS-5678").
            tags: Comma-separated tags for categorization (e.g., "backend,api,bug-fix").

        Returns:
            Task: The created task with assigned ID.

        Raises:
            ValueError: If title is empty or invalid.
        """
        # Validate and clean title
        title = title.strip()
        if not title:
            raise ValueError("Task title cannot be empty")

        if len(title) > 200:
            raise ValueError("Task title cannot exceed 200 characters")

        # Clean description
        if description is not None:
            description = description.strip() or None

        # Clean JIRA issues
        if jira_issues is not None:
            jira_issues = jira_issues.strip() or None

        # Clean tags
        if tags is not None:
            tags = tags.strip() or None

        # Create task
        task = Task(
            title=title,
            description=description,
            priority=priority,
            due_date=due_date,
            status=status,
            jira_issues=jira_issues,
            tags=tags,
        )

        created_task = self.repository.create(task)

        # Index for semantic search
        self._index_task(created_task)

        return created_task

    def get_task(self, task_id: int) -> Task:
        """Retrieve a task by ID.

        Args:
            task_id: The unique identifier of the task.

        Returns:
            Task: The requested task.

        Raises:
            ValueError: If task_id is invalid or task not found.
        """
        if task_id < 1:
            raise ValueError("Task ID must be positive")

        task = self.repository.get_by_id(task_id)
        if task is None:
            raise ValueError(f"Task with ID {task_id} not found")

        return task

    def list_tasks(
        self,
        status: TaskStatus | None = None,
        priority: Priority | None = None,
        due_before: date | None = None,
        tag: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Task], int]:
        """List tasks with filtering and pagination.

        Args:
            status: Filter by task status (optional).
            priority: Filter by priority level (optional).
            due_before: Filter tasks due before this date (optional).
            tag: Filter by tag (exact match, optional).
            limit: Maximum number of tasks to return (default: 20).
            offset: Number of tasks to skip for pagination (default: 0).

        Returns:
            tuple[list[Task], int]: List of tasks and total count.

        Raises:
            ValueError: If limit or offset is invalid.
        """
        if limit < 1 or limit > 100:
            raise ValueError("Limit must be between 1 and 100")

        if offset < 0:
            raise ValueError("Offset must be non-negative")

        tasks = self.repository.list_tasks(
            status=status,
            priority=priority,
            due_before=due_before,
            tag=tag,
            limit=limit,
            offset=offset,
        )

        total = self.repository.count_tasks(
            status=status,
            priority=priority,
            due_before=due_before,
            tag=tag,
        )

        return tasks, total

    def update_task(
        self,
        task_id: int,
        title: str | None = None,
        description: str | None = None,
        priority: Priority | None = None,
        due_date: date | None = None,
        status: TaskStatus | None = None,
        jira_issues: str | None = None,
        tags: str | None = None,
    ) -> Task:
        """Update an existing task.

        Args:
            task_id: The unique identifier of the task to update.
            title: New title (optional).
            description: New description (optional, empty string clears it).
            priority: New priority level (optional).
            due_date: New due date (optional).
            status: New status (optional).
            jira_issues: New JIRA issues (optional, empty string clears it).
            tags: New tags (optional, empty string clears it).

        Returns:
            Task: The updated task.

        Raises:
            ValueError: If task not found or validation fails.
        """
        # Get existing task
        task = self.get_task(task_id)

        # Update fields if provided
        if title is not None:
            title = title.strip()
            if not title:
                raise ValueError("Task title cannot be empty")
            if len(title) > 200:
                raise ValueError("Task title cannot exceed 200 characters")
            task.title = title

        if description is not None:
            task.description = description.strip() or None

        if priority is not None:
            task.priority = priority

        if due_date is not None:
            task.due_date = due_date

        if status is not None:
            # Business rule: Can't reopen completed tasks directly
            if task.status == TaskStatus.COMPLETED and status == TaskStatus.PENDING:
                raise ValueError("Cannot reopen completed task. Use in_progress status first.")
            task.status = status

        if jira_issues is not None:
            task.jira_issues = jira_issues.strip() or None

        if tags is not None:
            task.tags = tags.strip() or None

        updated_task = self.repository.update(task)

        # Re-index for semantic search
        self._index_task(updated_task)

        return updated_task

    def mark_complete(self, task_id: int) -> Task:
        """Mark a task as completed.

        Args:
            task_id: The unique identifier of the task.

        Returns:
            Task: The updated task.

        Raises:
            ValueError: If task not found or already archived.
        """
        task = self.get_task(task_id)

        # Business rule: Cannot complete archived tasks
        if task.status == TaskStatus.ARCHIVED:
            raise ValueError("Cannot complete archived task")

        task.mark_complete()
        return self.repository.update(task)

    def delete_task(self, task_id: int) -> bool:
        """Delete a task.

        Args:
            task_id: The unique identifier of the task to delete.

        Returns:
            bool: True if task was deleted.

        Raises:
            ValueError: If task_id is invalid or task not found.
        """
        if task_id < 1:
            raise ValueError("Task ID must be positive")

        result = self.repository.delete(task_id)
        if not result:
            raise ValueError(f"Task with ID {task_id} not found")

        # Remove from semantic search index
        self._remove_task_from_index(task_id)

        return result

    def get_overdue_tasks(self) -> list[Task]:
        """Get all overdue tasks.

        Returns:
            list[Task]: List of tasks that are overdue and not completed.
        """
        today = date.today()
        all_tasks = self.repository.list_tasks(
            status=TaskStatus.PENDING,
            due_before=today,
            limit=100,
        )

        # Also get in-progress overdue tasks
        in_progress_tasks = self.repository.list_tasks(
            status=TaskStatus.IN_PROGRESS,
            due_before=today,
            limit=100,
        )

        return all_tasks + in_progress_tasks

    def get_statistics(self) -> dict[str, int]:
        """Get task statistics.

        Returns:
            dict[str, int]: Dictionary with task counts by status and priority.
        """
        return {
            "total": self.repository.count_tasks(),
            "pending": self.repository.count_tasks(status=TaskStatus.PENDING),
            "in_progress": self.repository.count_tasks(status=TaskStatus.IN_PROGRESS),
            "completed": self.repository.count_tasks(status=TaskStatus.COMPLETED),
            "archived": self.repository.count_tasks(status=TaskStatus.ARCHIVED),
            "low_priority": self.repository.count_tasks(priority=Priority.LOW),
            "medium_priority": self.repository.count_tasks(priority=Priority.MEDIUM),
            "high_priority": self.repository.count_tasks(priority=Priority.HIGH),
            "urgent_priority": self.repository.count_tasks(priority=Priority.URGENT),
        }

    @staticmethod
    def format_jira_links(jira_issues: str | None, jira_url: str | None) -> list[str]:
        """Format JIRA issue keys into full URLs.

        Args:
            jira_issues: Comma-separated JIRA issue keys (e.g., "SRE-1234,DEVOPS-5678").
            jira_url: Base JIRA URL (e.g., "https://jira.company.com").

        Returns:
            List of tuples (issue_key, full_url) for each JIRA issue.
            Returns empty list if jira_issues is None/empty or jira_url is not configured.

        Examples:
            >>> TaskService.format_jira_links("SRE-1234,DEVOPS-5678", "https://jira.company.com")
            [("SRE-1234", "https://jira.company.com/browse/SRE-1234"),
             ("DEVOPS-5678", "https://jira.company.com/browse/DEVOPS-5678")]
        """
        if not jira_issues or not jira_url:
            return []

        jira_url = jira_url.rstrip("/")
        links = []

        for issue_key in jira_issues.split(","):
            issue_key = issue_key.strip()
            if issue_key:
                links.append((issue_key, f"{jira_url}/browse/{issue_key}"))

        return links

    def add_attachment(
        self,
        task_id: int,
        file_path: Path | str,
        mime_type: str | None = None,
    ) -> AttachmentMetadata:
        """Add a file attachment to a task.

        Args:
            task_id: The task ID
            file_path: Path to the file to attach
            mime_type: Optional MIME type

        Returns:
            Metadata for the added attachment

        Raises:
            ValueError: If task not found or file invalid
        """
        # Verify task exists
        task = self.get_task(task_id)

        # Add the file
        metadata = self.attachment_manager.add_attachment(task_id, Path(file_path), mime_type)

        # Update task's attachments metadata
        attachments = parse_attachments(task.attachments)
        attachments.append(metadata)
        task.attachments = serialize_attachments(attachments)
        task.mark_updated()

        self.repository.update(task)

        return metadata

    def add_attachment_from_content(
        self,
        task_id: int,
        filename: str,
        content: bytes | str,
    ) -> AttachmentMetadata:
        """Add a file attachment to a task from content (bytes or string).

        Enables programmatic attachment creation from generated content,
        stdin, or MCP payload.

        Args:
            task_id: The task ID
            filename: Attachment filename (e.g., 'TASK_60_PROMPT.md')
            content: Binary or string content

        Returns:
            Metadata for the added attachment

        Raises:
            ValueError: If task not found, filename invalid, or content empty
        """
        # Verify task exists
        task = self.get_task(task_id)

        # Normalize filename
        filename = Path(filename).name
        if not filename or not filename.strip():
            raise ValueError("Filename cannot be empty")

        # Convert content to bytes if string
        if isinstance(content, str):
            content = content.encode("utf-8")

        if not content:
            raise ValueError("Content cannot be empty")

        # Add the content via attachment manager
        metadata = self.attachment_manager.add_attachment_from_content(task_id, filename, content)

        # Update task's attachments metadata
        attachments = parse_attachments(task.attachments)
        attachments.append(metadata)
        task.attachments = serialize_attachments(attachments)
        task.mark_updated()

        self.repository.update(task)

        return metadata

    def remove_attachment(self, task_id: int, filename: str) -> bool:
        """Remove a file attachment from a task.

        Args:
            task_id: The task ID
            filename: The filename of the attachment to remove

        Returns:
            True if removed, False if not found

        Raises:
            ValueError: If task not found
        """
        # Verify task exists
        task = self.get_task(task_id)

        # Remove from filesystem
        removed = self.attachment_manager.remove_attachment(task_id, filename)

        if removed:
            # Update task's attachments metadata
            attachments = parse_attachments(task.attachments)
            attachments = [a for a in attachments if a["filename"] != filename]
            task.attachments = serialize_attachments(attachments)
            task.mark_updated()

            self.repository.update(task)

        return removed

    def list_attachments(self, task_id: int) -> list[AttachmentMetadata]:
        """List all attachments for a task.

        Args:
            task_id: The task ID

        Returns:
            List of attachment metadata

        Raises:
            ValueError: If task not found
        """
        task = self.get_task(task_id)
        return parse_attachments(task.attachments)

    def get_attachment_path(self, task_id: int, filename: str) -> Path:
        """Get the full path to an attachment file.

        Args:
            task_id: The task ID
            filename: The filename

        Returns:
            Full path to the attachment

        Raises:
            ValueError: If task not found or attachment not found
        """
        task = self.get_task(task_id)
        attachments = parse_attachments(task.attachments)

        # Verify attachment exists in metadata
        if not any(a["filename"] == filename for a in attachments):
            raise ValueError(f"Attachment '{filename}' not found for task #{task_id}")

        path = self.attachment_manager.get_attachment_path(task_id, filename)

        if not path.exists():
            raise ValueError(f"Attachment file not found: {path}")

        return path

    def get_attachment_content(self, task_id: int, filename: str) -> bytes | None:
        """Retrieve attachment file content.

        Args:
            task_id: ID of the task
            filename: Name of the attachment file (can be exact or partial match)

        Returns:
            File content as bytes, or None if not found

        Raises:
            ValueError: If task not found
        """
        # Verify task exists (raises ValueError if not found)
        self.get_task(task_id)

        # Get attachment directory
        task_dir = self.attachment_manager.get_task_dir(task_id)

        if not task_dir.exists():
            return None

        # Try exact filename first
        file_path = task_dir / filename
        if file_path.exists() and file_path.is_file():
            return file_path.read_bytes()

        # If not found, search by partial match (for stored filenames like 20260204_181256_ORIGINAL_NAME.md)
        for existing_file in task_dir.iterdir():
            if filename in existing_file.name or existing_file.name.endswith(filename):
                return existing_file.read_bytes()

        return None

    def add_db_attachment(self, task_id: int, original_filename: str, content: bytes) -> Attachment:
        """Add a file attachment to a task in the database.

        Args:
            task_id: The task ID
            original_filename: Original filename provided by user
            content: Binary file content

        Returns:
            Attachment: The created attachment record

        Raises:
            ValueError: If task not found or session not available
        """
        if not self.session:
            raise ValueError("Database session not available for attachment operations")

        # Verify task exists (for validation)
        self.get_task(task_id)

        # Generate storage filename with timestamp prefix
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        storage_filename = f"{timestamp}_{original_filename}"

        # Create attachment record
        attachment = Attachment(
            task_id=task_id,
            original_filename=original_filename,
            storage_filename=storage_filename,
            file_data=content,
            size_bytes=len(content),
        )

        self.session.add(attachment)
        self.session.commit()
        self.session.refresh(attachment)
        return attachment

    def get_attachment_by_filename(self, task_id: int, filename: str) -> Attachment | None:
        """Retrieve attachment using dual-filename matching with priority order.

        Matching priority:
        1. Exact match on original_filename
        2. Exact match on storage_filename
        3. Substring match on original_filename
        4. Substring match on storage_filename
        5. None if no match found

        Args:
            task_id: The task ID
            filename: Original or partial filename to match

        Returns:
            Attachment if found, None otherwise
        """
        if not self.session:
            return None

        # Verify task exists (for validation)
        self.get_task(task_id)

        # Query for attachments of this task
        query = self.session.query(Attachment).filter(Attachment.task_id == task_id)

        # Priority 1: Exact match on original_filename
        exact_match = query.filter(Attachment.original_filename == filename).first()
        if exact_match:
            return exact_match

        # Priority 2: Exact match on storage_filename
        exact_match = query.filter(Attachment.storage_filename == filename).first()
        if exact_match:
            return exact_match

        # Priority 3: Substring on original_filename
        substring_match = query.filter(Attachment.original_filename.ilike(f"%{filename}%")).first()
        if substring_match:
            return substring_match

        # Priority 4: Substring on storage_filename
        substring_match = query.filter(Attachment.storage_filename.ilike(f"%{filename}%")).first()
        if substring_match:
            return substring_match

        return None

    def list_db_attachments(self, task_id: int) -> list[Attachment]:
        """List all database-stored attachments for a task.

        Args:
            task_id: The task ID

        Returns:
            List of attachments

        Raises:
            ValueError: If task not found
        """
        if not self.session:
            return []

        # Verify task exists (for validation)
        self.get_task(task_id)

        attachments = (
            self.session.query(Attachment)
            .filter(Attachment.task_id == task_id)
            .order_by(Attachment.created_at.desc())
            .all()
        )

        return attachments

    def get_all_used_tags(self) -> list[str]:
        """Get all unique tags currently used across all tasks.

        Returns:
            list[str]: Sorted list of unique tags.
        """
        return self.repository.get_all_used_tags()

    def create_workspace(self, task_id: int, initialize_git: bool = True) -> WorkspaceMetadata:
        """Create a workspace for a task.

        Args:
            task_id: The task ID
            initialize_git: Whether to initialize a git repository

        Returns:
            Workspace metadata

        Raises:
            ValueError: If task not found or workspace already exists
        """
        # Verify task exists
        task = self.get_task(task_id)

        # Check if workspace already exists
        if task.workspace_path:
            raise ValueError(f"Workspace already exists for task #{task_id}")

        # Create workspace
        metadata = self.workspace_manager.create_workspace(
            task_id=task_id, initialize_git=initialize_git
        )

        # Update task with workspace path
        task.workspace_path = metadata["workspace_path"]
        task.mark_updated()
        self.repository.update(task)

        return metadata

    def get_workspace_info(self, task_id: int) -> WorkspaceMetadata | None:
        """Get workspace information for a task.

        Args:
            task_id: The task ID

        Returns:
            Workspace metadata if exists, None otherwise

        Raises:
            ValueError: If task not found
        """
        # Verify task exists
        task = self.get_task(task_id)

        if not task.workspace_path:
            return None

        return self.workspace_manager.get_workspace_metadata(task_id)

    def delete_workspace(self, task_id: int) -> bool:
        """Delete a task's workspace.

        Args:
            task_id: The task ID

        Returns:
            bool: True if workspace was deleted

        Raises:
            ValueError: If task not found
        """
        # Verify task exists
        task = self.get_task(task_id)

        if not task.workspace_path:
            return False

        # Delete workspace
        deleted = self.workspace_manager.delete_workspace(task_id)

        if deleted:
            # Update task to remove workspace path
            task.workspace_path = None
            task.mark_updated()
            self.repository.update(task)

        return deleted

    def get_workspace_path(self, task_id: int) -> Path | None:
        """Get the workspace path for a task.

        Args:
            task_id: The task ID

        Returns:
            Path to workspace if exists, None otherwise

        Raises:
            ValueError: If task not found
        """
        # Verify task exists
        task = self.get_task(task_id)

        if not task.workspace_path:
            return None

        return Path(task.workspace_path)

    def list_profiles(self) -> list[ProfileInfo]:
        """List all profile databases in config directory.

        Returns:
            list[ProfileInfo]: List of profiles with metadata
        """
        config_dir = self.config.get_config_dir()
        profiles = []

        # Find all tasks*.db files
        for db_file in config_dir.glob("tasks*.db"):
            # Extract profile name from filename
            # tasks.db -> "default"
            # tasks-dev.db -> "dev"
            # tasks-custom.db -> "custom"
            filename = db_file.stem
            if filename == "tasks":
                profile_name = "default"
            else:
                profile_name = filename.replace("tasks-", "")

            stat = db_file.stat()

            # Count tasks in this profile
            task_count = self._count_tasks_in_profile(profile_name)

            # Check if configured in settings
            configured = profile_name in self.config.profiles or profile_name in [
                "default",
                "dev",
                "test",
            ]

            profiles.append(
                ProfileInfo(
                    name=profile_name,
                    database_path=str(db_file),
                    exists=True,
                    size_bytes=stat.st_size,
                    task_count=task_count,
                    configured=configured,
                    last_modified=datetime.fromtimestamp(stat.st_mtime),
                    created=datetime.fromtimestamp(stat.st_ctime),
                )
            )

        return sorted(profiles, key=lambda p: p.name)

    def _count_tasks_in_profile(self, profile_name: str) -> int:
        """Count tasks in a specific profile.

        Args:
            profile_name: The profile name

        Returns:
            int: Number of tasks in the profile
        """
        from sqlalchemy.orm import Session

        from taskmanager.config import Settings
        from taskmanager.database import get_engine
        from taskmanager.models import Task

        # Create a temporary settings object for this profile
        settings = Settings()
        settings.profile = profile_name

        try:
            db_url = settings.get_database_url()
            engine = get_engine(db_url)

            with Session(engine) as session:
                count = session.query(Task).count()
                return count
        except Exception:
            # If there's an error, return 0
            return 0

    def audit_profile(self, profile_name: str) -> ProfileAudit:
        """Audit a profile before deletion.

        Args:
            profile_name: The profile name to audit

        Returns:
            ProfileAudit: Audit information

        Raises:
            ValueError: If profile doesn't exist
        """
        from sqlalchemy.orm import Session

        from taskmanager.config import Settings
        from taskmanager.database import get_engine
        from taskmanager.models import Task

        config_dir = self.config.get_config_dir()

        # Find the database file
        db_filename = "tasks.db" if profile_name == "default" else f"tasks-{profile_name}.db"
        db_path = config_dir / db_filename

        if not db_path.exists():
            raise ValueError(f"Profile '{profile_name}' database not found at {db_path}")

        stat = db_path.stat()

        # Count tasks
        task_count = self._count_tasks_in_profile(profile_name)

        # Check if configured
        configured = profile_name in self.config.profiles or profile_name in [
            "default",
            "dev",
            "test",
        ]

        # Get oldest and newest tasks
        oldest_task = None
        newest_task = None

        try:
            temp_settings = Settings()
            temp_settings.profile = profile_name

            db_url = temp_settings.get_database_url()
            engine = get_engine(db_url)

            with Session(engine) as session:
                tasks = session.query(Task).all()
                if tasks:
                    # Sort by ID to get oldest and newest
                    sorted_tasks = sorted(tasks, key=lambda t: t.id)
                    oldest_task = sorted_tasks[0]
                    newest_task = sorted_tasks[-1]
        except Exception:
            # If we can't get tasks, just skip
            pass

        return ProfileAudit(
            name=profile_name,
            location=str(db_path),
            size_bytes=stat.st_size,
            task_count=task_count,
            configured=configured,
            last_modified=datetime.fromtimestamp(stat.st_mtime),
            oldest_task=oldest_task,
            newest_task=newest_task,
        )

    def delete_profile(self, profile_name: str) -> None:
        """Delete a profile database and remove from settings.toml if configured.

        Args:
            profile_name: The profile name to delete

        Raises:
            ValueError: If trying to delete a built-in profile or profile not found
        """
        from taskmanager.config import get_user_config_path

        # Prevent deletion of built-in profiles
        if profile_name in ["default", "dev", "test"]:
            raise ValueError(f"Cannot delete built-in profile '{profile_name}'")

        config_dir = self.config.get_config_dir()

        # Find and delete the database file
        db_filename = f"tasks-{profile_name}.db"
        db_path = config_dir / db_filename

        if db_path.exists():
            db_path.unlink()

        # Remove from settings.toml if configured
        config_path = get_user_config_path()
        if config_path.exists():
            try:
                # Read current config
                with open(config_path, "rb") as f:
                    config = tomllib.load(f)

                # Remove profile if it exists
                if "profiles" in config and profile_name in config["profiles"]:
                    del config["profiles"][profile_name]

                    # Write back
                    with open(config_path, "wb") as f:
                        tomli_w.dump(config, f)
            except Exception as e:
                # Log the error but don't fail the deletion
                print(f"Warning: Could not remove profile from settings.toml: {e}")

    def construct_full_prompt(
        self, user_query: str | None = None, task_id: int | None = None
    ) -> str:
        """Construct the full system prompt and context that would be sent to the LLM.

        This function creates the exact prompt that would be used during a tasks chat session,
        including system instructions, current context, and any user query.

        Args:
            user_query: Optional user query to include in the prompt
            task_id: Optional task ID to focus the context on

        Returns:
            str: The complete formatted prompt string
        """
        from datetime import date
        from zoneinfo import ZoneInfo

        settings = self.config

        # Get current time in user's local timezone
        tz = ZoneInfo(settings.timezone)
        now = datetime.now(tz)
        current_time_str = now.strftime("%A, %B %d, %Y at %I:%M %p %Z")

        # Gather task statistics
        all_tasks, _ = self.list_tasks(limit=100)  # Get up to 100 tasks for overview
        in_progress = [t for t in all_tasks if t.status == TaskStatus.IN_PROGRESS]
        overdue = [
            t
            for t in all_tasks
            if t.due_date
            and t.due_date < date.today()
            and t.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]
        ]
        high_priority = [
            t
            for t in all_tasks
            if t.priority == Priority.HIGH
            and t.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]
        ]
        urgent_priority = [
            t
            for t in all_tasks
            if t.priority == Priority.URGENT
            and t.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]
        ]

        # Build structured context
        context_parts = []
        context_parts.append("# Initial Task Context\n")
        context_parts.append(f"**Current Time:** {current_time_str}")
        context_parts.append(f"**Today's Date:** {now.strftime('%Y-%m-%d')}")
        context_parts.append(f"**Day of Week:** {now.strftime('%A')}")
        context_parts.append(f"**Timezone:** {settings.timezone}")
        context_parts.append(f"**Weekend:** {'Yes' if now.weekday() >= 5 else 'No'}\n")
        context_parts.append(f"**Profile:** {settings.profile}")
        context_parts.append(f"**Total tasks:** {len(all_tasks)}\n")

        if urgent_priority:
            context_parts.append(f"## 🚨 Urgent Tasks ({len(urgent_priority)})")
            for task in urgent_priority[:5]:  # Show up to 5
                context_parts.append(f"- **#{task.id}** {task.title} [{task.status.value}]")
            if len(urgent_priority) > 5:
                context_parts.append(f"  _(and {len(urgent_priority) - 5} more)_")
            context_parts.append("")

        if overdue:
            context_parts.append(f"## ⏰ Overdue Tasks ({len(overdue)})")
            for task in overdue[:5]:
                context_parts.append(
                    f"- **#{task.id}** {task.title} (due {task.due_date}) [{task.status.value}]"
                )
            if len(overdue) > 5:
                context_parts.append(f"  _(and {len(overdue) - 5} more)_")
            context_parts.append("")

        if in_progress:
            context_parts.append(f"## ▶️ In Progress ({len(in_progress)})")
            for task in in_progress[:5]:
                jira_info = f" - JIRA: {task.jira_issues}" if task.jira_issues else ""
                context_parts.append(
                    f"- **#{task.id}** {task.title} [{task.priority.value}]{jira_info}"
                )
            if len(in_progress) > 5:
                context_parts.append(f"  _(and {len(in_progress) - 5} more)_")
            context_parts.append("")

        if high_priority and not urgent_priority:
            context_parts.append(f"## ⚠️ High Priority Tasks ({len(high_priority)})")
            for task in high_priority[:3]:
                context_parts.append(f"- **#{task.id}** {task.title} [{task.status.value}]")
            if len(high_priority) > 3:
                context_parts.append(f"  _(and {len(high_priority) - 3} more)_")
            context_parts.append("")

        context_parts.append(
            "\n**I'm ready to help you with your tasks. What would you like to work on?**"
        )

        context_prompt = "\n".join(context_parts)

        # Build comprehensive system prompt
        system_prompt = """# Mission: Smart Assistant for Task & JIRA Management

You are a specialized AI assistant with expertise in task management and JIRA/Confluence operations. Your primary mission is to help users efficiently manage their work using two MCP servers:

## Available MCP Tools

### 1. tasks-mcp Server
The tasks-mcp server provides comprehensive task management capabilities:

**Core Operations:**
- `mcp_tasks-mcp_list_tasks` - List tasks with filtering (status, priority, tag, overdue)
- `mcp_tasks-mcp_get_task` - Get detailed information about a specific task
- `mcp_tasks-mcp_create_task` - Create new tasks (use interactive version for guided creation)
- `mcp_tasks-mcp_update_task` - Update task fields (title, description, priority, status, due date, tags, JIRA issues)
- `mcp_tasks-mcp_complete_task` - Mark a task as completed
- `mcp_tasks-mcp_delete_task` - Delete a task (use interactive version for confirmation)

**Workspace Operations:**
- `mcp_tasks-mcp_create_workspace` - Create persistent workspace directory structure for a task
- `mcp_tasks-mcp_get_workspace_info` - Get workspace metadata and path information
- `mcp_tasks-mcp_get_workspace_path` - Get absolute filesystem path to a task's workspace
- `mcp_tasks-mcp_list_workspace_files` - Browse workspace directory contents
- `mcp_tasks-mcp_search_workspace` - Search for content within a task's workspace files
- `mcp_tasks-mcp_delete_workspace` - Delete a task's workspace (destructive)

**Search & Discovery:**
- `mcp_tasks-mcp_search_all_tasks` - Comprehensive search across task metadata and workspace content

**Time Awareness:**
- `mcp_tasks-mcp_get_current_time` - Get current timestamp with timezone info (ISO 8601, unix timestamp, day of week, weekend detection)
- `mcp_tasks-mcp_format_datetime` - Format and convert datetime strings with timezone support
- `mcp_tasks-mcp_calculate_time_delta` - Calculate time differences for deadline tracking and scheduling

**Best Practices for tasks-mcp:**
- Use interactive versions (`create_task_interactive`, `update_task_interactive`, `delete_task_interactive`) when you need guidance or confirmation
- Always ensure workspace exists before working with task files
- Tasks can have JIRA issues linked via comma-separated keys (e.g., "SRE-1234,DEVOPS-5678")
- Workspaces provide organized structure: notes/, code/, logs/, tmp/
- Use time-awareness tools for accurate schedule operations, deadline calculations, and time-sensitive workflows
- All timezone operations support IANA timezone names (UTC, America/New_York, Europe/London, etc.)

### 2. atlassian-mcp Server
The atlassian-mcp server provides JIRA and Confluence integration (when credentials are configured):

**JIRA Operations:**
- Search and retrieve JIRA issues
- View issue details, comments, and attachments
- Create and update issues
- Manage issue transitions (workflow states)

**Confluence Operations:**
- Search and retrieve Confluence pages
- View page content and metadata
- Create and update pages

**Best Practices for atlassian-mcp:**
- JIRA issue keys follow pattern: PROJECT-NUMBER (e.g., SRE-1234)
- Link JIRA issues to tasks using the jira_issues field
- Search before creating to avoid duplicates

## Initial Context Gathering

When starting a new session, please:

1. **Be aware of current time:**
   - The current date and time are provided in the initial context
   - Use this for deadline discussions and deadline-aware operations
   - Check for overdue tasks by comparing due dates to today's date

2. **Understand the current profile context:**
   - List recent tasks to understand what's in flight
   - Identify high-priority or urgent items
   - Check if there are related JIRA issues

3. **Assess the work environment:**
   - Note which tasks are in progress vs pending
   - Look for high-priority items
   - Check if there are related JIRA issues

4. **Ask clarifying questions:**
   - What would you like to focus on today?
   - Should we review existing tasks or start something new?
   - Are there specific JIRA issues you're working on?

## Operational Guidelines

- **Safety First:** Always confirm before destructive operations (delete, major updates)
- **Context Aware:** Consider task status, priority, and deadlines when making suggestions
- **Time Aware:** Use current time tools to provide accurate schedule information and deadline calculations. Always check current time when discussing due dates or time-sensitive tasks.
- **Proactive:** Suggest related JIRA issues or tasks that might be relevant
- **Organized:** Use workspace features to keep notes, code, and logs structured
- **Efficient:** Batch similar operations when appropriate
- **Transparent:** Explain what you're doing and why, especially for complex operations

## Communication Standards

- **Always Use Numeric Task IDs:** When referring to tasks in your responses, ALWAYS include the numeric task ID (e.g., "task #27" or "#27") even when using natural language descriptions. Never refer to tasks by title alone.
  - ✅ GOOD: "I've updated task #27 (Context initialization defect)"
  - ✅ GOOD: "Let's work on #27"
  - ❌ BAD: "I've updated the context initialization defect task"
  - ❌ BAD: "Let's work on that task"
- **JIRA References:** Similarly, always include JIRA issue keys when discussing JIRA items (e.g., "SRE-1234")
- **Clarity:** This ensures precise communication and avoids ambiguity when discussing multiple tasks

"""

        # Add current task context if provided
        if task_id:
            task = self.get_task(task_id)
            workspace_path = self.get_workspace_path(task_id)
            system_prompt += "\n## Current Task Focus\n\n"
            system_prompt += "You are currently working in the context of:\n\n"
            system_prompt += f"- **Task ID:** #{task.id}\n"
            system_prompt += f"- **Title:** {task.title}\n"
            system_prompt += f"- **Status:** {task.status.value}\n"
            system_prompt += f"- **Priority:** {task.priority.value}\n"
            if task.description:
                system_prompt += f"- **Description:** {task.description}\n"
            if task.due_date:
                system_prompt += f"- **Due Date:** {task.due_date}\n"
            if task.jira_issues:
                system_prompt += f"- **Related JIRA Issues:** {task.jira_issues}\n"
            if task.tags:
                system_prompt += f"- **Tags:** {', '.join(task.tags)}\n"
            if workspace_path:
                system_prompt += f"- **Workspace:** {workspace_path}\n"
            system_prompt += "\nPlease help the user work on this task efficiently.\n"

        # Add profile-specific prompt additions if configured
        profile_modifier = settings.get_profile_modifier()
        if profile_modifier and profile_modifier.prompt_additions:
            system_prompt += (
                f"\n## Profile-Specific Instructions\n\n{profile_modifier.prompt_additions}\n"
            )

        # Combine system prompt and context
        full_prompt = f"{system_prompt}\n\n{context_prompt}"

        # Add user query if provided
        if user_query:
            full_prompt += f"\n\n# User Query\n\n{user_query}"

        return full_prompt
