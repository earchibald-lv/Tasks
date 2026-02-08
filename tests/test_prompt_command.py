"""Tests for the prompt command functionality."""

import tempfile
from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine

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
    return TaskService(repository, session=session, enable_semantic_search=False)


class TestPromptConstruction:
    """Test the construct_full_prompt method in TaskService."""

    def test_construct_full_prompt_basic(self, test_db_path):
        """Test basic prompt construction without task or query."""
        service = get_service_for_db(test_db_path)

        # Create some tasks
        service.create_task(title="Task 1", priority=Priority.HIGH)
        service.create_task(title="Task 2", priority=Priority.MEDIUM, status=TaskStatus.IN_PROGRESS)

        # Generate prompt
        prompt = service.construct_full_prompt()

        # Verify key sections are present
        assert "# Mission: Smart Assistant for Task & JIRA Management" in prompt
        assert "## Available MCP Tools" in prompt
        assert "# Initial Task Context" in prompt
        assert "**Total tasks:** 2" in prompt

    def test_construct_full_prompt_with_query(self, test_db_path):
        """Test prompt construction with a user query."""
        service = get_service_for_db(test_db_path)

        # Generate prompt with query
        query = "Help me prioritize my tasks"
        prompt = service.construct_full_prompt(user_query=query)

        # Verify query is included
        assert "# User Query" in prompt
        assert query in prompt

    def test_construct_full_prompt_with_task_id(self, test_db_path):
        """Test prompt construction focused on a specific task."""
        service = get_service_for_db(test_db_path)

        # Create a task
        task = service.create_task(
            title="Focus Task",
            description="A task to focus on",
            priority=Priority.HIGH,
            status=TaskStatus.IN_PROGRESS
        )

        # Generate prompt with task focus
        prompt = service.construct_full_prompt(task_id=task.id)

        # Verify task context is included
        assert "## Current Task Focus" in prompt
        assert f"**Task ID:** #{task.id}" in prompt
        assert "**Title:** Focus Task" in prompt
        assert "**Description:** A task to focus on" in prompt
        assert "**Priority:** high" in prompt
        assert "**Status:** in_progress" in prompt

    def test_construct_full_prompt_with_query_and_task(self, test_db_path):
        """Test prompt construction with both query and task focus."""
        service = get_service_for_db(test_db_path)

        # Create a task
        task = service.create_task(title="Test Task")

        # Generate prompt with both
        query = "What should I do next?"
        prompt = service.construct_full_prompt(user_query=query, task_id=task.id)

        # Verify both are included
        assert "## Current Task Focus" in prompt
        assert f"**Task ID:** #{task.id}" in prompt
        assert "# User Query" in prompt
        assert query in prompt

    def test_construct_full_prompt_shows_task_categories(self, test_db_path):
        """Test that prompt shows urgent, overdue, and in-progress tasks."""
        service = get_service_for_db(test_db_path)

        # Create various tasks
        service.create_task(title="Urgent Task", priority=Priority.URGENT)
        service.create_task(title="High Priority", priority=Priority.HIGH)
        service.create_task(title="In Progress", status=TaskStatus.IN_PROGRESS)

        # Generate prompt
        prompt = service.construct_full_prompt()

        # Verify categorization
        assert "🚨 Urgent Tasks" in prompt
        assert "⚠️ High Priority Tasks" in prompt or "🚨 Urgent Tasks" in prompt
        assert "▶️ In Progress" in prompt

    def test_construct_full_prompt_includes_timezone_info(self, test_db_path):
        """Test that prompt includes timezone and date information."""
        service = get_service_for_db(test_db_path)

        # Generate prompt
        prompt = service.construct_full_prompt()

        # Verify time context
        assert "**Current Time:**" in prompt
        assert "**Today's Date:**" in prompt
        assert "**Day of Week:**" in prompt
        assert "**Timezone:**" in prompt
        assert "**Weekend:**" in prompt
