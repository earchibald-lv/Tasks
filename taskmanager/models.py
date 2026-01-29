"""Data models for the Task Manager application.

This module defines the core SQLModel models for persistent storage,
including the Task entity and associated enumerations.
"""

from datetime import date, datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class TaskStatus(str, Enum):
    """Status of a task in its lifecycle."""

    PENDING = "pending"  # Not started
    IN_PROGRESS = "in_progress"  # Currently working on
    COMPLETED = "completed"  # Finished
    ARCHIVED = "archived"  # Old/inactive


class Priority(str, Enum):
    """Priority level for task importance and urgency."""

    LOW = "low"  # Nice to have
    MEDIUM = "medium"  # Normal priority
    HIGH = "high"  # Important
    URGENT = "urgent"  # Critical/time-sensitive


class Task(SQLModel, table=True):
    """Task entity representing a single to-do item.

    Attributes:
        id: Unique identifier for the task (auto-generated).
        title: Brief description of the task (required, max 200 chars).
        description: Detailed description of the task (optional).
        status: Current status of the task (default: PENDING).
        priority: Priority level of the task (default: MEDIUM).
        due_date: Optional deadline for task completion.
        created_at: Timestamp when task was created (auto-generated).
        updated_at: Timestamp when task was last updated (auto-updated).
        jira_issues: Comma-separated JIRA issue keys (e.g., "SRE-1234,DEVOPS-5678").
    """

    # Identity
    id: int | None = Field(default=None, primary_key=True)

    # Core fields
    title: str = Field(min_length=1, max_length=200, index=True)
    description: str | None = Field(default=None)

    # Status and workflow
    status: TaskStatus = Field(default=TaskStatus.PENDING, index=True)
    priority: Priority = Field(default=Priority.MEDIUM, index=True)

    # Scheduling
    due_date: date | None = Field(default=None, index=True)

    # Metadata
    created_at: datetime = Field(default_factory=datetime.now, index=True)
    updated_at: datetime | None = Field(default=None)

    # External tracking
    jira_issues: str | None = Field(default=None, description="Comma-separated JIRA issue keys")

    def mark_updated(self) -> None:
        """Update the updated_at timestamp to current time."""
        self.updated_at = datetime.now()

    def mark_complete(self) -> None:
        """Mark task as completed and update timestamp."""
        self.status = TaskStatus.COMPLETED
        self.mark_updated()

    def __repr__(self) -> str:
        """Return string representation of task."""
        return f"Task(id={self.id}, title='{self.title}', status={self.status.value})"
