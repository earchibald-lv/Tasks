"""FastMCP 3.0 server for task management.

This module provides an MCP server that exposes task management functionality
to AI agents through tools with User Elicitation for interactive forms.
"""

from datetime import date, datetime
from typing import Literal

from fastmcp import FastMCP, Context
from pydantic import BaseModel, Field

from taskmanager.database import get_session, init_db
from taskmanager.models import Priority, Task, TaskStatus
from taskmanager.repository_impl import SQLTaskRepository
from taskmanager.service import TaskService

# Initialize FastMCP server
mcp = FastMCP("Task Manager", version="0.1.0")

# Initialize database on startup
init_db()


def get_service() -> TaskService:
    """Create and return a TaskService instance."""
    session = get_session()
    repository = SQLTaskRepository(session)
    return TaskService(repository)


def format_task_markdown(task: Task) -> str:
    """Format a task as Markdown."""
    lines = [
        f"# Task #{task.id}: {task.title}",
        "",
        f"**Status:** {task.status.value}",
        f"**Priority:** {task.priority.value}",
    ]

    if task.description:
        lines.extend(["", f"**Description:** {task.description}"])

    if task.due_date:
        is_overdue = task.due_date < date.today() and task.status not in [
            TaskStatus.COMPLETED,
            TaskStatus.ARCHIVED,
        ]
        due_str = f"{task.due_date} ⚠️ OVERDUE" if is_overdue else str(task.due_date)
        lines.append(f"**Due:** {due_str}")

    lines.append("")
    if task.created_at:
        lines.append(f"**Created:** {task.created_at.strftime('%Y-%m-%d %H:%M')}")
    if task.updated_at:
        lines.append(f"**Updated:** {task.updated_at.strftime('%Y-%m-%d %H:%M')}")

    return "\n".join(lines)


# ============================================================================
# User Elicitation Forms (Pydantic Models)
# ============================================================================


class TaskCreationForm(BaseModel):
    """Interactive form for creating a new task."""

    title: str = Field(description="Task title (required)")
    description: str = Field(default="", description="Detailed description (optional)")
    priority: Literal["low", "medium", "high"] = Field(
        default="medium", description="Task priority"
    )
    due_date: str = Field(default="", description="Due date in YYYY-MM-DD format (optional)")


class TaskUpdateForm(BaseModel):
    """Interactive form for updating an existing task."""

    title: str = Field(default="", description="New task title (leave empty to keep current)")
    description: str = Field(default="", description="New description (leave empty to keep current)")
    priority: str = Field(
        default="", description="New priority: low, medium, high (leave empty to keep current)"
    )
    status: str = Field(
        default="", description="New status: todo, in_progress, done (leave empty to keep current)"
    )
    due_date: str = Field(default="", description="New due date YYYY-MM-DD (leave empty to keep current)")


class TaskDeletionConfirmation(BaseModel):
    """Confirmation form for deleting a task."""

    confirm: bool = Field(
        default=False,
        description="Confirm deletion (true to delete, false to cancel)",
    )


# ============================================================================
# Tools with User Elicitation
# ============================================================================


@mcp.tool()
async def create_task_interactive(ctx: Context) -> str:
    """Create a new task with an interactive form.

    This tool presents a form to collect all task details interactively,
    making it easy to create well-structured tasks with all necessary information.
    """
    # Request structured input from user
    result = await ctx.elicit(
        message="Please provide task details",
        response_type=TaskCreationForm,
    )

    # Handle user response
    if result.action == "accept":
        task_data = result.data

        # Parse due_date if provided
        parsed_due_date = None
        if task_data.due_date and task_data.due_date.strip():
            try:
                parsed_due_date = datetime.strptime(task_data.due_date.strip(), "%Y-%m-%d").date()
            except ValueError:
                return f"❌ Invalid date format: {task_data.due_date}. Use YYYY-MM-DD"

        # Create task in database
        service = get_service()
        task = service.create_task(
            title=task_data.title,
            description=task_data.description if task_data.description.strip() else None,
            priority=Priority(task_data.priority),
            due_date=parsed_due_date,
        )

        return f"✅ **Created task #{task.id}:** {task.title}\n\n{format_task_markdown(task)}"

    elif result.action == "decline":
        return "❌ Task creation declined - no changes made"

    else:  # cancel
        return "🚫 Task creation cancelled"


@mcp.tool()
async def update_task_interactive(ctx: Context, task_id: int) -> str:
    """Update an existing task with an interactive form showing current values.

    This tool fetches the current task and presents a form pre-filled with
    existing values, making it easy to see what you're changing.

    Args:
        task_id: The ID of the task to update
    """
    service = get_service()

    # Fetch current task
    task = service.get_task(task_id)
    if not task:
        return f"❌ Task #{task_id} not found"

    # Request updates with current values shown
    result = await ctx.elicit(
        message=f"Update task #{task_id}: {task.title}\n\nCurrent values will be shown in the form. Leave fields empty to keep current values.",
        response_type=TaskUpdateForm,
    )

    if result.action == "accept":
        updates = result.data

        # Build update dict with only changed fields (non-empty strings)
        update_dict = {}
        if updates.title and updates.title.strip():
            update_dict["title"] = updates.title.strip()
        if updates.description and updates.description.strip():
            update_dict["description"] = updates.description.strip()
        if updates.priority and updates.priority.strip():
            try:
                update_dict["priority"] = Priority(updates.priority.strip())
            except ValueError:
                return f"❌ Invalid priority: {updates.priority}. Use: low, medium, high"
        if updates.status and updates.status.strip():
            try:
                update_dict["status"] = TaskStatus(updates.status.strip())
            except ValueError:
                return f"❌ Invalid status: {updates.status}. Use: todo, in_progress, done"
        if updates.due_date and updates.due_date.strip():
            try:
                update_dict["due_date"] = datetime.strptime(updates.due_date.strip(), "%Y-%m-%d").date()
            except ValueError:
                return f"❌ Invalid date format: {updates.due_date}. Use YYYY-MM-DD"

        if not update_dict:
            return "ℹ️ No changes made - all fields were empty"

        # Update the task
        updated_task = service.update_task(task_id, **update_dict)

        changed_fields = ", ".join(update_dict.keys())
        return f"✅ **Updated task #{task_id}:** {changed_fields}\n\n{format_task_markdown(updated_task)}"

    elif result.action == "decline":
        return "❌ Update declined - no changes made"

    else:  # cancel
        return "🚫 Update cancelled"


@mcp.tool()
async def delete_task_interactive(ctx: Context, task_id: int) -> str:
    """Delete a task with confirmation dialog.

    This tool shows task details and asks for confirmation before deletion
    to prevent accidental data loss.

    Args:
        task_id: The ID of the task to delete
    """
    service = get_service()

    # Fetch task to show details
    task = service.get_task(task_id)
    if not task:
        return f"❌ Task #{task_id} not found"

    # Request confirmation
    result = await ctx.elicit(
        message=f"⚠️ **Confirm Deletion**\n\n{format_task_markdown(task)}\n\nThis action cannot be undone.",
        response_type=TaskDeletionConfirmation,
    )

    if result.action == "accept" and result.data.confirm:
        # Delete the task
        service.delete_task(task_id)
        return f"✅ Deleted task #{task_id}: {task.title}"

    elif result.action == "decline" or not result.data.confirm:
        return "❌ Deletion declined - task preserved"

    else:  # cancel
        return "🚫 Deletion cancelled - task preserved"


# ============================================================================
# Standard Tools (Non-Interactive)
# ============================================================================


@mcp.tool()
def create_task(
    title: str,
    description: str | None = None,
    priority: Literal["low", "medium", "high"] = "medium",
    status: Literal["todo", "in_progress", "done"] = "todo",
    due_date: str | None = None,
    tags: list[str] | None = None,
) -> str:
    """Create a new task (non-interactive version).

    Use this when you already have all the task details.
    For interactive creation with a form, use create_task_interactive instead.

    Args:
        title: Task title
        description: Detailed description
        priority: Task priority (low, medium, high)
        status: Initial status (todo, in_progress, done)
        due_date: Due date in YYYY-MM-DD format
        tags: List of tags for organization
    """
    service = get_service()

    # Parse due_date if provided
    parsed_due_date = None
    if due_date:
        try:
            parsed_due_date = datetime.strptime(due_date, "%Y-%m-%d").date()
        except ValueError:
            return f"❌ Invalid date format: {due_date}. Use YYYY-MM-DD"

    # Create the task
    task = service.create_task(
        title=title,
        description=description,
        priority=Priority(priority),
        status=TaskStatus(status),
        due_date=parsed_due_date,
        tags=tags,
    )

    return f"✅ **Created task #{task.id}:** {task.title}\n\n{format_task_markdown(task)}"


@mcp.tool()
def list_tasks(
    status: Literal["todo", "in_progress", "done", "all"] = "all",
    priority: Literal["low", "medium", "high", "all"] = "all",
    tag: str | None = None,
    overdue_only: bool = False,
) -> str:
    """List tasks with optional filtering.

    Args:
        status: Filter by status (todo, in_progress, done, all)
        priority: Filter by priority (low, medium, high, all)
        tag: Filter by tag
        overdue_only: Show only overdue tasks
    """
    service = get_service()

    # Build filters
    filters = {}
    if status != "all":
        filters["status"] = TaskStatus(status)
    if priority != "all":
        filters["priority"] = Priority(priority)
    if tag:
        filters["tag"] = tag

    # Get tasks (service returns tuple of tasks and total count)
    tasks, total = service.list_tasks(**filters)

    # Filter overdue if requested
    if overdue_only:
        today = date.today()
        tasks = [
            t
            for t in tasks
            if t.due_date
            and t.due_date < today
            and t.status not in [TaskStatus.COMPLETED, TaskStatus.ARCHIVED]
        ]

    if not tasks:
        return "📭 No tasks found matching the criteria"

    # Format output
    lines = [f"📋 **Found {len(tasks)} task(s)**\n"]

    for task in tasks:
        status_emoji = {
            TaskStatus.PENDING: "⭕",
            TaskStatus.IN_PROGRESS: "🔄",
            TaskStatus.COMPLETED: "✅",
            TaskStatus.ARCHIVED: "📦",
        }.get(task.status, "❓")

        priority_emoji = {
            Priority.HIGH: "🔴",
            Priority.MEDIUM: "🟡",
            Priority.LOW: "🟢",
        }.get(task.priority, "⚪")

        due_info = ""
        if task.due_date:
            is_overdue = task.due_date < date.today() and task.status not in [
                TaskStatus.COMPLETED,
                TaskStatus.ARCHIVED,
            ]
            due_info = f" | Due: {task.due_date}" + (" ⚠️ OVERDUE" if is_overdue else "")

        lines.append(
            f"{status_emoji} {priority_emoji} **#{task.id}** {task.title}{due_info}"
        )

    return "\n".join(lines)


@mcp.tool()
def get_task(task_id: int) -> str:
    """Get detailed information about a specific task.

    Args:
        task_id: The ID of the task to retrieve
    """
    service = get_service()
    task = service.get_task(task_id)

    if not task:
        return f"❌ Task #{task_id} not found"

    return format_task_markdown(task)


@mcp.tool()
def update_task(
    task_id: int,
    title: str | None = None,
    description: str | None = None,
    priority: Literal["low", "medium", "high"] | None = None,
    status: Literal["todo", "in_progress", "done"] | None = None,
    due_date: str | None = None,
    tags: list[str] | None = None,
) -> str:
    """Update a task's fields (non-interactive version).

    Use this when you know exactly what to change.
    For interactive updates with a form, use update_task_interactive instead.

    Args:
        task_id: The ID of the task to update
        title: New task title
        description: New description
        priority: New priority
        status: New status
        due_date: New due date in YYYY-MM-DD format
        tags: New tags
    """
    service = get_service()

    # Check task exists
    existing_task = service.get_task(task_id)
    if not existing_task:
        return f"❌ Task #{task_id} not found"

    # Build update dict
    updates = {}
    if title is not None:
        updates["title"] = title
    if description is not None:
        updates["description"] = description
    if priority is not None:
        updates["priority"] = Priority(priority)
    if status is not None:
        updates["status"] = TaskStatus(status)
    if tags is not None:
        updates["tags"] = tags

    # Parse due_date if provided
    if due_date is not None:
        try:
            updates["due_date"] = datetime.strptime(due_date, "%Y-%m-%d").date()
        except ValueError:
            return f"❌ Invalid date format: {due_date}. Use YYYY-MM-DD"

    if not updates:
        return "ℹ️ No updates provided - task unchanged"

    # Update the task
    task = service.update_task(task_id, **updates)

    changed_fields = ", ".join(updates.keys())
    return f"✅ **Updated task #{task_id}:** {changed_fields}\n\n{format_task_markdown(task)}"


@mcp.tool()
def complete_task(task_id: int) -> str:
    """Mark a task as completed.

    Args:
        task_id: The ID of the task to complete
    """
    service = get_service()

    task = service.get_task(task_id)
    if not task:
        return f"❌ Task #{task_id} not found"

    task = service.update_task(task_id, status=TaskStatus.COMPLETED)
    return f"✅ **Completed task #{task_id}:** {task.title}\n\n{format_task_markdown(task)}"


@mcp.tool()
def delete_task(task_id: int) -> str:
    """Delete a task immediately without confirmation (non-interactive version).

    ⚠️ WARNING: This permanently deletes the task without confirmation.
    For safe deletion with confirmation, use delete_task_interactive instead.

    Args:
        task_id: The ID of the task to delete
    """
    service = get_service()

    task = service.get_task(task_id)
    if not task:
        return f"❌ Task #{task_id} not found"

    title = task.title
    service.delete_task(task_id)
    return f"✅ Deleted task #{task_id}: {title}"


# ============================================================================
# Resources
# ============================================================================


@mcp.resource("tasks://stats")
def get_stats() -> str:
    """Get task statistics and overview."""
    service = get_service()

    all_tasks, total = service.list_tasks()

    if total == 0:
        return "📊 **Task Statistics**\n\nNo tasks yet. Create your first task to get started!"

    # Status breakdown
    status_counts = {}
    for task in all_tasks:
        status_counts[task.status] = status_counts.get(task.status, 0) + 1

    # Priority breakdown
    priority_counts = {}
    for task in all_tasks:
        priority_counts[task.priority] = priority_counts.get(task.priority, 0) + 1

    # Overdue tasks
    today = date.today()
    overdue = [
        t
        for t in all_tasks
        if t.due_date
        and t.due_date < today
        and t.status not in [TaskStatus.COMPLETED, TaskStatus.ARCHIVED]
    ]

    # Build stats output
    lines = [
        "📊 **Task Statistics**",
        "",
        f"**Total Tasks:** {total}",
        "",
        "**By Status:**",
        f"  ⭕ Pending: {status_counts.get(TaskStatus.PENDING, 0)}",
        f"  🔄 In Progress: {status_counts.get(TaskStatus.IN_PROGRESS, 0)}",
        f"  ✅ Completed: {status_counts.get(TaskStatus.COMPLETED, 0)}",
        f"  📦 Archived: {status_counts.get(TaskStatus.ARCHIVED, 0)}",
        "",
        "**By Priority:**",
        f"  🔴 High: {priority_counts.get(Priority.HIGH, 0)}",
        f"  🟡 Medium: {priority_counts.get(Priority.MEDIUM, 0)}",
        f"  🟢 Low: {priority_counts.get(Priority.LOW, 0)}",
    ]

    if overdue:
        lines.extend(["", f"⚠️ **Overdue Tasks:** {len(overdue)}"])

    return "\n".join(lines)


# ============================================================================
# Main Entry Point
# ============================================================================


def main():
    """Main entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
