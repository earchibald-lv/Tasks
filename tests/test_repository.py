"""Tests for repository implementation."""

from datetime import date

import pytest
from sqlmodel import Session, SQLModel, create_engine

from taskmanager.models import Priority, Task, TaskStatus
from taskmanager.repository_impl import SQLTaskRepository


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


class TestSQLTaskRepository:
    """Tests for SQLTaskRepository implementation."""

    def test_create_task(self, repository):
        """Test creating a new task."""
        task = Task(title="Test Task", description="Test description")
        created = repository.create(task)

        assert created.id is not None
        assert created.title == "Test Task"
        assert created.description == "Test description"
        assert created.status == TaskStatus.PENDING
        assert created.priority == Priority.MEDIUM

    def test_create_task_with_id_raises_error(self, repository):
        """Test that creating a task with existing id raises error."""
        task = Task(id=1, title="Test Task")

        with pytest.raises(ValueError, match="Cannot create task with existing id"):
            repository.create(task)

    def test_create_task_with_empty_title_raises_error(self, repository):
        """Test that creating a task with empty title raises error."""
        task = Task(title="")

        with pytest.raises(ValueError, match="Task title cannot be empty"):
            repository.create(task)

        task = Task(title="   ")

        with pytest.raises(ValueError, match="Task title cannot be empty"):
            repository.create(task)

    def test_get_by_id(self, repository):
        """Test retrieving a task by ID."""
        task = Task(title="Test Task")
        created = repository.create(task)

        retrieved = repository.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.title == "Test Task"

    def test_get_by_id_nonexistent(self, repository):
        """Test retrieving a nonexistent task returns None."""
        retrieved = repository.get_by_id(999)
        assert retrieved is None

    def test_list_tasks_empty(self, repository):
        """Test listing tasks when repository is empty."""
        tasks = repository.list_tasks()
        assert tasks == []

    def test_list_tasks(self, repository):
        """Test listing all tasks."""
        repository.create(Task(title="Task 1"))
        repository.create(Task(title="Task 2"))
        repository.create(Task(title="Task 3"))

        tasks = repository.list_tasks()

        assert len(tasks) == 3
        assert tasks[0].title == "Task 3"  # Most recent first
        assert tasks[1].title == "Task 2"
        assert tasks[2].title == "Task 1"

    def test_list_tasks_with_status_filter(self, repository):
        """Test listing tasks filtered by status."""
        repository.create(Task(title="Pending Task", status=TaskStatus.PENDING))
        repository.create(Task(title="In Progress Task", status=TaskStatus.IN_PROGRESS))
        repository.create(Task(title="Completed Task", status=TaskStatus.COMPLETED))

        pending_tasks = repository.list_tasks(status=TaskStatus.PENDING)
        assert len(pending_tasks) == 1
        assert pending_tasks[0].title == "Pending Task"

        completed_tasks = repository.list_tasks(status=TaskStatus.COMPLETED)
        assert len(completed_tasks) == 1
        assert completed_tasks[0].title == "Completed Task"

    def test_list_tasks_with_priority_filter(self, repository):
        """Test listing tasks filtered by priority."""
        repository.create(Task(title="Low Priority", priority=Priority.LOW))
        repository.create(Task(title="High Priority", priority=Priority.HIGH))
        repository.create(Task(title="Urgent Priority", priority=Priority.URGENT))

        high_priority = repository.list_tasks(priority=Priority.HIGH)
        assert len(high_priority) == 1
        assert high_priority[0].title == "High Priority"

    def test_list_tasks_with_due_before_filter(self, repository):
        """Test listing tasks filtered by due date."""
        repository.create(Task(title="Due Jan 30", due_date=date(2026, 1, 30)))
        repository.create(Task(title="Due Feb 1", due_date=date(2026, 2, 1)))
        repository.create(Task(title="Due Feb 5", due_date=date(2026, 2, 5)))

        tasks_due_before_feb = repository.list_tasks(due_before=date(2026, 2, 1))
        assert len(tasks_due_before_feb) == 2
        assert any(t.title == "Due Jan 30" for t in tasks_due_before_feb)
        assert any(t.title == "Due Feb 1" for t in tasks_due_before_feb)

    def test_list_tasks_with_pagination(self, repository):
        """Test pagination of task listing."""
        for i in range(25):
            repository.create(Task(title=f"Task {i}"))

        # First page
        page1 = repository.list_tasks(limit=10, offset=0)
        assert len(page1) == 10

        # Second page
        page2 = repository.list_tasks(limit=10, offset=10)
        assert len(page2) == 10

        # Third page (partial)
        page3 = repository.list_tasks(limit=10, offset=20)
        assert len(page3) == 5

    def test_count_tasks(self, repository):
        """Test counting tasks."""
        repository.create(Task(title="Task 1"))
        repository.create(Task(title="Task 2"))
        repository.create(Task(title="Task 3"))

        count = repository.count_tasks()
        assert count == 3

    def test_count_tasks_with_filters(self, repository):
        """Test counting tasks with filters."""
        repository.create(Task(title="Pending", status=TaskStatus.PENDING))
        repository.create(Task(title="Completed", status=TaskStatus.COMPLETED))
        repository.create(
            Task(title="High Priority", status=TaskStatus.COMPLETED, priority=Priority.HIGH)
        )

        pending_count = repository.count_tasks(status=TaskStatus.PENDING)
        assert pending_count == 1

        completed_count = repository.count_tasks(status=TaskStatus.COMPLETED)
        assert completed_count == 2

        high_priority_count = repository.count_tasks(priority=Priority.HIGH)
        assert high_priority_count == 1

    def test_update_task(self, repository):
        """Test updating an existing task."""
        task = Task(title="Original Title")
        created = repository.create(task)

        created.title = "Updated Title"
        created.priority = Priority.HIGH
        updated = repository.update(created)

        assert updated.title == "Updated Title"
        assert updated.priority == Priority.HIGH
        assert updated.updated_at is not None

    def test_update_task_without_id_raises_error(self, repository):
        """Test that updating a task without id raises error."""
        task = Task(title="Test Task")

        with pytest.raises(ValueError, match="Cannot update task without id"):
            repository.update(task)

    def test_update_nonexistent_task_raises_error(self, repository):
        """Test that updating a nonexistent task raises error."""
        task = Task(id=999, title="Nonexistent Task")

        with pytest.raises(ValueError, match="Task with id 999 not found"):
            repository.update(task)

    def test_update_task_with_empty_title_raises_error(self, repository):
        """Test that updating a task with empty title raises error."""
        task = Task(title="Original")
        created = repository.create(task)

        created.title = ""

        with pytest.raises(ValueError, match="Task title cannot be empty"):
            repository.update(created)

    def test_delete_task(self, repository):
        """Test deleting a task."""
        task = Task(title="To Delete")
        created = repository.create(task)

        result = repository.delete(created.id)
        assert result is True

        retrieved = repository.get_by_id(created.id)
        assert retrieved is None

    def test_delete_nonexistent_task(self, repository):
        """Test deleting a nonexistent task returns False."""
        result = repository.delete(999)
        assert result is False
