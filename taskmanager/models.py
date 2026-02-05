"""Data models for the Task Manager application.

This module defines the core SQLModel models for persistent storage,
including the Task entity and associated enumerations.
"""

from datetime import date, datetime
from enum import Enum

from sqlmodel import Field, SQLModel, UniqueConstraint


class TaskStatus(str, Enum):
    """Status of a task in its lifecycle."""

    PENDING = "pending"  # Not started
    IN_PROGRESS = "in_progress"  # Currently working on
    COMPLETED = "completed"  # Finished
    CANCELLED = "cancelled"  # Abandoned/no longer needed
    ARCHIVED = "archived"  # Old/inactive

    # Agent communication statuses (for multi-agent workflows)
    ASSIGNED = "assigned"  # Main agent assigned work to delegate
    STUCK = "stuck"  # Delegate blocked, needs intervention
    REVIEW = "review"  # Delegate work ready for review before integration
    INTEGRATE = "integrate"  # Approved, ready to merge to main


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
        tags: Comma-separated tags for categorization (e.g., "backend,api,bug-fix").
    """

    # Identity
    id: int | None = Field(
        default=None,
        primary_key=True,
        sa_column_kwargs={"autoincrement": True}
    )

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
    tags: str | None = Field(default=None, description="Comma-separated tags for categorization", index=True)
    attachments: str | None = Field(default=None, description="JSON array of attachment metadata")

    # Workspace
    workspace_path: str | None = Field(default=None, description="Path to task-specific LLM agent workspace")

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

class Attachment(SQLModel, table=True):
    """File attachment associated with a task.
    
    Attributes:
        id: Unique identifier for the attachment (auto-generated).
        task_id: Foreign key to the task this attachment belongs to.
        original_filename: The original filename provided by user (e.g., "TASK_59_PROMPT.md").
        storage_filename: Timestamp-prefixed storage filename (e.g., "20260204_193601_TASK_59_PROMPT.md").
        file_data: Binary content of the file.
        size_bytes: Size of the file in bytes.
        created_at: Timestamp when attachment was added.
    """
    
    __tablename__ = "attachment"
    
    # Identity
    id: int | None = Field(
        default=None,
        primary_key=True,
        sa_column_kwargs={"autoincrement": True}
    )
    
    # Foreign key
    task_id: int = Field(foreign_key="task.id", index=True)
    
    # Filenames - dual indexing for flexible retrieval
    original_filename: str = Field(
        description="Original filename provided by user when attaching"
    )
    storage_filename: str = Field(
        description="Timestamp-prefixed storage filename"
    )
    
    # Content
    file_data: bytes = Field(description="Binary file content")
    size_bytes: int = Field(description="File size in bytes")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.now, index=True)
    
    # Unique constraint: prevent duplicate original filenames per task
    __table_args__ = (
        UniqueConstraint('task_id', 'original_filename', name='uq_attachment_task_original_filename'),
    )