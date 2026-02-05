"""Tests for agent communication status system.

Tests verify that delegate agents can mark tasks as stuck/review
and main agents can mark tasks as integrate, enabling multi-agent
feature development workflows.
"""

import tempfile
from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine

from taskmanager.models import TaskStatus
from taskmanager.repository_impl import SQLTaskRepository
from taskmanager.service import TaskService


@pytest.fixture
def test_db():
    """Create a temporary database for tests."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)

    yield db_path

    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def service(test_db):
    """Create a task service instance."""
    engine = create_engine(f"sqlite:///{test_db}")
    session = Session(engine)
    repository = SQLTaskRepository(session)
    return TaskService(repository)


class TestAgentStatusTransitions:
    """Test the full agent communication workflow."""

    def test_assign_task_to_delegate(self, service):
        """Test main agent assigning task to delegate."""
        # Create task in pending state
        task = service.create_task(
            title="Implement new feature",
            description="Complex feature requiring delegate work",
            priority="high"
        )
        assert task.status == TaskStatus.PENDING

        # Main agent marks as assigned
        updated = service.update_task(task.id, status="assigned")
        assert updated.status == TaskStatus.ASSIGNED
        assert updated.status.value == "assigned"

    def test_delegate_marks_review_when_complete(self, service):
        """Test delegate marking work as ready for review."""
        task = service.create_task(title="Feature", status="assigned")
        assert task.status == TaskStatus.ASSIGNED

        # Delegate completes work and marks review
        updated = service.update_task(
            task.id,
            status="review",
            description="Implementation complete. Tests pass. Linting passes."
        )
        assert updated.status == TaskStatus.REVIEW

    def test_main_agent_approves_and_marks_integrate(self, service):
        """Test main agent approving delegate work for integration."""
        task = service.create_task(title="Feature", status="review")

        # Main agent reviews and marks integrate
        updated = service.update_task(task.id, status="integrate")
        assert updated.status == TaskStatus.INTEGRATE

    def test_full_assigned_review_integrate_workflow(self, service):
        """Test complete workflow from assignment to integration."""
        # 1. Main agent: Create task, mark assigned
        task = service.create_task(
            title="Implement agent communication system",
            description="Enable multi-agent workflows"
        )
        assert task.status == TaskStatus.PENDING

        task = service.update_task(task.id, status="assigned")
        assert task.status == TaskStatus.ASSIGNED

        # 2. Delegate agent: Implement and mark review
        task = service.update_task(
            task.id,
            status="review",
            description="Added 4 new statuses: assigned, stuck, review, integrate. Tests pass."
        )
        assert task.status == TaskStatus.REVIEW

        # 3. Main agent: Review and mark integrate
        task = service.update_task(task.id, status="integrate")
        assert task.status == TaskStatus.INTEGRATE

        # 4. Human: Merge and complete
        task = service.update_task(task.id, status="completed")
        assert task.status == TaskStatus.COMPLETED

    def test_delegate_marks_stuck_when_blocked(self, service):
        """Test delegate marking task as stuck due to blocker."""
        task = service.create_task(title="Complex feature", status="assigned")

        # Delegate encounters blocker
        updated = service.update_task(
            task.id,
            status="stuck",
            description="Cannot proceed: database migration fails. Need DevOps intervention."
        )
        assert updated.status == TaskStatus.STUCK

    def test_stuck_to_assigned_when_blocker_resolved(self, service):
        """Test marking task back to assigned after blocker is resolved."""
        task = service.create_task(
            title="Feature",
            status="stuck",
            description="Database migration failed"
        )

        # Main agent fixes blocker, marks back to assigned
        updated = service.update_task(
            task.id,
            status="assigned",
            description="DevOps fixed migration. Retrying implementation."
        )
        assert updated.status == TaskStatus.ASSIGNED

    def test_review_with_feedback_cycles_back_to_assigned(self, service):
        """Test cycle between review and assigned when feedback requires changes."""
        task = service.create_task(title="Feature", status="assigned")

        # Delegate marks review
        task = service.update_task(task.id, status="review")
        assert task.status == TaskStatus.REVIEW

        # Main agent provides feedback, marks back to assigned
        task = service.update_task(
            task.id,
            status="assigned",
            description="Review feedback: needs refactoring for performance. Please iterate."
        )
        assert task.status == TaskStatus.ASSIGNED

        # Delegate makes changes and marks review again
        task = service.update_task(task.id, status="review")
        assert task.status == TaskStatus.REVIEW


class TestAgentStatusValidation:
    """Test that all agent statuses are properly supported."""

    def test_all_agent_statuses_accepted(self, service):
        """Test that all four new statuses are accepted."""
        task = service.create_task(title="Test")

        for status in ["assigned", "stuck", "review", "integrate"]:
            updated = service.update_task(task.id, status=status)
            assert updated.status.value == status

    def test_task_with_agent_status_persists_across_queries(self, service):
        """Test that agent status values persist in database."""
        task = service.create_task(title="Feature", status="assigned")
        task_id = task.id

        # Query the task again
        retrieved = service.get_task(task_id)
        assert retrieved.status == TaskStatus.ASSIGNED
        assert retrieved.status.value == "assigned"

    def test_list_tasks_includes_agent_statuses(self, service):
        """Test that list operations include tasks with agent statuses."""
        service.create_task(title="Pending task", status="pending")
        service.create_task(title="Assigned task", status="assigned")
        service.create_task(title="Stuck task", status="stuck")
        service.create_task(title="Review task", status="review")
        service.create_task(title="Integrate task", status="integrate")

        all_tasks, total = service.list_tasks()
        assert len(all_tasks) == 5
        assert total == 5

        # Verify each status is represented
        statuses = {t.status.value for t in all_tasks}
        assert "assigned" in statuses
        assert "stuck" in statuses
        assert "review" in statuses
        assert "integrate" in statuses


class TestAgentStatusFiltering:
    """Test filtering tasks by agent statuses."""

    def test_filter_by_assigned_status(self, service):
        """Test filtering to find assigned tasks."""
        service.create_task(title="Assigned 1", status="assigned")
        service.create_task(title="Assigned 2", status="assigned")
        service.create_task(title="Pending", status="pending")

        assigned_tasks, total = service.list_tasks(status="assigned")
        assert len(assigned_tasks) == 2
        assert total == 2
        assert all(t.status == TaskStatus.ASSIGNED for t in assigned_tasks)

    def test_filter_by_review_status(self, service):
        """Test filtering to find tasks ready for review."""
        service.create_task(title="Review 1", status="review")
        service.create_task(title="Review 2", status="review")
        service.create_task(title="Assigned", status="assigned")

        review_tasks, total = service.list_tasks(status="review")
        assert len(review_tasks) == 2
        assert total == 2
        assert all(t.status == TaskStatus.REVIEW for t in review_tasks)

    def test_filter_by_stuck_status(self, service):
        """Test filtering to find blocked tasks."""
        service.create_task(title="Stuck 1", status="stuck")
        service.create_task(title="Stuck 2", status="stuck")
        service.create_task(title="In Progress", status="in_progress")

        stuck_tasks, total = service.list_tasks(status="stuck")
        assert len(stuck_tasks) == 2
        assert total == 2
        assert all(t.status == TaskStatus.STUCK for t in stuck_tasks)


class TestWorkflowWithDescription:
    """Test agent workflow updates with task descriptions."""

    def test_stuck_includes_blocker_details(self, service):
        """Test that stuck status includes blocker description."""
        blocker_description = """Cannot proceed: environment setup failure
        
Error: Python 3.9 required but system has 3.8
Solution needed: Upgrade Python or update requirements

Awaiting main agent intervention."""

        task = service.create_task(
            title="Feature",
            status="assigned",
            description="Initial implementation started"
        )

        task = service.update_task(
            task.id,
            status="stuck",
            description=blocker_description
        )

        assert task.status == TaskStatus.STUCK
        assert "Python 3.9 required" in task.description

    def test_review_includes_summary(self, service):
        """Test that review status includes implementation summary."""
        review_summary = """Implementation complete!

Changes delivered:
- Added 4 new statuses to TaskStatus enum
- Updated README with workflow documentation
- Added AGENT_GUIDANCE.md section for delegate signaling
- Updated CLI help text
- 12 new tests added

Test results:
- All unit tests passing (45/45)
- Integration tests passing (28/28)
- Linting: ruff check . passed
- Type check: mypy passed
- Security: bandit passed

Ready for code review."""

        task = service.create_task(title="Feature", status="assigned")

        task = service.update_task(
            task.id,
            status="review",
            description=review_summary
        )

        assert task.status == TaskStatus.REVIEW
        assert "Implementation complete" in task.description
        assert "All unit tests passing" in task.description


class TestMultipleAgentInteractions:
    """Test scenarios with multiple independent tasks."""

    def test_multiple_concurrent_delegate_tasks(self, service):
        """Test multiple delegates working on different tasks simultaneously."""
        # Create multiple tasks assigned to different delegates
        task1 = service.create_task(title="Feature A", status="assigned")
        task2 = service.create_task(title="Feature B", status="assigned")
        task3 = service.create_task(title="Feature C", status="assigned")

        # Delegate 1 completes task1
        task1 = service.update_task(task1.id, status="review")

        # Delegate 2 completes task2
        task2 = service.update_task(task2.id, status="review")

        # Delegate 3 is stuck
        task3 = service.update_task(task3.id, status="stuck")

        # Verify all states are correct
        assert service.get_task(task1.id).status == TaskStatus.REVIEW
        assert service.get_task(task2.id).status == TaskStatus.REVIEW
        assert service.get_task(task3.id).status == TaskStatus.STUCK

        # Main agent approves task1
        service.update_task(task1.id, status="integrate")

        # Verify task1 is integrate, others unchanged
        assert service.get_task(task1.id).status == TaskStatus.INTEGRATE
        assert service.get_task(task2.id).status == TaskStatus.REVIEW
        assert service.get_task(task3.id).status == TaskStatus.STUCK

    def test_workflow_state_tracking(self, service):
        """Test that timestamps are updated correctly through workflow."""
        task = service.create_task(title="Feature")
        created_at = task.created_at

        # Mark assigned
        task = service.update_task(task.id, status="assigned")
        assert task.updated_at is not None
        assert task.updated_at >= created_at

        # Mark review
        task = service.update_task(task.id, status="review")
        previous_updated = task.updated_at

        # Small delay to ensure timestamp difference
        import time
        time.sleep(0.01)

        # Mark integrate
        task = service.update_task(task.id, status="integrate")
        assert task.updated_at >= previous_updated
