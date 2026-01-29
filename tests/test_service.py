"""Tests for the task service layer."""

from datetime import date, timedelta

import pytest
from sqlmodel import Session, SQLModel, create_engine

from taskmanager.models import Priority, TaskStatus
from taskmanager.repository_impl import SQLTaskRepository
from taskmanager.service import TaskService


@pytest.fixture
def engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """Create a new database session for each test."""
    with Session(engine) as session:
        yield session


@pytest.fixture
def repository(session):
    """Create a repository instance for testing."""
    return SQLTaskRepository(session)


@pytest.fixture
def service(repository):
    """Create a service instance for testing."""
    return TaskService(repository)


class TestTaskServiceCreate:
    """Tests for task creation."""

    def test_create_task_minimal(self, service):
        """Test creating a task with minimal required fields."""
        task = service.create_task(title="Test Task")

        assert task.id is not None
        assert task.title == "Test Task"
        assert task.description is None
        assert task.status == TaskStatus.PENDING
        assert task.priority == Priority.MEDIUM
        assert task.due_date is None

    def test_create_task_full(self, service):
        """Test creating a task with all fields."""
        due_date = date.today() + timedelta(days=7)

        task = service.create_task(
            title="Complete Task",
            description="Detailed description",
            priority=Priority.HIGH,
            due_date=due_date,
            status=TaskStatus.IN_PROGRESS,
        )

        assert task.title == "Complete Task"
        assert task.description == "Detailed description"
        assert task.priority == Priority.HIGH
        assert task.due_date == due_date
        assert task.status == TaskStatus.IN_PROGRESS

    def test_create_task_strips_whitespace(self, service):
        """Test that title and description are stripped."""
        task = service.create_task(
            title="  Test Task  ",
            description="  Description  ",
        )

        assert task.title == "Test Task"
        assert task.description == "Description"

    def test_create_task_empty_description_becomes_none(self, service):
        """Test that empty description is stored as None."""
        task = service.create_task(title="Test", description="   ")

        assert task.description is None

    def test_create_task_empty_title_raises_error(self, service):
        """Test that empty title raises ValueError."""
        with pytest.raises(ValueError, match="Task title cannot be empty"):
            service.create_task(title="")

        with pytest.raises(ValueError, match="Task title cannot be empty"):
            service.create_task(title="   ")

    def test_create_task_title_too_long_raises_error(self, service):
        """Test that title over 200 characters raises ValueError."""
        long_title = "x" * 201

        with pytest.raises(ValueError, match="cannot exceed 200 characters"):
            service.create_task(title=long_title)

    def test_create_task_with_past_due_date_allowed(self, service):
        """Test that creating task with past due date is allowed for testing overdue scenarios."""
        past_date = date.today() - timedelta(days=1)

        task = service.create_task(title="Past task", due_date=past_date)
        assert task.due_date == past_date


class TestTaskServiceGet:
    """Tests for retrieving tasks."""

    def test_get_task(self, service):
        """Test retrieving a task by ID."""
        created = service.create_task(title="Test Task")

        retrieved = service.get_task(created.id)

        assert retrieved.id == created.id
        assert retrieved.title == "Test Task"

    def test_get_task_not_found_raises_error(self, service):
        """Test that getting nonexistent task raises ValueError."""
        with pytest.raises(ValueError, match="Task with ID 999 not found"):
            service.get_task(999)

    def test_get_task_invalid_id_raises_error(self, service):
        """Test that invalid task ID raises ValueError."""
        with pytest.raises(ValueError, match="Task ID must be positive"):
            service.get_task(0)

        with pytest.raises(ValueError, match="Task ID must be positive"):
            service.get_task(-1)


class TestTaskServiceList:
    """Tests for listing tasks."""

    def test_list_tasks_empty(self, service):
        """Test listing tasks when none exist."""
        tasks, total = service.list_tasks()

        assert tasks == []
        assert total == 0

    def test_list_tasks(self, service):
        """Test listing all tasks."""
        service.create_task(title="Task 1")
        service.create_task(title="Task 2")
        service.create_task(title="Task 3")

        tasks, total = service.list_tasks()

        assert len(tasks) == 3
        assert total == 3

    def test_list_tasks_with_status_filter(self, service):
        """Test filtering by status."""
        service.create_task(title="Pending", status=TaskStatus.PENDING)
        service.create_task(title="Completed", status=TaskStatus.COMPLETED)

        tasks, total = service.list_tasks(status=TaskStatus.PENDING)

        assert len(tasks) == 1
        assert total == 1
        assert tasks[0].title == "Pending"

    def test_list_tasks_with_priority_filter(self, service):
        """Test filtering by priority."""
        service.create_task(title="Low", priority=Priority.LOW)
        service.create_task(title="High", priority=Priority.HIGH)

        tasks, total = service.list_tasks(priority=Priority.HIGH)

        assert len(tasks) == 1
        assert total == 1
        assert tasks[0].title == "High"

    def test_list_tasks_with_pagination(self, service):
        """Test pagination."""
        for i in range(25):
            service.create_task(title=f"Task {i}")

        # First page
        page1, total = service.list_tasks(limit=10, offset=0)
        assert len(page1) == 10
        assert total == 25

        # Second page
        page2, total = service.list_tasks(limit=10, offset=10)
        assert len(page2) == 10
        assert total == 25

    def test_list_tasks_invalid_limit_raises_error(self, service):
        """Test that invalid limit raises ValueError."""
        with pytest.raises(ValueError, match="Limit must be between 1 and 100"):
            service.list_tasks(limit=0)

        with pytest.raises(ValueError, match="Limit must be between 1 and 100"):
            service.list_tasks(limit=101)

    def test_list_tasks_invalid_offset_raises_error(self, service):
        """Test that negative offset raises ValueError."""
        with pytest.raises(ValueError, match="Offset must be non-negative"):
            service.list_tasks(offset=-1)


class TestTaskServiceUpdate:
    """Tests for updating tasks."""

    def test_update_task_title(self, service):
        """Test updating task title."""
        task = service.create_task(title="Original")

        updated = service.update_task(task.id, title="Updated")

        assert updated.title == "Updated"
        assert updated.updated_at is not None

    def test_update_task_description(self, service):
        """Test updating task description."""
        task = service.create_task(title="Test")

        updated = service.update_task(task.id, description="New description")

        assert updated.description == "New description"

    def test_update_task_clear_description(self, service):
        """Test clearing task description."""
        task = service.create_task(title="Test", description="Old")

        updated = service.update_task(task.id, description="   ")

        assert updated.description is None

    def test_update_task_priority(self, service):
        """Test updating task priority."""
        task = service.create_task(title="Test")

        updated = service.update_task(task.id, priority=Priority.URGENT)

        assert updated.priority == Priority.URGENT

    def test_update_task_due_date(self, service):
        """Test updating task due date."""
        task = service.create_task(title="Test")
        future_date = date.today() + timedelta(days=7)

        updated = service.update_task(task.id, due_date=future_date)

        assert updated.due_date == future_date

    def test_update_task_status(self, service):
        """Test updating task status."""
        task = service.create_task(title="Test")

        updated = service.update_task(task.id, status=TaskStatus.IN_PROGRESS)

        assert updated.status == TaskStatus.IN_PROGRESS

    def test_update_task_not_found_raises_error(self, service):
        """Test updating nonexistent task raises ValueError."""
        with pytest.raises(ValueError, match="Task with ID 999 not found"):
            service.update_task(999, title="Test")

    def test_update_task_empty_title_raises_error(self, service):
        """Test that empty title raises ValueError."""
        task = service.create_task(title="Test")

        with pytest.raises(ValueError, match="Task title cannot be empty"):
            service.update_task(task.id, title="")

    def test_update_task_past_due_date_raises_error(self, service):
        """Test that past due date raises ValueError."""
        task = service.create_task(title="Test")
        past_date = date.today() - timedelta(days=1)

        with pytest.raises(ValueError, match="Due date cannot be in the past"):
            service.update_task(task.id, due_date=past_date)

    def test_update_task_cannot_reopen_completed(self, service):
        """Test that completed tasks cannot be reopened directly to pending."""
        task = service.create_task(title="Test")
        service.update_task(task.id, status=TaskStatus.COMPLETED)

        with pytest.raises(ValueError, match="Cannot reopen completed task"):
            service.update_task(task.id, status=TaskStatus.PENDING)


class TestTaskServiceMarkComplete:
    """Tests for marking tasks as complete."""

    def test_mark_complete(self, service):
        """Test marking a task as complete."""
        task = service.create_task(title="Test")

        completed = service.mark_complete(task.id)

        assert completed.status == TaskStatus.COMPLETED
        assert completed.updated_at is not None

    def test_mark_complete_archived_task_raises_error(self, service):
        """Test that archived tasks cannot be completed."""
        task = service.create_task(title="Test")
        service.update_task(task.id, status=TaskStatus.ARCHIVED)

        with pytest.raises(ValueError, match="Cannot complete archived task"):
            service.mark_complete(task.id)

    def test_mark_complete_not_found_raises_error(self, service):
        """Test marking nonexistent task complete raises ValueError."""
        with pytest.raises(ValueError, match="Task with ID 999 not found"):
            service.mark_complete(999)


class TestTaskServiceDelete:
    """Tests for deleting tasks."""

    def test_delete_task(self, service):
        """Test deleting a task."""
        task = service.create_task(title="Test")

        result = service.delete_task(task.id)

        assert result is True

        # Verify task is deleted
        with pytest.raises(ValueError, match="not found"):
            service.get_task(task.id)

    def test_delete_task_not_found_raises_error(self, service):
        """Test deleting nonexistent task raises ValueError."""
        with pytest.raises(ValueError, match="Task with ID 999 not found"):
            service.delete_task(999)

    def test_delete_task_invalid_id_raises_error(self, service):
        """Test that invalid task ID raises ValueError."""
        with pytest.raises(ValueError, match="Task ID must be positive"):
            service.delete_task(0)


class TestTaskServiceOverdue:
    """Tests for overdue task retrieval."""

    def test_get_overdue_tasks_empty(self, service):
        """Test getting overdue tasks when none exist."""
        overdue = service.get_overdue_tasks()

        assert overdue == []

    def test_get_overdue_tasks(self, service):
        """Test getting overdue tasks."""
        yesterday = date.today() - timedelta(days=1)
        tomorrow = date.today() + timedelta(days=1)

        # Create overdue pending task
        service.create_task(title="Overdue Pending", due_date=yesterday)

        # Create overdue in-progress task
        service.create_task(
            title="Overdue In Progress",
            due_date=yesterday,
            status=TaskStatus.IN_PROGRESS,
        )

        # Create future task (not overdue)
        service.create_task(title="Future", due_date=tomorrow)

        # Create completed overdue task (should not appear)
        service.create_task(
            title="Completed Overdue",
            due_date=yesterday,
            status=TaskStatus.COMPLETED,
        )

        overdue = service.get_overdue_tasks()

        assert len(overdue) == 2
        titles = {task.title for task in overdue}
        assert "Overdue Pending" in titles
        assert "Overdue In Progress" in titles


class TestTaskServiceStatistics:
    """Tests for task statistics."""

    def test_get_statistics_empty(self, service):
        """Test statistics when no tasks exist."""
        stats = service.get_statistics()

        assert stats["total"] == 0
        assert stats["pending"] == 0
        assert stats["completed"] == 0

    def test_get_statistics(self, service):
        """Test statistics with various tasks."""
        service.create_task(title="Pending 1", status=TaskStatus.PENDING)
        service.create_task(title="Pending 2", status=TaskStatus.PENDING)
        service.create_task(title="Completed", status=TaskStatus.COMPLETED)
        service.create_task(title="High", priority=Priority.HIGH)
        service.create_task(title="Urgent", priority=Priority.URGENT)

        stats = service.get_statistics()

        assert stats["total"] == 5
        assert stats["pending"] == 4  # 2 explicit + 2 default (High and Urgent)
        assert stats["completed"] == 1
        assert stats["high_priority"] == 1
        assert stats["urgent_priority"] == 1
        assert stats["medium_priority"] == 3  # Default priority
