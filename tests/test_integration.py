"""Integration tests for database persistence across service instances.

These tests verify that the service layer correctly persists data and that
changes are visible across multiple service instances (simulating how CLI
and MCP server would share the same database).
"""

import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest
from sqlmodel import Session, create_engine, SQLModel

from taskmanager.models import Priority, Task, TaskStatus
from taskmanager.repository_impl import SQLTaskRepository
from taskmanager.service import TaskService


@pytest.fixture
def test_db_path():
    """Create a temporary database for integration tests."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    
    # Initialize database schema
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)
    
    yield db_path
    
    # Cleanup
    if db_path.exists():
        db_path.unlink()


def get_service_for_db(db_path: Path) -> TaskService:
    """Create a service instance for a specific database."""
    engine = create_engine(f"sqlite:///{db_path}")
    session = Session(engine)
    repository = SQLTaskRepository(session)
    return TaskService(repository)


class TestServicePersistence:
    """Test that changes persist across service instances (simulates CLI/MCP interaction)."""

    def test_create_in_one_service_visible_in_another(self, test_db_path):
        """Test that tasks created in one service instance are visible in another."""
        # Create task with first service instance
        service1 = get_service_for_db(test_db_path)
        task = service1.create_task(title="Shared Task", priority=Priority.HIGH)
        task_id = task.id
        
        # Verify with second service instance (simulates different interface)
        service2 = get_service_for_db(test_db_path)
        retrieved_task = service2.get_task(task_id)
        
        assert retrieved_task.title == "Shared Task"
        assert retrieved_task.priority == Priority.HIGH

    def test_update_in_one_service_visible_in_another(self, test_db_path):
        """Test that updates in one service are visible in another."""
        # Create and update with first service
        service1 = get_service_for_db(test_db_path)
        task = service1.create_task(title="Original")
        task_id = task.id
        service1.update_task(task_id, title="Updated", priority=Priority.URGENT)
        
        # Verify with second service
        service2 = get_service_for_db(test_db_path)
        updated_task = service2.get_task(task_id)
        
        assert updated_task.title == "Updated"
        assert updated_task.priority == Priority.URGENT

    def test_delete_in_one_service_affects_another(self, test_db_path):
        """Test that deletions in one service are reflected in another."""
        # Create and delete with first service
        service1 = get_service_for_db(test_db_path)
        task = service1.create_task(title="To Delete")
        task_id = task.id
        service1.delete_task(task_id)
        
        # Verify deletion with second service
        service2 = get_service_for_db(test_db_path)
        with pytest.raises(ValueError, match="not found"):
            service2.get_task(task_id)

    def test_list_tasks_shows_all_service_created_tasks(self, test_db_path):
        """Test that list_tasks shows tasks created by different service instances."""
        # Create tasks with first service
        service1 = get_service_for_db(test_db_path)
        service1.create_task(title="Task 1")
        service1.create_task(title="Task 2")
        
        # Create more tasks with second service
        service2 = get_service_for_db(test_db_path)
        service2.create_task(title="Task 3")
        
        # List with third service
        service3 = get_service_for_db(test_db_path)
        tasks, total = service3.list_tasks()
        
        assert total == 3
        titles = {task.title for task in tasks}
        assert titles == {"Task 1", "Task 2", "Task 3"}

    def test_status_filter_works_across_services(self, test_db_path):
        """Test that status filtering works consistently across service instances."""
        # Create tasks with different statuses
        service1 = get_service_for_db(test_db_path)
        service1.create_task(title="Pending", status=TaskStatus.PENDING)
        service1.create_task(title="Completed", status=TaskStatus.COMPLETED)
        
        # Filter with second service
        service2 = get_service_for_db(test_db_path)
        pending_tasks, count = service2.list_tasks(status=TaskStatus.PENDING)
        
        assert count == 1
        assert pending_tasks[0].title == "Pending"

    def test_statistics_accurate_across_services(self, test_db_path):
        """Test that statistics are accurate across service instances."""
        # Create tasks with first service
        service1 = get_service_for_db(test_db_path)
        service1.create_task(title="P1", status=TaskStatus.PENDING)
        service1.create_task(title="P2", status=TaskStatus.PENDING)
        
        # Create more with second service
        service2 = get_service_for_db(test_db_path)
        service2.create_task(title="C1", status=TaskStatus.COMPLETED)
        
        # Get stats with third service
        service3 = get_service_for_db(test_db_path)
        stats = service3.get_statistics()
        
        assert stats["total"] == 3
        assert stats["pending"] == 2
        assert stats["completed"] == 1

    def test_complex_workflow_across_services(self, test_db_path):
        """Test a complex workflow spanning multiple service instances."""
        # Service 1: Create tasks
        service1 = get_service_for_db(test_db_path)
        task1 = service1.create_task(title="Task 1", priority=Priority.LOW)
        task2 = service1.create_task(title="Task 2", priority=Priority.HIGH)
        task3 = service1.create_task(title="Task 3", priority=Priority.MEDIUM)
        
        # Service 2: Update and complete
        service2 = get_service_for_db(test_db_path)
        service2.update_task(task1.id, status=TaskStatus.IN_PROGRESS)
        service2.update_task(task2.id, status=TaskStatus.COMPLETED)
        
        # Service 3: Delete and verify
        service3 = get_service_for_db(test_db_path)
        service3.delete_task(task3.id)
        
        # Service 4: Final verification
        service4 = get_service_for_db(test_db_path)
        tasks, total = service4.list_tasks()
        
        assert total == 2  # task3 deleted
        
        # Verify task states
        final_task1 = service4.get_task(task1.id)
        assert final_task1.status == TaskStatus.IN_PROGRESS
        
        final_task2 = service4.get_task(task2.id)
        assert final_task2.status == TaskStatus.COMPLETED
        
        # Verify task3 is gone
        with pytest.raises(ValueError):
            service4.get_task(task3.id)


class TestConcurrentAccess:
    """Test concurrent access patterns (multiple service instances)."""

    def test_sequential_writes_maintain_consistency(self, test_db_path):
        """Test that sequential writes from different services maintain consistency."""
        # Multiple services writing sequentially
        for i in range(5):
            service = get_service_for_db(test_db_path)
            service.create_task(title=f"Task {i + 1}")
        
        # Verify all tasks were created
        final_service = get_service_for_db(test_db_path)
        tasks, total = final_service.list_tasks()
        
        assert total == 5
        titles = {task.title for task in tasks}
        expected_titles = {f"Task {i + 1}" for i in range(5)}
        assert titles == expected_titles

    def test_interleaved_operations_work_correctly(self, test_db_path):
        """Test that interleaved operations from different services work correctly."""
        # Service 1: Create
        service1 = get_service_for_db(test_db_path)
        task1 = service1.create_task(title="Task 1")
        
        # Service 2: Create
        service2 = get_service_for_db(test_db_path)
        task2 = service2.create_task(title="Task 2")
        
        # Service 1: Update task1
        service1.update_task(task1.id, status=TaskStatus.COMPLETED)
        
        # Service 2: Update task2
        service2.update_task(task2.id, priority=Priority.URGENT)
        
        # Service 3: Verify both updates
        service3 = get_service_for_db(test_db_path)
        
        verified_task1 = service3.get_task(task1.id)
        assert verified_task1.status == TaskStatus.COMPLETED
        
        verified_task2 = service3.get_task(task2.id)
        assert verified_task2.priority == Priority.URGENT


class TestDataIntegrity:
    """Test data integrity across service instances."""

    def test_all_task_fields_persist_correctly(self, test_db_path):
        """Test that all task fields persist correctly."""
        # Create task with all fields
        service1 = get_service_for_db(test_db_path)
        due_date = date.today() + timedelta(days=7)
        task = service1.create_task(
            title="Complete Task",
            description="Full description",
            priority=Priority.HIGH,
            due_date=due_date,
            status=TaskStatus.IN_PROGRESS
        )
        
        # Retrieve with different service
        service2 = get_service_for_db(test_db_path)
        retrieved = service2.get_task(task.id)
        
        # Verify all fields
        assert retrieved.title == "Complete Task"
        assert retrieved.description == "Full description"
        assert retrieved.priority == Priority.HIGH
        assert retrieved.due_date == due_date
        assert retrieved.status == TaskStatus.IN_PROGRESS
        assert retrieved.created_at is not None

    def test_timestamps_persist_correctly(self, test_db_path):
        """Test that timestamps persist correctly across services."""
        # Create task
        service1 = get_service_for_db(test_db_path)
        task = service1.create_task(title="Timestamp Test")
        task_id = task.id
        original_created = task.created_at
        
        # Retrieve with different service
        service2 = get_service_for_db(test_db_path)
        retrieved = service2.get_task(task_id)
        
        # Verify created_at persisted
        assert retrieved.created_at == original_created
        
        # Update task
        service2.update_task(task_id, title="Updated")
        
        # Retrieve with third service
        service3 = get_service_for_db(test_db_path)
        updated = service3.get_task(task_id)
        
        # Verify updated_at is set
        assert updated.updated_at is not None
        assert updated.created_at == original_created  # created_at unchanged

    def test_empty_optional_fields_persist_correctly(self, test_db_path):
        """Test that empty optional fields persist correctly."""
        # Create minimal task
        service1 = get_service_for_db(test_db_path)
        task = service1.create_task(title="Minimal Task")
        
        # Retrieve with different service
        service2 = get_service_for_db(test_db_path)
        retrieved = service2.get_task(task.id)
        
        # Verify optional fields are None
        assert retrieved.description is None
        assert retrieved.due_date is None
