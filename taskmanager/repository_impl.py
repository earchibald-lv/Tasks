"""SQLite implementation of the TaskRepository.

This module provides the concrete implementation of the TaskRepository
protocol using SQLModel and SQLite for data persistence.
"""

from datetime import date

from sqlmodel import Session, select

from taskmanager.models import Priority, Task, TaskStatus


class SQLTaskRepository:
    """SQLite implementation of the TaskRepository protocol.

    This repository handles all database operations for tasks using
    SQLModel and SQLite as the storage backend.
    """

    def __init__(self, session: Session) -> None:
        """Initialize the repository with a database session.

        Args:
            session: SQLModel Session for database operations.
        """
        self.session = session

    def create(self, task: Task) -> Task:
        """Create a new task in the database.

        Args:
            task: Task object to create (id should be None).

        Returns:
            Task: The created task with assigned id.

        Raises:
            ValueError: If task.id is not None or task data is invalid.
        """
        if task.id is not None:
            raise ValueError("Cannot create task with existing id")

        if not task.title or not task.title.strip():
            raise ValueError("Task title cannot be empty")

        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)
        return task

    def get_by_id(self, task_id: int) -> Task | None:
        """Retrieve a task by its ID.

        Args:
            task_id: The unique identifier of the task.

        Returns:
            Optional[Task]: The task if found, None otherwise.
        """
        return self.session.get(Task, task_id)

    def list_tasks(
        self,
        status: TaskStatus | None = None,
        priority: Priority | None = None,
        due_before: date | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Task]:
        """List tasks with optional filtering and pagination.

        Args:
            status: Filter by task status (optional).
            priority: Filter by priority level (optional).
            due_before: Filter tasks due before this date (optional).
            limit: Maximum number of tasks to return (default: 20).
            offset: Number of tasks to skip for pagination (default: 0).

        Returns:
            list[Task]: List of tasks matching the criteria.
        """
        statement = select(Task)

        # Apply filters
        if status is not None:
            statement = statement.where(Task.status == status)

        if priority is not None:
            statement = statement.where(Task.priority == priority)

        if due_before is not None:
            statement = statement.where(
                Task.due_date.isnot(None), Task.due_date <= due_before  # type: ignore
            )

        # Apply ordering (most recent first)
        statement = statement.order_by(Task.created_at.desc())  # type: ignore[attr-defined]

        # Apply pagination
        statement = statement.limit(limit).offset(offset)

        results = self.session.exec(statement)
        return list(results.all())

    def count_tasks(
        self,
        status: TaskStatus | None = None,
        priority: Priority | None = None,
        due_before: date | None = None,
    ) -> int:
        """Count tasks matching the given criteria.

        Args:
            status: Filter by task status (optional).
            priority: Filter by priority level (optional).
            due_before: Filter tasks due before this date (optional).

        Returns:
            int: Number of tasks matching the criteria.
        """
        statement = select(Task)

        # Apply filters
        if status is not None:
            statement = statement.where(Task.status == status)

        if priority is not None:
            statement = statement.where(Task.priority == priority)

        if due_before is not None:
            statement = statement.where(
                Task.due_date.isnot(None), Task.due_date <= due_before  # type: ignore
            )

        results = self.session.exec(statement)
        return len(list(results.all()))

    def update(self, task: Task) -> Task:
        """Update an existing task.

        Args:
            task: Task object with updated fields.

        Returns:
            Task: The updated task.

        Raises:
            ValueError: If task doesn't exist or task.id is None.
        """
        if task.id is None:
            raise ValueError("Cannot update task without id")

        existing = self.get_by_id(task.id)
        if existing is None:
            raise ValueError(f"Task with id {task.id} not found")

        if not task.title or not task.title.strip():
            raise ValueError("Task title cannot be empty")

        # Update the timestamp
        task.mark_updated()

        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)
        return task

    def delete(self, task_id: int) -> bool:
        """Delete a task by ID.

        Args:
            task_id: The unique identifier of the task to delete.

        Returns:
            bool: True if task was deleted, False if task wasn't found.
        """
        task = self.get_by_id(task_id)
        if task is None:
            return False

        self.session.delete(task)
        self.session.commit()
        return True
