"""Performance tests for task management operations.

These tests verify that operations complete within acceptable time limits
and that the system handles larger datasets efficiently.
"""

import time
from datetime import date, timedelta

import pytest
from sqlmodel import Session, create_engine, SQLModel

from taskmanager.models import Priority, TaskStatus
from taskmanager.repository_impl import SQLTaskRepository
from taskmanager.service import TaskService


@pytest.fixture
def perf_service(tmp_path):
    """Create a service instance for performance testing."""
    db_path = tmp_path / "perf_test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)
    
    session = Session(engine)
    repository = SQLTaskRepository(session)
    return TaskService(repository)


class TestBasicOperationPerformance:
    """Test that basic operations complete quickly."""

    def test_create_task_performance(self, perf_service):
        """Test that task creation completes quickly."""
        start = time.time()
        perf_service.create_task(title="Performance Test Task")
        duration = time.time() - start
        
        # Should complete in under 50ms
        assert duration < 0.05, f"Task creation took {duration:.3f}s"

    def test_get_task_performance(self, perf_service):
        """Test that task retrieval completes quickly."""
        task = perf_service.create_task(title="Test Task")
        
        start = time.time()
        perf_service.get_task(task.id)
        duration = time.time() - start
        
        # Should complete in under 10ms
        assert duration < 0.01, f"Task retrieval took {duration:.3f}s"

    def test_update_task_performance(self, perf_service):
        """Test that task update completes quickly."""
        task = perf_service.create_task(title="Original")
        
        start = time.time()
        perf_service.update_task(task.id, title="Updated")
        duration = time.time() - start
        
        # Should complete in under 50ms
        assert duration < 0.05, f"Task update took {duration:.3f}s"

    def test_delete_task_performance(self, perf_service):
        """Test that task deletion completes quickly."""
        task = perf_service.create_task(title="To Delete")
        
        start = time.time()
        perf_service.delete_task(task.id)
        duration = time.time() - start
        
        # Should complete in under 50ms
        assert duration < 0.05, f"Task deletion took {duration:.3f}s"


class TestListOperationPerformance:
    """Test that list operations scale well."""

    def test_list_small_dataset_performance(self, perf_service):
        """Test list performance with small dataset (10 tasks)."""
        # Create 10 tasks
        for i in range(10):
            perf_service.create_task(title=f"Task {i}")
        
        start = time.time()
        tasks, total = perf_service.list_tasks()
        duration = time.time() - start
        
        assert total == 10
        # Should complete in under 50ms
        assert duration < 0.05, f"List 10 tasks took {duration:.3f}s"

    def test_list_medium_dataset_performance(self, perf_service):
        """Test list performance with medium dataset (100 tasks)."""
        # Create 100 tasks
        for i in range(100):
            perf_service.create_task(
                title=f"Task {i}",
                priority=Priority.HIGH if i % 3 == 0 else Priority.LOW,
                status=TaskStatus.COMPLETED if i % 5 == 0 else TaskStatus.PENDING
            )
        
        start = time.time()
        tasks, total = perf_service.list_tasks(limit=20)
        duration = time.time() - start
        
        assert total == 100
        assert len(tasks) == 20  # Pagination working
        # Should complete in under 100ms even with 100 tasks
        assert duration < 0.1, f"List 100 tasks took {duration:.3f}s"

    def test_filtered_list_performance(self, perf_service):
        """Test that filtered queries perform well."""
        # Create 50 tasks with various statuses
        for i in range(50):
            perf_service.create_task(
                title=f"Task {i}",
                status=TaskStatus.COMPLETED if i % 3 == 0 else TaskStatus.PENDING
            )
        
        start = time.time()
        tasks, total = perf_service.list_tasks(status=TaskStatus.COMPLETED)
        duration = time.time() - start
        
        assert total > 0
        # Filtered query should be fast (indexes help)
        assert duration < 0.05, f"Filtered list took {duration:.3f}s"

    def test_pagination_performance(self, perf_service):
        """Test that pagination doesn't load all data."""
        # Create 100 tasks
        for i in range(100):
            perf_service.create_task(title=f"Task {i}")
        
        # Get page 5 (should not load first 80 tasks into memory)
        start = time.time()
        tasks, total = perf_service.list_tasks(limit=20, offset=80)
        duration = time.time() - start
        
        assert len(tasks) == 20
        assert total == 100
        # Should be fast even with large offset
        assert duration < 0.1, f"Paginated query took {duration:.3f}s"


class TestStatisticsPerformance:
    """Test that statistics operations perform well."""

    def test_statistics_with_many_tasks(self, perf_service):
        """Test statistics performance with many tasks."""
        # Create 100 tasks with various attributes
        for i in range(100):
            perf_service.create_task(
                title=f"Task {i}",
                priority=Priority(["low", "medium", "high"][i % 3]),
                status=TaskStatus(["pending", "in_progress", "completed"][i % 3])
            )
        
        start = time.time()
        stats = perf_service.get_statistics()
        duration = time.time() - start
        
        assert stats["total"] == 100
        # Multiple count queries should complete quickly
        assert duration < 0.2, f"Statistics took {duration:.3f}s"

    def test_overdue_tasks_performance(self, perf_service):
        """Test overdue task query performance."""
        # Create tasks with various due dates
        today = date.today()
        for i in range(50):
            due_date = today - timedelta(days=i) if i % 2 == 0 else today + timedelta(days=i)
            perf_service.create_task(
                title=f"Task {i}",
                due_date=due_date,
                status=TaskStatus.PENDING if i % 3 != 0 else TaskStatus.COMPLETED
            )
        
        start = time.time()
        overdue = perf_service.get_overdue_tasks()
        duration = time.time() - start
        
        assert len(overdue) > 0
        # Filtered date query should be fast
        assert duration < 0.1, f"Overdue query took {duration:.3f}s"


class TestBulkOperationPerformance:
    """Test performance of bulk operations."""

    def test_bulk_create_performance(self, perf_service):
        """Test creating many tasks in sequence."""
        start = time.time()
        
        # Create 50 tasks
        for i in range(50):
            perf_service.create_task(title=f"Bulk Task {i}")
        
        duration = time.time() - start
        
        # Should average less than 50ms per task
        avg_time = duration / 50
        assert avg_time < 0.05, f"Average creation time: {avg_time:.3f}s"

    def test_bulk_update_performance(self, perf_service):
        """Test updating many tasks in sequence."""
        # Create 50 tasks
        task_ids = []
        for i in range(50):
            task = perf_service.create_task(title=f"Task {i}")
            task_ids.append(task.id)
        
        start = time.time()
        
        # Update all tasks
        for task_id in task_ids:
            perf_service.update_task(task_id, status=TaskStatus.COMPLETED)
        
        duration = time.time() - start
        
        # Should average less than 50ms per update
        avg_time = duration / 50
        assert avg_time < 0.05, f"Average update time: {avg_time:.3f}s"


class TestMemoryEfficiency:
    """Test that operations don't use excessive memory."""

    def test_list_does_not_load_all_tasks(self, perf_service):
        """Test that list with limit doesn't load all tasks into memory."""
        # Create 200 tasks
        for i in range(200):
            perf_service.create_task(title=f"Task {i}")
        
        # Request only 10 tasks
        tasks, total = perf_service.list_tasks(limit=10)
        
        # Should return exactly 10 tasks, not 200
        assert len(tasks) == 10
        assert total == 200
        
        # This validates that pagination works correctly and
        # doesn't load all 200 tasks into the list

    def test_count_does_not_load_all_tasks(self, perf_service):
        """Test that count operations don't load all task data."""
        # Create 100 tasks
        for i in range(100):
            perf_service.create_task(
                title=f"Task {i}",
                description="Long description " * 100,  # Make tasks larger
                status=TaskStatus.PENDING
            )
        
        start = time.time()
        _, total = perf_service.list_tasks(limit=1)
        duration = time.time() - start
        
        assert total == 100
        # Should be fast even with large task descriptions
        # because count should not load full objects
        assert duration < 0.1, f"Count with large tasks took {duration:.3f}s"
