"""Repository protocol for data access abstraction.

This module defines the repository interface (Protocol) that abstracts
data access operations, enabling testability and future flexibility.
"""

from datetime import date
from typing import Protocol

from taskmanager.models import Priority, Task, TaskStatus


class TaskRepository(Protocol):
    """Protocol defining the interface for task data access.

    This protocol enables dependency injection and allows for multiple
    implementations (e.g., SQLite, PostgreSQL, in-memory for testing).
    """

    def create(self, task: Task) -> Task:
        """Create a new task in the repository.

        Args:
            task: Task object to create (id should be None).

        Returns:
            Task: The created task with assigned id.

        Raises:
            ValueError: If task.id is not None or task data is invalid.
        """
        ...

    def get_by_id(self, task_id: int) -> Task | None:
        """Retrieve a task by its ID.

        Args:
            task_id: The unique identifier of the task.

        Returns:
            Optional[Task]: The task if found, None otherwise.
        """
        ...

    def list_tasks(
        self,
        status: TaskStatus | None = None,
        priority: Priority | None = None,
        due_before: date | None = None,
        tag: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Task]:
        """List tasks with optional filtering and pagination.

        Args:
            status: Filter by task status (optional).
            priority: Filter by priority level (optional).
            due_before: Filter tasks due before this date (optional).
            tag: Filter by tag (partial match, optional).
            limit: Maximum number of tasks to return (default: 20).
            offset: Number of tasks to skip for pagination (default: 0).

        Returns:
            list[Task]: List of tasks matching the criteria.
        """
        ...

    def count_tasks(
        self,
        status: TaskStatus | None = None,
        priority: Priority | None = None,
        due_before: date | None = None,
        tag: str | None = None,
    ) -> int:
        """Count tasks matching the given criteria.

        Args:
            status: Filter by task status (optional).
            priority: Filter by priority level (optional).
            due_before: Filter tasks due before this date (optional).
            tag: Filter by tag (partial match, optional).

        Returns:
            int: Number of tasks matching the criteria.
        """
        ...

    def update(self, task: Task) -> Task:
        """Update an existing task.

        Args:
            task: Task object with updated fields.

        Returns:
            Task: The updated task.

        Raises:
            ValueError: If task doesn't exist or task.id is None.
        """
        ...

    def delete(self, task_id: int) -> bool:
        """Delete a task by ID.

        Args:
            task_id: The unique identifier of the task to delete.

        Returns:
            bool: True if task was deleted, False if task wasn't found.
        """
        ...

    def get_all_used_tags(self) -> list[str]:
        """Get all unique tags currently used across all tasks.

        Returns:
            list[str]: Sorted list of unique tags.
        """
        ...
