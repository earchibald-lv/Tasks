"""Business logic layer for task management.

This module provides the service layer that sits between the interface
layer (CLI, MCP) and the repository layer, implementing core business
logic and validation rules.
"""

from datetime import date
from pathlib import Path

from taskmanager.attachments import (
    AttachmentManager,
    AttachmentMetadata,
    parse_attachments,
    serialize_attachments,
)
from taskmanager.models import Priority, Task, TaskStatus
from taskmanager.repository import TaskRepository
from taskmanager.workspace import WorkspaceManager, WorkspaceMetadata


class TaskService:
    """Service layer for task management business logic.

    This class encapsulates all business logic for task operations,
    ensuring consistency across CLI and MCP server interfaces.
    """

    def __init__(self, repository: TaskRepository) -> None:
        """Initialize the task service.

        Args:
            repository: TaskRepository implementation for data access.
        """
        self.repository = repository
        self.attachment_manager = AttachmentManager()
        self.workspace_manager = WorkspaceManager()

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

        return self.repository.create(task)

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
                raise ValueError(
                    "Cannot reopen completed task. Use in_progress status first."
                )
            task.status = status

        if jira_issues is not None:
            task.jira_issues = jira_issues.strip() or None

        if tags is not None:
            task.tags = tags.strip() or None

        return self.repository.update(task)

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
        metadata = self.attachment_manager.add_attachment(
            task_id, Path(file_path), mime_type
        )

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
            content = content.encode('utf-8')

        if not content:
            raise ValueError("Content cannot be empty")

        # Add the content via attachment manager
        metadata = self.attachment_manager.add_attachment_from_content(
            task_id, filename, content
        )

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
        # Verify task exists
        task = self.get_task(task_id)

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

    def get_all_used_tags(self) -> list[str]:
        """Get all unique tags currently used across all tasks.

        Returns:
            list[str]: Sorted list of unique tags.
        """
        return self.repository.get_all_used_tags()

    def create_workspace(
        self,
        task_id: int,
        initialize_git: bool = True
    ) -> WorkspaceMetadata:
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
            task_id=task_id,
            initialize_git=initialize_git
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
