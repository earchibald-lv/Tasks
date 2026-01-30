"""Business logic layer for task management.

This module provides the service layer that sits between the interface
layer (CLI, MCP) and the repository layer, implementing core business
logic and validation rules.
"""

from datetime import date

from taskmanager.models import Priority, Task, TaskStatus
from taskmanager.repository import TaskRepository


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
