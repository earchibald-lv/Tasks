"""Tests for data models."""

from datetime import date, datetime

from taskmanager.models import Priority, Task, TaskStatus


class TestTaskStatus:
    """Tests for TaskStatus enumeration."""

    def test_all_statuses_exist(self):
        """Test that all expected statuses are defined."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.IN_PROGRESS.value == "in_progress"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.ARCHIVED.value == "archived"


class TestPriority:
    """Tests for Priority enumeration."""

    def test_all_priorities_exist(self):
        """Test that all expected priorities are defined."""
        assert Priority.LOW.value == "low"
        assert Priority.MEDIUM.value == "medium"
        assert Priority.HIGH.value == "high"
        assert Priority.URGENT.value == "urgent"


class TestTask:
    """Tests for Task model."""

    def test_task_creation_with_defaults(self):
        """Test creating a task with minimal required fields."""
        task = Task(title="Test Task")

        assert task.title == "Test Task"
        assert task.description is None
        assert task.status == TaskStatus.PENDING
        assert task.priority == Priority.MEDIUM
        assert task.due_date is None
        assert task.id is None
        assert isinstance(task.created_at, datetime)
        assert task.updated_at is None

    def test_task_creation_with_all_fields(self):
        """Test creating a task with all fields specified."""
        due = date(2026, 2, 1)
        created = datetime(2026, 1, 29, 12, 0, 0)

        task = Task(
            title="Complete Task",
            description="Detailed description",
            status=TaskStatus.IN_PROGRESS,
            priority=Priority.HIGH,
            due_date=due,
            created_at=created,
        )

        assert task.title == "Complete Task"
        assert task.description == "Detailed description"
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.priority == Priority.HIGH
        assert task.due_date == due
        assert task.created_at == created

    def test_mark_updated(self):
        """Test that mark_updated sets updated_at timestamp."""
        task = Task(title="Test Task")
        assert task.updated_at is None

        task.mark_updated()
        assert task.updated_at is not None
        assert isinstance(task.updated_at, datetime)

    def test_mark_complete(self):
        """Test that mark_complete updates status and timestamp."""
        task = Task(title="Test Task", status=TaskStatus.PENDING)

        assert task.status == TaskStatus.PENDING
        assert task.updated_at is None

        task.mark_complete()

        assert task.status == TaskStatus.COMPLETED
        assert task.updated_at is not None

    def test_task_repr(self):
        """Test string representation of task."""
        task = Task(id=42, title="Test Task", status=TaskStatus.PENDING)
        repr_str = repr(task)

        assert "Task" in repr_str
        assert "42" in repr_str
        assert "Test Task" in repr_str
        assert "pending" in repr_str
