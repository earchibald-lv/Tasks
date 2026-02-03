"""FastMCP 3.0 server for task management.

This module provides an MCP server that exposes task management functionality
to AI agents through tools with User Elicitation for interactive forms.
"""

import os
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastmcp import FastMCP, Context
from pydantic import BaseModel, Field

from taskmanager.database import get_session, init_db
from taskmanager.models import Priority, Task, TaskStatus
from taskmanager.repository_impl import SQLTaskRepository
from taskmanager.service import TaskService

# Initialize FastMCP server
mcp = FastMCP("Task Manager", version="0.1.0")

# Get default profile from environment variable or use "default"
DEFAULT_PROFILE = os.environ.get("TASKMANAGER_PROFILE", "default")

# Initialize all profile databases on startup
for profile in ["default", "dev", "test"]:
    init_db(profile)


def get_service(profile: str = DEFAULT_PROFILE) -> TaskService:
    """Create and return a TaskService instance for a specific profile.

    Args:
        profile: Database profile to use (default, dev, test)

    Returns:
        TaskService: Service instance for the specified profile
    """
    session = get_session(profile)
    repository = SQLTaskRepository(session)
    return TaskService(repository)


def mcp_status_to_task_status(mcp_status: str) -> TaskStatus:
    """Convert MCP-friendly status string to TaskStatus enum.
    
    MCP tools use simplified terminology:
    - "todo" → PENDING
    - "in_progress" → IN_PROGRESS  
    - "done" → COMPLETED
    - "cancelled" → CANCELLED (direct mapping)
    - "archived" → ARCHIVED (direct mapping)
    
    Args:
        mcp_status: Status string from MCP tool (todo, in_progress, done, cancelled, archived)
        
    Returns:
        TaskStatus: Corresponding enum value
        
    Raises:
        ValueError: If status string is invalid
    """
    status_map = {
        "todo": TaskStatus.PENDING,
        "pending": TaskStatus.PENDING,  # Allow direct use too
        "in_progress": TaskStatus.IN_PROGRESS,
        "done": TaskStatus.COMPLETED,
        "completed": TaskStatus.COMPLETED,  # Allow direct use too
        "cancelled": TaskStatus.CANCELLED,
        "archived": TaskStatus.ARCHIVED,
    }
    
    if mcp_status not in status_map:
        valid = ", ".join(sorted(status_map.keys()))
        raise ValueError(f"Invalid status '{mcp_status}'. Valid values: {valid}")
    
    return status_map[mcp_status]


def task_status_to_mcp_status(task_status: TaskStatus) -> str:
    """Convert TaskStatus enum to MCP-friendly status string.
    
    Returns simplified terminology for MCP tools:
    - PENDING → "todo"
    - IN_PROGRESS → "in_progress"
    - COMPLETED → "done"
    - CANCELLED → "cancelled"
    - ARCHIVED → "archived"
    
    Args:
        task_status: TaskStatus enum value
        
    Returns:
        str: MCP-friendly status string
    """
    reverse_map = {
        TaskStatus.PENDING: "todo",
        TaskStatus.IN_PROGRESS: "in_progress",
        TaskStatus.COMPLETED: "done",
        TaskStatus.CANCELLED: "cancelled",
        TaskStatus.ARCHIVED: "archived",
    }
    return reverse_map[task_status]


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

    if task.jira_issues:
        from taskmanager.config import get_settings
        from taskmanager.service import TaskService
        
        settings = get_settings()
        jira_url = settings.atlassian.jira_url if settings.atlassian else None
        jira_links = TaskService.format_jira_links(task.jira_issues, jira_url)
        
        if jira_links:
            lines.append("")
            lines.append("**JIRA Issues:**")
            for issue_key, url in jira_links:
                lines.append(f"- [{issue_key}]({url})")
        else:
            lines.append(f"**JIRA Issues:** {task.jira_issues}")

    if task.tags:
        lines.append(f"**Tags:** {task.tags}")

    if task.due_date:
        is_overdue = task.due_date < date.today() and task.status not in [
            TaskStatus.COMPLETED,
            TaskStatus.CANCELLED,
            TaskStatus.ARCHIVED,
        ]
        due_str = f"{task.due_date} ⚠️ OVERDUE" if is_overdue else str(task.due_date)
        lines.append(f"**Due:** {due_str}")

    lines.append("")
    if task.created_at:
        lines.append(f"**Created:** {task.created_at.strftime('%Y-%m-%d %H:%M')}")
    if task.updated_at:
        lines.append(f"**Updated:** {task.updated_at.strftime('%Y-%m-%d %H:%M')}")

    # Show workspace information if it exists
    if task.workspace_path:
        lines.extend([
            "",
            "---",
            "**🗂️ Workspace Available**",
            f"📁 Path: `{task.workspace_path}`",
            "💡 Use `get_workspace_path({})` to get the path for file operations".format(task.id)
        ])

    return "\n".join(lines)


# ============================================================================
# User Elicitation Forms (Pydantic Models)
# ============================================================================


class TaskCreationForm(BaseModel):
    """Interactive form for creating a new task."""

    title: str = Field(description="Task title (required)")
    description: str = Field(default="", description="Detailed description (optional)")
    priority: Literal["low", "medium", "high", "urgent"] = Field(
        default="medium", description="Task priority"
    )
    due_date: str = Field(default="", description="Due date in YYYY-MM-DD format (optional)")
    jira_issues: str = Field(default="", description="JIRA issue keys as CSV list (e.g., 'SRE-1234,DEVOPS-5678'). No spaces around commas. Multiple issues can be linked to one task. (optional)")
    tags: str = Field(default="", description="Tags for categorization, comma-separated (e.g., backend,api,bug-fix) (optional)")


class TaskUpdateForm(BaseModel):
    """Interactive form for updating an existing task."""

    title: str = Field(default="", description="New task title (leave empty to keep current)")
    description: str = Field(default="", description="New description (leave empty to keep current)")
    priority: str = Field(
        default="", description="New priority: low, medium, high (leave empty to keep current)"
    )
    status: str = Field(
        default="", description="New status: todo, in_progress, done, cancelled (leave empty to keep current)"
    )
    due_date: str = Field(default="", description="New due date YYYY-MM-DD (leave empty to keep current)")
    jira_issues: str = Field(default="", description="New JIRA issues as CSV list (e.g., 'SRE-1234,DEVOPS-5678'). No spaces. Leave empty to keep current. (optional)")
    tags: str = Field(default="", description="New tags (comma-separated) (leave empty to keep current)")


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
async def create_task_interactive(
    ctx: Context,
    profile: Literal["default", "dev", "test"] = DEFAULT_PROFILE,
) -> str:
    """Create a new task with an interactive form.

    This tool presents a form to collect all task details interactively,
    making it easy to create well-structured tasks with all necessary information.

    Args:
        profile: Database profile to use (default, dev, test)
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
        service = get_service(profile)
        task = service.create_task(
            title=task_data.title,
            description=task_data.description if task_data.description.strip() else None,
            priority=Priority(task_data.priority),
            due_date=parsed_due_date,
            jira_issues=task_data.jira_issues if task_data.jira_issues.strip() else None,
            tags=task_data.tags if task_data.tags.strip() else None,
        )

        return f"✅ **Created task #{task.id}:** {task.title}\n\n{format_task_markdown(task)}"

    elif result.action == "decline":
        return "❌ Task creation declined - no changes made"

    else:  # cancel
        return "🚫 Task creation cancelled"


@mcp.tool()
async def update_task_interactive(
    ctx: Context,
    task_id: int,
    profile: Literal["default", "dev", "test"] = DEFAULT_PROFILE,
) -> str:
    """Update an existing task with an interactive form showing current values.

    This tool fetches the current task and presents a form pre-filled with
    existing values, making it easy to see what you're changing.

    Args:
        task_id: The ID of the task to update
        profile: Database profile to use (default, dev, test)
    """
    service = get_service(profile)

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
                return f"❌ Invalid status: {updates.status}. Use: pending, in_progress, completed, cancelled, archived"
        if updates.due_date and updates.due_date.strip():
            try:
                update_dict["due_date"] = datetime.strptime(updates.due_date.strip(), "%Y-%m-%d").date()
            except ValueError:
                return f"❌ Invalid date format: {updates.due_date}. Use YYYY-MM-DD"
        if updates.jira_issues and updates.jira_issues.strip():
            update_dict["jira_issues"] = updates.jira_issues.strip()
        if updates.tags and updates.tags.strip():
            update_dict["tags"] = updates.tags.strip()

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
async def delete_task_interactive(
    ctx: Context,
    task_id: int,
    profile: Literal["default", "dev", "test"] = DEFAULT_PROFILE,
) -> str:
    """Delete a task with confirmation dialog.

    This tool shows task details and asks for confirmation before deletion
    to prevent accidental data loss.

    Args:
        task_id: The ID of the task to delete
        profile: Database profile to use (default, dev, test)
    """
    service = get_service(profile)

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
    priority: Literal["low", "medium", "high", "urgent"] = "medium",
    status: Literal["todo", "in_progress", "done", "cancelled", "archived"] = "todo",
    due_date: str | None = None,
    tags: list[str] | None = None,
    jira_issues: str | None = None,
    profile: Literal["default", "dev", "test"] = DEFAULT_PROFILE,
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
        jira_issues: Comma-separated (CSV) JIRA issue keys (e.g., "SRE-1234,DEVOPS-5678"). No spaces around commas. Can link multiple JIRA issues to one task.
        profile: Database profile to use (default, dev, test)
    """
    service = get_service(profile)

    # Parse due_date if provided
    parsed_due_date = None
    if due_date:
        try:
            parsed_due_date = datetime.strptime(due_date, "%Y-%m-%d").date()
        except ValueError:
            return f"❌ Invalid date format: {due_date}. Use YYYY-MM-DD"

    # Convert tags list to comma-separated string
    tags_str = None
    if tags:
        tags_str = ",".join(tags)

    # Create the task
    task = service.create_task(
        title=title,
        description=description,
        priority=Priority(priority),
        status=mcp_status_to_task_status(status),
        due_date=parsed_due_date,
        tags=tags_str,
        jira_issues=jira_issues,
    )

    return f"✅ **Created task #{task.id}:** {task.title}\n\n{format_task_markdown(task)}"


@mcp.tool()
def list_tasks(
    status: Literal["todo", "in_progress", "done", "cancelled", "archived", "all"] = "all",
    priority: Literal["low", "medium", "high", "urgent", "all"] = "all",
    tag: str | None = None,
    overdue_only: bool = False,
    profile: Literal["default", "dev", "test"] = DEFAULT_PROFILE,
) -> str:
    """List tasks with optional filtering.

    Args:
        status: Filter by status (todo, in_progress, done, all)
        priority: Filter by priority (low, medium, high, all)
        tag: Filter by tag
        overdue_only: Show only overdue tasks
        profile: Database profile to use (default, dev, test)
    """
    try:
        service = get_service(profile)

        # Build filters
        filters = {}
        if status != "all":
            filters["status"] = mcp_status_to_task_status(status)
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
                TaskStatus.CANCELLED: "❌",
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
                    TaskStatus.CANCELLED,
                    TaskStatus.ARCHIVED,
                ]
                due_info = f" | Due: {task.due_date}" + (" ⚠️ OVERDUE" if is_overdue else "")

            lines.append(
                f"{status_emoji} {priority_emoji} **#{task.id}** {task.title}{due_info}"
            )

        return "\n".join(lines)
    except ValueError as e:
        return f"❌ Error: {str(e)}"
    except Exception as e:
        return f"❌ Unexpected error: {str(e)}"


@mcp.tool()
def get_task(
    task_id: int,
    profile: Literal["default", "dev", "test"] = DEFAULT_PROFILE,
) -> str:
    """Get detailed information about a specific task.

    Args:
        task_id: The ID of the task to retrieve
        profile: Database profile to use (default, dev, test)
    """
    try:
        service = get_service(profile)
        task = service.get_task(task_id)
        return format_task_markdown(task)
    except ValueError as e:
        return f"❌ Error: {str(e)}"
    except Exception as e:
        return f"❌ Unexpected error: {str(e)}"


@mcp.tool()
def update_task(
    task_id: int,
    title: str | None = None,
    description: str | None = None,
    priority: Literal["low", "medium", "high", "urgent"] | None = None,
    status: Literal["todo", "in_progress", "done", "cancelled", "archived"] | None = None,
    due_date: str | None = None,
    tags: list[str] | None = None,
    jira_issues: str | None = None,
    profile: Literal["default", "dev", "test"] = DEFAULT_PROFILE,
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
        jira_issues: New JIRA issues as CSV list (comma-separated, no spaces). Format: "KEY-1234,KEY-5678"
        profile: Database profile to use (default, dev, test)
    """
    try:
        service = get_service(profile)

        # Build update dict
        updates = {}
        if title is not None:
            updates["title"] = title
        if description is not None:
            updates["description"] = description
        if priority is not None:
            updates["priority"] = Priority(priority)
        if status is not None:
            updates["status"] = mcp_status_to_task_status(status)
        if tags is not None:
            updates["tags"] = ",".join(tags) if tags else ""
        if jira_issues is not None:
            updates["jira_issues"] = jira_issues

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
    except ValueError as e:
        return f"❌ Error: {str(e)}"
    except Exception as e:
        return f"❌ Unexpected error: {str(e)}"


@mcp.tool()
def complete_task(
    task_id: int,
    profile: Literal["default", "dev", "test"] = DEFAULT_PROFILE,
) -> str:
    """Mark a task as completed.

    Args:
        task_id: The ID of the task to complete
        profile: Database profile to use (default, dev, test)
    """
    try:
        service = get_service(profile)
        task = service.update_task(task_id, status=TaskStatus.COMPLETED)
        return f"✅ **Completed task #{task_id}:** {task.title}\n\n{format_task_markdown(task)}"
    except ValueError as e:
        return f"❌ Error: {str(e)}"
    except Exception as e:
        return f"❌ Unexpected error: {str(e)}"


@mcp.tool()
def delete_task(
    task_id: int,
    profile: Literal["default", "dev", "test"] = DEFAULT_PROFILE,
) -> str:
    """Delete a task immediately without confirmation (non-interactive version).

    ⚠️ WARNING: This permanently deletes the task without confirmation.
    For safe deletion with confirmation, use delete_task_interactive instead.

    Args:
        task_id: The ID of the task to delete
        profile: Database profile to use (default, dev, test)
    """
    try:
        service = get_service(profile)
        task = service.get_task(task_id)
        title = task.title
        service.delete_task(task_id)
        return f"✅ Deleted task #{task_id}: {title}"
    except ValueError as e:
        return f"❌ Error: {str(e)}"
    except Exception as e:
        return f"❌ Unexpected error: {str(e)}"


# ============================================================================
# Workspace Management Tools
# ============================================================================


@mcp.tool()
def create_workspace(
    task_id: int,
    initialize_git: bool = True,
    profile: Literal["default", "dev", "test"] = DEFAULT_PROFILE,
) -> str:
    """Create a persistent workspace for a task.

    Creates a directory structure at ~/.taskmanager/workspaces/task_{id}/ with:
    - notes/ - Documentation and context files
    - code/ - Code snippets and experiments
    - logs/ - Execution logs
    - tmp/ - Temporary files

    Optionally initializes a git repository for version control.

    Args:
        task_id: The ID of the task to create workspace for
        initialize_git: Whether to initialize git repository (default: True)
        profile: Database profile to use (default, dev, test)
    """
    try:
        service = get_service(profile)
        metadata = service.create_workspace(
            task_id=task_id,
            initialize_git=initialize_git
        )

        git_status = "✓ Git initialized" if metadata["git_initialized"] else "✗ Git not initialized"

        return f"""✅ **Created workspace for task #{task_id}**

**Path:** `{metadata['workspace_path']}`
**Created:** {metadata['created_at']}
**Git:** {git_status}

**Directory Structure:**
- `notes/` - Documentation and context
- `code/` - Code experiments
- `logs/` - Execution logs
- `tmp/` - Temporary files

You can now use this workspace for task-specific file operations."""
    except ValueError as e:
        return f"❌ Error: {str(e)}"
    except Exception as e:
        return f"❌ Unexpected error: {str(e)}"


@mcp.tool()
def get_workspace_info(task_id: int,
    profile: Literal["default", "dev", "test"] = DEFAULT_PROFILE,) -> str:
    """Get information about a task's workspace.

    Returns workspace metadata including path, creation time, and git status.

    Args:
        task_id: The ID of the task
    """
    try:
        service = get_service(profile)
        metadata = service.get_workspace_info(task_id)

        if not metadata:
            return f"ℹ️ No workspace exists for task #{task_id}\n\nUse `create_workspace({task_id})` to create one."

        git_status = "✓ Yes" if metadata["git_initialized"] else "✗ No"
        last_accessed = metadata.get("last_accessed", "Never")

        return f"""📁 **Workspace for Task #{task_id}**

**Path:** `{metadata['workspace_path']}`
**Created:** {metadata['created_at']}
**Last Accessed:** {last_accessed}
**Git Initialized:** {git_status}

This workspace provides a sandboxed environment for task-specific operations."""
    except ValueError as e:
        return f"❌ Error: {str(e)}"
    except Exception as e:
        return f"❌ Unexpected error: {str(e)}"


@mcp.tool()
def get_workspace_path(task_id: int,
    profile: Literal["default", "dev", "test"] = DEFAULT_PROFILE,) -> str:
    """Get the filesystem path to a task's workspace.

    Returns the absolute path that can be used for file operations.
    This is useful for passing to other tools or file system operations.

    Args:
        task_id: The ID of the task
    """
    try:
        service = get_service(profile)
        path = service.get_workspace_path(task_id)

        if not path:
            return f"❌ No workspace exists for task #{task_id}\n\nCreate one first with `create_workspace({task_id})`"

        return str(path)
    except ValueError as e:
        return f"❌ Error: {str(e)}"
    except Exception as e:
        return f"❌ Unexpected error: {str(e)}"


@mcp.tool()
def ensure_workspace(task_id: int, initialize_git: bool = True,
    profile: Literal["default", "dev", "test"] = DEFAULT_PROFILE,) -> str:
    """Ensure a workspace exists for a task, creating it if necessary.

    This is a convenience tool that checks if a workspace exists and creates
    one if it doesn't. Safe to call multiple times - won't fail if workspace
    already exists.

    Args:
        task_id: The ID of the task
        initialize_git: Whether to initialize git if creating new workspace
    """
    try:
        service = get_service(profile)

        # Check if workspace already exists
        existing_path = service.get_workspace_path(task_id)
        if existing_path:
            return f"✓ Workspace already exists for task #{task_id}\n\n📁 Path: `{existing_path}`"

        # Create new workspace
        metadata = service.create_workspace(
            task_id=task_id,
            initialize_git=initialize_git
        )

        git_status = "✓ Git initialized" if metadata["git_initialized"] else "✗ Git not initialized"

        return f"""✅ **Created workspace for task #{task_id}**

📁 Path: `{metadata['workspace_path']}`
{git_status}

**Directory Structure:**
- `notes/` - Documentation and context
- `code/` - Code experiments
- `logs/` - Execution logs
- `tmp/` - Temporary files"""
    except ValueError as e:
        return f"❌ Error: {str(e)}"
    except Exception as e:
        return f"❌ Unexpected error: {str(e)}"


@mcp.tool()
def delete_workspace(task_id: int,
    profile: Literal["default", "dev", "test"] = DEFAULT_PROFILE,) -> str:
    """Delete a task's workspace and all its contents.

    ⚠️ WARNING: This permanently deletes all files in the workspace directory.
    This action cannot be undone.

    Args:
        task_id: The ID of the task
    """
    try:
        service = get_service(profile)

        # Check if workspace exists
        path = service.get_workspace_path(task_id)
        if not path:
            return f"ℹ️ No workspace exists for task #{task_id}"

        # Delete workspace
        deleted = service.delete_workspace(task_id)

        if deleted:
            return f"✅ Deleted workspace for task #{task_id}\n\nPath: `{path}` (removed)"
        else:
            return f"❌ Failed to delete workspace for task #{task_id}"
    except ValueError as e:
        return f"❌ Error: {str(e)}"
    except Exception as e:
        return f"❌ Unexpected error: {str(e)}"


@mcp.tool()
def search_workspace(
    task_id: int,
    query: str,
    file_pattern: str = "*",
    case_sensitive: bool = False,
    max_results: int = 50,
    profile: Literal["default", "dev", "test"] = DEFAULT_PROFILE,) -> str:
    """Search for content within a task's workspace.

    Uses fast text search to find files and content matching your query.
    Great for finding specific code, notes, or references within a workspace.

    Args:
        task_id: The ID of the task whose workspace to search
        query: Text to search for (supports regex patterns)
        file_pattern: File pattern to search (e.g., "*.py", "*.md", "notes/*")
        case_sensitive: Whether to match case exactly (default: False)
        max_results: Maximum number of results to return (default: 50)
    """
    import subprocess

    try:
        service = get_service(profile)

        # Get workspace path
        workspace_path = service.get_workspace_path(task_id)
        if not workspace_path:
            return f"❌ No workspace exists for task #{task_id}\n\nCreate one first with `ensure_workspace({task_id})`"

        if not workspace_path.exists():
            return f"❌ Workspace directory not found: {workspace_path}"

        # Build ripgrep command
        rg_args = [
            "rg",
            "--color", "never",
            "--line-number",
            "--heading",
            "--max-count", str(max_results),
        ]

        if not case_sensitive:
            rg_args.append("--ignore-case")

        # Add glob pattern if specified
        if file_pattern != "*":
            rg_args.extend(["--glob", file_pattern])

        # Exclude git and tmp directories
        rg_args.extend([
            "--glob", "!.git",
            "--glob", "!tmp/*",
            "--glob", "!*.pyc",
            "--glob", "!__pycache__",
        ])

        rg_args.extend([query, str(workspace_path)])

        # Execute search
        result = subprocess.run(
            rg_args,
            capture_output=True,
            text=True,
            timeout=10
        )

        # Handle no results
        if result.returncode == 1:
            return f"🔍 No matches found in workspace for task #{task_id}\n\n**Query:** `{query}`\n**Pattern:** `{file_pattern}`"

        # Handle errors
        if result.returncode > 1:
            return f"❌ Search error: {result.stderr}"

        # Format results
        output_lines = result.stdout.strip().split("\n")

        if not output_lines or output_lines[0] == "":
            return f"🔍 No matches found in workspace for task #{task_id}\n\n**Query:** `{query}`\n**Pattern:** `{file_pattern}`"

        # Count matches and files
        file_count = len([line for line in output_lines if line and not line.startswith(" ") and ":" in line])
        match_count = len([line for line in output_lines if line.startswith(" ")])

        result_text = f"""🔍 **Search Results for Task #{task_id}**

**Query:** `{query}`
**Pattern:** `{file_pattern}`
**Found:** {match_count} match(es) in {file_count} file(s)

---

{result.stdout.strip()}

---

💡 Tip: Use `file_pattern="*.md"` to search only markdown files, or `"notes/*"` to search only in notes/"""

        return result_text

    except subprocess.TimeoutExpired:
        return f"❌ Search timed out after 10 seconds"
    except FileNotFoundError:
        return f"❌ Search tool 'ripgrep' not found. Install with: brew install ripgrep"
    except ValueError as e:
        return f"❌ Error: {str(e)}"
    except Exception as e:
        return f"❌ Unexpected error: {str(e)}"


@mcp.tool()
def search_all_tasks(
    query: str,
    search_workspaces: bool = True,
    search_task_fields: bool = True,
    file_pattern: str = "*",
    case_sensitive: bool = False,
    status_filter: Literal["todo", "in_progress", "done", "cancelled", "archived", "all"] = "all",
    profile: Literal["default", "dev", "test"] = DEFAULT_PROFILE,) -> str:
    """Search across all tasks and their workspaces.

    Performs a comprehensive search across:
    - Task titles, descriptions, tags, and JIRA issues
    - Workspace content (notes, code, logs) if workspaces exist

    This is useful when you don't know which task contains the information
    you're looking for.

    Args:
        query: Text to search for
        search_workspaces: Whether to search workspace files (default: True)
        search_task_fields: Whether to search task metadata (default: True)
        file_pattern: File pattern for workspace search (e.g., "*.py", "*.md")
        case_sensitive: Whether to match case exactly (default: False)
        status_filter: Filter by task status (todo, in_progress, done, all)
    """
    import subprocess

    try:
        service = get_service(profile)

        # Build filters
        filters = {}
        if status_filter != "all":
            filters["status"] = mcp_status_to_task_status(status_filter)

        # Get all tasks
        tasks, total = service.list_tasks(**filters, limit=100)

        if total == 0:
            return "📭 No tasks found"

        task_matches = []
        workspace_matches = []

        # Search task metadata
        if search_task_fields:
            query_lower = query.lower() if not case_sensitive else query

            for task in tasks:
                matches = []

                # Check title
                title_check = task.title.lower() if not case_sensitive else task.title
                if query_lower in title_check:
                    matches.append("title")

                # Check description
                if task.description:
                    desc_check = task.description.lower() if not case_sensitive else task.description
                    if query_lower in desc_check:
                        matches.append("description")

                # Check tags
                if task.tags:
                    tags_check = task.tags.lower() if not case_sensitive else task.tags
                    if query_lower in tags_check:
                        matches.append("tags")

                # Check JIRA issues
                if task.jira_issues:
                    jira_check = task.jira_issues.lower() if not case_sensitive else task.jira_issues
                    if query_lower in jira_check:
                        matches.append("JIRA")

                if matches:
                    task_matches.append({
                        "task": task,
                        "fields": matches
                    })

        # Search workspaces
        if search_workspaces:
            for task in tasks:
                if not task.workspace_path or not task.id:
                    continue

                workspace_path = service.get_workspace_path(task.id)
                if not workspace_path or not workspace_path.exists():
                    continue

                try:
                    # Build ripgrep command
                    rg_args = [
                        "rg",
                        "--color", "never",
                        "--files-with-matches",
                        "--max-count", "5",
                    ]

                    if not case_sensitive:
                        rg_args.append("--ignore-case")

                    if file_pattern != "*":
                        rg_args.extend(["--glob", file_pattern])

                    rg_args.extend([
                        "--glob", "!.git",
                        "--glob", "!tmp/*",
                        "--glob", "!*.pyc",
                        "--glob", "!__pycache__",
                    ])

                    rg_args.extend([query, str(workspace_path)])

                    result = subprocess.run(
                        rg_args,
                        capture_output=True,
                        text=True,
                        timeout=5
                    )

                    if result.returncode == 0:
                        matched_files = result.stdout.strip().split("\n")
                        matched_files = [f.replace(str(workspace_path) + "/", "") for f in matched_files if f]

                        workspace_matches.append({
                            "task": task,
                            "files": matched_files
                        })

                except (subprocess.TimeoutExpired, FileNotFoundError):
                    continue

        # Format results
        if not task_matches and not workspace_matches:
            return f"""🔍 **Search Results: No matches found**

**Query:** `{query}`
**Searched:** {total} task(s)
**Workspaces:** {"Yes" if search_workspaces else "No"}
**Task Fields:** {"Yes" if search_task_fields else "No"}"""

        lines = [
            f"🔍 **Search Results for:** `{query}`",
            "",
            f"**Searched:** {total} task(s)",
            f"**Found:** {len(task_matches)} task metadata match(es), {len(workspace_matches)} workspace match(es)",
            ""
        ]

        # Show task metadata matches
        if task_matches:
            lines.extend([
                "## 📋 Task Metadata Matches",
                ""
            ])

            for match in task_matches[:20]:
                task = match["task"]
                fields = ", ".join(match["fields"])

                status_emoji = {
                    TaskStatus.PENDING: "⭕",
                    TaskStatus.IN_PROGRESS: "🔄",
                    TaskStatus.COMPLETED: "✅",
                    TaskStatus.CANCELLED: "❌",
                    TaskStatus.ARCHIVED: "📦",
                }.get(task.status, "❓")

                lines.append(f"{status_emoji} **Task #{task.id}**: {task.title}")
                lines.append(f"   Matched in: {fields}")
                if task.workspace_path:
                    lines.append(f"   📁 Has workspace")
                lines.append("")

        # Show workspace matches
        if workspace_matches:
            lines.extend([
                "## 📂 Workspace Content Matches",
                ""
            ])

            for match in workspace_matches[:20]:
                task = match["task"]
                files = match["files"]

                status_emoji = {
                    TaskStatus.PENDING: "⭕",
                    TaskStatus.IN_PROGRESS: "🔄",
                    TaskStatus.COMPLETED: "✅",
                    TaskStatus.CANCELLED: "❌",
                    TaskStatus.ARCHIVED: "📦",
                }.get(task.status, "❓")

                lines.append(f"{status_emoji} **Task #{task.id}**: {task.title}")
                lines.append(f"   📄 Found in {len(files)} file(s):")
                for f in files[:5]:
                    lines.append(f"      - `{f}`")
                if len(files) > 5:
                    lines.append(f"      ... and {len(files) - 5} more")
                lines.append("")

        lines.extend([
            "---",
            f"💡 Use `get_task(task_id)` to view task details",
            f"💡 Use `search_workspace(task_id, '{query}')` to see specific matches"
        ])

        return "\n".join(lines)

    except FileNotFoundError:
        return f"❌ Search tool 'ripgrep' not found. Install with: brew install ripgrep"
    except ValueError as e:
        return f"❌ Error: {str(e)}"
    except Exception as e:
        return f"❌ Unexpected error: {str(e)}"


@mcp.tool()
def list_workspace_files(
    task_id: int,
    subdirectory: str = "",
    file_pattern: str = "*",
    profile: Literal["default", "dev", "test"] = DEFAULT_PROFILE,) -> str:
    """List files in a task's workspace.

    Browse the contents of a workspace directory to see what files are available.

    Args:
        task_id: The ID of the task
        subdirectory: Subdirectory to list (e.g., "notes", "code", "logs")
        file_pattern: Pattern to filter files (e.g., "*.py", "*.md")
    """
    import datetime

    try:
        service = get_service(profile)

        # Get workspace path
        workspace_path = service.get_workspace_path(task_id)
        if not workspace_path:
            return f"❌ No workspace exists for task #{task_id}"

        # Build target path
        target_path = workspace_path / subdirectory if subdirectory else workspace_path

        if not target_path.exists():
            return f"❌ Directory not found: {target_path}"

        # Get matching files
        if file_pattern == "*":
            files = list(target_path.rglob("*"))
        else:
            files = list(target_path.rglob(file_pattern))

        # Filter to only files (not directories)
        files = [f for f in files if f.is_file()]

        # Exclude git and cache files
        files = [f for f in files if ".git" not in str(f) and "__pycache__" not in str(f)]

        if not files:
            return f"📂 No files found in workspace\n\n**Path:** `{target_path}`\n**Pattern:** `{file_pattern}`"

        # Sort by modification time (most recent first)
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

        # Format results
        lines = [
            f"📂 **Workspace Files for Task #{task_id}**",
            "",
            f"**Path:** `{target_path}`",
            f"**Pattern:** `{file_pattern}`",
            f"**Found:** {len(files)} file(s)",
            "",
            "---",
            ""
        ]

        for f in files[:50]:  # Limit to 50 files
            relative_path = f.relative_to(workspace_path)
            size = f.stat().st_size
            modified = datetime.datetime.fromtimestamp(f.stat().st_mtime)

            # Format size
            if size < 1024:
                size_str = f"{size}B"
            elif size < 1024 * 1024:
                size_str = f"{size / 1024:.1f}KB"
            else:
                size_str = f"{size / (1024 * 1024):.1f}MB"

            lines.append(f"📄 `{relative_path}` - {size_str} - {modified.strftime('%Y-%m-%d %H:%M')}")

        if len(files) > 50:
            lines.append(f"\n... and {len(files) - 50} more files")

        return "\n".join(lines)

    except ValueError as e:
        return f"❌ Error: {str(e)}"
    except Exception as e:
        return f"❌ Unexpected error: {str(e)}"


# ============================================================================
# Resources
# ============================================================================


@mcp.resource("tasks://schema/status")
def get_status_enum() -> str:
    """Get available TaskStatus enum values with descriptions.

    This resource helps LLM agents understand valid status values
    without trial and error when creating or updating tasks.
    """
    lines = [
        "# Task Status Values",
        "",
        "Valid status values for tasks in the system:",
        "",
        "## Available Status Values",
        "",
        "- **pending** - Task not yet started (default for new tasks)",
        "- **in_progress** - Currently working on this task",
        "- **completed** - Task finished successfully",
        "- **cancelled** - Task abandoned or no longer needed",
        "- **archived** - Old/inactive task kept for records",
        "",
        "## Usage in MCP Tools",
        "",
        "When using MCP tools, note the status parameter mapping:",
        "- MCP tools accept: `todo`, `in_progress`, `done`",
        "- Database stores: `pending`, `in_progress`, `completed`",
        "",
        "**Mapping:**",
        "- `todo` → `pending`",
        "- `in_progress` → `in_progress`",
        "- `done` → `completed`",
        "",
        "## CLI Usage",
        "",
        "The CLI uses the full status names:",
        "```bash",
        "tasks add \"My task\" --status pending",
        "tasks update 1 --status in_progress",
        "tasks update 1 --status completed",
        "```",
    ]

    return "\n".join(lines)


@mcp.resource("tasks://schema/priority")
def get_priority_enum() -> str:
    """Get available Priority enum values with descriptions.

    This resource helps LLM agents understand valid priority values
    when creating or updating tasks.
    """
    lines = [
        "# Task Priority Values",
        "",
        "Valid priority levels for tasks in the system:",
        "",
        "## Available Priority Values",
        "",
        "- **low** - Nice to have, no urgency",
        "- **medium** - Normal priority (default for new tasks)",
        "- **high** - Important, should be addressed soon",
        "- **urgent** - Critical/time-sensitive, requires immediate attention",
        "",
        "## Usage Examples",
        "",
        "**MCP Tools:**",
        "```python",
        'create_task(title="Fix bug", priority="high")',
        'update_task(task_id=1, priority="urgent")',
        "```",
        "",
        "**CLI:**",
        "```bash",
        'tasks add "Fix bug" --priority high',
        "tasks update 1 --priority urgent",
        "```",
    ]

    return "\n".join(lines)


@mcp.resource("tasks://tools")
def get_available_tools() -> str:
    """Get comprehensive list of all available MCP tools.

    This resource provides a complete reference of task management
    functionality available through the MCP server.
    """
    lines = [
        "# Available MCP Tools",
        "",
        "Complete reference of task management tools available in this MCP server.",
        "",
        "## Task CRUD Operations",
        "",
        "### create_task_interactive(profile)",
        "Create a new task with an interactive form. Prompts user for all task details.",
        "",
        "### create_task(title, description, priority, status, due_date, tags, jira_issues, profile)",
        "Create a new task non-interactively. Use when you have all details upfront.",
        "",
        "### update_task_interactive(task_id, profile)",
        "Update an existing task with an interactive form showing current values.",
        "",
        "### update_task(task_id, title, description, priority, status, due_date, tags, jira_issues, profile)",
        "Update a task non-interactively. Only provide fields you want to change.",
        "",
        "### get_task(task_id, profile)",
        "Get detailed information about a specific task.",
        "",
        "### list_tasks(status, priority, tag, limit, offset, profile)",
        "List tasks with optional filtering by status, priority, or tag.",
        "",
        "### complete_task(task_id, profile)",
        "Mark a task as completed (shortcut for update with status='done').",
        "",
        "### delete_task_interactive(task_id, profile)",
        "Delete a task with confirmation dialog showing task details.",
        "",
        "### delete_task(task_id, profile)",
        "Delete a task immediately without confirmation (use with caution).",
        "",
        "## Workspace Management",
        "",
        "### create_workspace(task_id, initialize_git, profile)",
        "Create a persistent workspace directory for a task with notes/, code/, logs/, tmp/ folders.",
        "",
        "### ensure_workspace(task_id, initialize_git, profile)",
        "Ensure a workspace exists, creating it if needed. Safe to call multiple times.",
        "",
        "### get_workspace_info(task_id, profile)",
        "Get workspace metadata including path, creation time, and git status.",
        "",
        "### get_workspace_path(task_id, profile)",
        "Get the filesystem path to a task's workspace for file operations.",
        "",
        "### delete_workspace(task_id, profile)",
        "Delete a task's workspace and all its contents permanently.",
        "",
        "### list_workspace_files(task_id, subdirectory, file_pattern, profile)",
        "Browse files in a workspace directory with optional pattern filtering.",
        "",
        "### search_workspace(task_id, query, file_pattern, case_sensitive, max_results, profile)",
        "Search for content within a task's workspace using regex patterns.",
        "",
        "## Search Operations",
        "",
        "### search_all_tasks(query, search_workspaces, search_task_fields, file_pattern, case_sensitive, status_filter, profile)",
        "Search across all tasks and their workspaces comprehensively.",
        "",
        "## Profiles",
        "",
        "All tools support a `profile` parameter to select which database to use:",
        "- **default** - Main task database (~/.taskmanager/tasks.db)",
        "- **dev** - Development/testing tasks (~/.taskmanager/tasks_dev.db)",
        "- **test** - Test tasks (~/.taskmanager/tasks_test.db)",
        "",
        "## Status & Priority Values",
        "",
        "See these resources for valid values:",
        "- `tasks://schema/status` - Available status values",
        "- `tasks://schema/priority` - Available priority levels",
    ]

    return "\n".join(lines)


@mcp.resource("tasks://workspaces")
def list_workspaces() -> str:
    """List all tasks that have workspaces."""
    service = get_service()

    # Get all tasks with workspaces
    all_tasks, _ = service.list_tasks(limit=100)
    tasks_with_workspaces = [t for t in all_tasks if t.workspace_path]

    if not tasks_with_workspaces:
        return "📂 **Task Workspaces**\n\nNo workspaces created yet.\n\nCreate a workspace for a task with `create_workspace(task_id)`"

    lines = [
        "📂 **Task Workspaces**",
        "",
        f"Found {len(tasks_with_workspaces)} task(s) with workspaces:",
        ""
    ]

    for task in tasks_with_workspaces:
        status_emoji = {
            TaskStatus.PENDING: "⭕",
            TaskStatus.IN_PROGRESS: "🔄",
            TaskStatus.COMPLETED: "✅",
            TaskStatus.CANCELLED: "❌",
            TaskStatus.ARCHIVED: "📦",
        }.get(task.status, "❓")

        lines.append(f"{status_emoji} **Task #{task.id}**: {task.title}")
        lines.append(f"   📁 `{task.workspace_path}`")
        lines.append("")

    lines.extend([
        "---",
        "💡 Use `get_workspace_path(task_id)` to get a path for file operations"
    ])

    return "\n".join(lines)


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
        and t.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.ARCHIVED]
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
# Prompts
# ============================================================================


@mcp.prompt(
    name="newTask",
    description="Guide user through creating a new task with natural language",
)
def new_task_prompt(task_type: str = "feature") -> str:
    """Interactive prompt template for creating a new task.

    Args:
        task_type: Type of task to create (feature, bug, docs, chore, test)
    """
    type_templates = {
        "feature": {
            "title": "feat: Add new capability",
            "example": "User authentication, API endpoint, UI component",
        },
        "bug": {
            "title": "fix: Resolve issue with X",
            "example": "Login fails on mobile, API returns 500 error",
        },
        "docs": {
            "title": "docs: Update documentation for X",
            "example": "API reference, README, user guide",
        },
        "chore": {
            "title": "chore: Improve X",
            "example": "Refactor code, update dependencies, cleanup",
        },
        "test": {
            "title": "test: Add tests for X",
            "example": "Unit tests, integration tests, E2E tests",
        },
    }

    template_info = type_templates.get(
        task_type, type_templates["feature"]
    )

    return f"""I'll help you create a new {task_type} task. Let's gather the details:

**1. Task Title** (brief and actionable)
   Example: {template_info['title']}
   Common patterns: {template_info['example']}

**2. Description** (what needs to be done)
   - What's the goal?
   - What are the acceptance criteria?
   - Any technical notes or constraints?

**3. Priority** 
   - `low`: Nice to have, no urgency
   - `medium`: Should be done soon (default)
   - `high`: Important, needs attention
   - `urgent`: Critical, immediate action

**4. JIRA Issues** (optional)
   - Link to related JIRA tickets (e.g., SRE-1234, DEVOPS-5678)
   - Use comma-separated format

**5. Due Date** (optional)
   - Format: YYYY-MM-DD
   - When should this be completed?

**6. Tags** (optional)
   - Categorize the task (e.g., backend, frontend, infrastructure)

Please provide these details and I'll create the task for you!"""


@mcp.prompt(
    name="updateTask",
    description="Guide user through updating an existing task",
)
def update_task_prompt(task_id: int) -> str:
    """Interactive prompt for updating a task.

    Args:
        task_id: ID of the task to update
    """
    return f"""I'll help you update task #{task_id}. What would you like to change?

**Available Updates:**

1. **Title** - Make it more clear or actionable
2. **Description** - Add details, clarify requirements, update progress
3. **Status** - Change workflow state:
   - `pending` → Task is pending
   - `in_progress` → Currently working on it
   - `completed` → Finished
   - `cancelled` → Abandoned/no longer needed
   - `archived` → Old/inactive

4. **Priority** - Adjust urgency:
   - `low`, `medium`, `high`, `urgent`

5. **JIRA Issues** - Link or unlink JIRA tickets:
   - Add: Comma-separated list (SRE-1234, DEVOPS-5678)
   - Remove: Use --clear-jira flag

6. **Due Date** - Set or change deadline (YYYY-MM-DD format)

7. **Tags** - Update categorization

First, let me show you the current task details. Then tell me what you'd like to update!"""


@mcp.prompt(
    name="reviewTasks",
    description="Prompt for reviewing and prioritizing tasks",
)
def review_tasks_prompt(
    focus: str = "all",
) -> str:
    """Generate a prompt for reviewing tasks.

    Args:
        focus: What to focus on (all, overdue, high-priority, in-progress)
    """
    focus_guidance = {
        "all": "Let's review all your tasks and organize them by priority and status.",
        "overdue": "Let's review your overdue tasks and create a plan to get back on track.",
        "high-priority": "Let's review your high-priority tasks and ensure they're on track.",
        "in-progress": "Let's review what you're currently working on and check progress.",
    }

    guidance = focus_guidance.get(focus, focus_guidance["all"])

    return f"""📋 **Task Review Session**

{guidance}

**Review Process:**

1. **Current State** - Show me your {focus} tasks
2. **Assessment** - For each task, let's check:
   - Is the priority still correct?
   - Is the status accurate?
   - Are there blockers?
   - Should we adjust due dates?

3. **Actions** - What needs to happen:
   - Tasks to complete
   - Tasks to reprioritize
   - Tasks to break down
   - Tasks to delegate or archive

4. **Plan** - Create actionable next steps

Let's start by listing your {focus} tasks!"""


@mcp.prompt(
    name="planWork",
    description="Help plan and break down work into manageable tasks",
)
def plan_work_prompt(
    project: str = "current work",
) -> str:
    """Generate a prompt for work planning.

    Args:
        project: Name or description of the project to plan
    """
    return f"""🎯 **Work Planning for: {project}**

Let's break down this work into manageable, trackable tasks.

**Planning Steps:**

1. **Objective** - What's the end goal?
   - What problem are we solving?
   - What's the definition of done?

2. **Scope** - What's included and excluded?
   - Core features vs. nice-to-haves
   - Dependencies and constraints

3. **Break Down** - Divide into tasks:
   - Each task should be completable in 1-3 days
   - Tasks should have clear acceptance criteria
   - Consider dependencies between tasks

4. **Prioritize** - Order the tasks:
   - What must be done first? (dependencies)
   - What's most valuable? (impact)
   - What's most urgent? (deadlines)

5. **Estimate** - Set due dates:
   - Be realistic with time estimates
   - Account for meetings and interruptions
   - Add buffer for unknowns

Tell me about {project} and I'll help you create the task breakdown!"""


@mcp.prompt(
    name="dailyStandup",
    description="Generate a daily standup report from your tasks",
)
def daily_standup_prompt() -> str:
    """Generate a prompt for daily standup format."""
    return """📅 **Daily Standup Report**

Let me help you prepare your standup update based on your tasks.

**Standup Format:**

**Yesterday:**
- What tasks did I complete? (completed tasks from last 1-2 days)
- What progress did I make? (updates on in-progress tasks)

**Today:**
- What am I working on? (current in-progress tasks)
- What do I plan to complete? (top priorities for today)

**Blockers:**
- Am I blocked on anything? (tasks with no progress, waiting on others)
- Do I need help? (high-priority tasks at risk)

**This Week:**
- What are my key deliverables? (tasks due this week)
- Am I on track? (overall progress assessment)

Let's generate your standup by looking at your recent task activity!"""


@mcp.prompt(
    name="workOnTask",
    description="Start working on a task with automatic workspace setup",
)
def work_on_task_prompt(task_id: int) -> str:
    """Generate a prompt for working on a task with workspace context.

    Args:
        task_id: ID of the task to work on
    """
    return f"""🚀 **Starting Work on Task #{task_id}**

Let me set up your working environment:

**Step 1: Load Task Context**
- Fetch task details with `get_task({task_id})`
- Review description, requirements, and current status

**Step 2: Ensure Workspace**
- Use `ensure_workspace({task_id})` to create/verify workspace
- This gives you a dedicated directory for:
  - 📝 `notes/` - Documentation and planning
  - 💻 `code/` - Code experiments and snippets
  - 📊 `logs/` - Execution logs and debugging
  - 🗑️ `tmp/` - Temporary files

**Step 3: Set Working Directory**
- Get workspace path with `get_workspace_path({task_id})`
- All file operations should be scoped to this directory
- Keeps task work isolated and organized

**Step 4: Begin Work**
- Create a notes/plan.md with approach
- Store any code experiments in code/
- Log progress and decisions in notes/
- Use git commits (workspace has git initialized)

**Step 5: Track Progress**
- Update task status: `update_task({task_id}, status="in_progress")`
- Add notes to task description as you work
- When done: `update_task({task_id}, status="completed")`

Let's get started! First, I'll load the task and set up your workspace."""


@mcp.prompt(
    name="taskReport",
    description="Generate a comprehensive task status report",
)
def task_report_prompt(
    period: str = "week",
) -> str:
    """Generate a prompt for task reporting.

    Args:
        period: Reporting period (day, week, sprint, month)
    """
    period_context = {
        "day": ("today", "yesterday", "daily"),
        "week": ("this week", "last week", "weekly"),
        "sprint": ("this sprint", "last sprint", "sprint"),
        "month": ("this month", "last month", "monthly"),
    }

    current, previous, adj = period_context.get(
        period, period_context["week"]
    )

    return f"""📊 **{adj.title()} Task Report**

Let me generate a comprehensive report of your task activity.

**Report Sections:**

1. **Completed** ({current})
   - Tasks finished {current}
   - What was delivered?

2. **In Progress** (current)
   - Tasks actively being worked on
   - Expected completion dates

3. **Blocked/At Risk**
   - Tasks not making progress
   - Tasks past due date
   - What's preventing completion?

4. **Planned** (upcoming)
   - High-priority tasks starting soon
   - Tasks due {current}

5. **Metrics**
   - Completion rate: X tasks completed
   - On-time delivery: X% met deadlines
   - Task distribution: by priority, by status

6. **Insights**
   - What went well?
   - What needs attention?
   - Recommended actions

Let's generate your {adj} report!"""


# ============================================================================
# Time Awareness Tools
# ============================================================================


@mcp.tool()
def get_current_time(timezone: str = "UTC") -> str:
    """Get current timestamp with timezone information.
    
    Provides agents with accurate time awareness for schedule operations,
    deadline management, and time-sensitive workflows.
    
    Args:
        timezone: Timezone name (e.g., "UTC", "America/New_York", "Europe/London")
                 Defaults to UTC. Use standard IANA timezone names.
    
    Returns:
        JSON string with current time information including:
        - timestamp: ISO 8601 formatted datetime
        - timezone: Timezone name
        - unix_timestamp: Unix epoch timestamp
        - day_of_week: Day name (Monday, Tuesday, etc.)
        - is_weekend: Boolean indicating if it's weekend
    """
    try:
        tz = ZoneInfo(timezone)
    except Exception:
        return f"❌ Invalid timezone: {timezone}\n\nUse IANA timezone names like: UTC, America/New_York, Europe/London, Asia/Tokyo"
    
    now = datetime.now(tz)
    
    result = {
        "timestamp": now.isoformat(),
        "timezone": timezone,
        "unix_timestamp": int(now.timestamp()),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "day_of_week": now.strftime("%A"),
        "is_weekend": now.weekday() >= 5,
        "formatted": now.strftime("%A, %B %d, %Y at %I:%M %p %Z")
    }
    
    lines = [
        f"🕐 **Current Time**",
        f"",
        f"**{result['formatted']}**",
        f"",
        f"- **Date:** {result['date']}",
        f"- **Time:** {result['time']}",
        f"- **Day:** {result['day_of_week']}" + (" (Weekend)" if result['is_weekend'] else ""),
        f"- **Timezone:** {timezone}",
        f"- **Unix Timestamp:** {result['unix_timestamp']}",
        f"",
        f"**ISO 8601:** `{result['timestamp']}`"
    ]
    
    return "\n".join(lines)


@mcp.tool()
def format_datetime(
    timestamp: str,
    format_string: str = "%Y-%m-%d %H:%M:%S",
    source_timezone: str = "UTC",
    target_timezone: str = "UTC"
) -> str:
    """Format and convert datetime strings.
    
    Parses datetime strings and reformats them according to specifications.
    Supports timezone conversion.
    
    Args:
        timestamp: Input datetime string (ISO 8601 format recommended)
        format_string: Output format using Python strftime codes
                      Examples: "%Y-%m-%d", "%B %d, %Y", "%I:%M %p"
        source_timezone: Timezone of input timestamp (default: UTC)
        target_timezone: Timezone for output (default: UTC)
    
    Returns:
        Formatted datetime string or error message
    """
    try:
        # Parse the input timestamp
        if 'T' in timestamp or '+' in timestamp or timestamp.endswith('Z'):
            # ISO 8601 format
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        else:
            # Try common formats
            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"]:
                try:
                    dt = datetime.strptime(timestamp, fmt)
                    break
                except ValueError:
                    continue
            else:
                raise ValueError("Could not parse timestamp")
        
        # Add source timezone if naive
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo(source_timezone))
        
        # Convert to target timezone
        if target_timezone != source_timezone:
            dt = dt.astimezone(ZoneInfo(target_timezone))
        
        formatted = dt.strftime(format_string)
        
        return f"✓ Formatted: **{formatted}**\n\nTimezone: {target_timezone}"
        
    except Exception as e:
        return f"❌ Error formatting datetime: {str(e)}\n\nTip: Use ISO 8601 format (YYYY-MM-DDTHH:MM:SS) for best results"


@mcp.tool()
def calculate_time_delta(
    start: str,
    end: str = "",
    timezone: str = "UTC"
) -> str:
    """Calculate time difference between two dates/times.
    
    Computes duration between two timestamps, or from a timestamp to now.
    Useful for deadline calculations, time tracking, and schedule planning.
    
    Args:
        start: Start datetime (ISO 8601 or YYYY-MM-DD format)
        end: End datetime (ISO 8601 or YYYY-MM-DD format). 
             If empty, uses current time.
        timezone: Timezone for calculations (default: UTC)
    
    Returns:
        Human-readable time difference with breakdown
    """
    try:
        tz = ZoneInfo(timezone)
        
        # Parse start time
        if 'T' in start or '+' in start or start.endswith('Z'):
            start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
        else:
            start_dt = datetime.fromisoformat(start + "T00:00:00")
        
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=tz)
        
        # Parse or get end time
        if end:
            if 'T' in end or '+' in end or end.endswith('Z'):
                end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
            else:
                end_dt = datetime.fromisoformat(end + "T00:00:00")
            
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=tz)
        else:
            end_dt = datetime.now(tz)
            end = "now"
        
        # Calculate delta
        delta = end_dt - start_dt
        
        # Break down the time difference
        total_seconds = int(delta.total_seconds())
        is_past = total_seconds < 0
        total_seconds = abs(total_seconds)
        
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        # Build human-readable output
        parts = []
        if days > 0:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes > 0:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        if seconds > 0 and not parts:  # Only show seconds if no larger units
            parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
        
        readable = ", ".join(parts) if parts else "0 seconds"
        direction = "ago" if is_past else "from now"
        
        lines = [
            f"⏱️ **Time Delta**",
            f"",
            f"**{readable}** {direction}",
            f"",
            f"- **Start:** {start_dt.strftime('%Y-%m-%d %H:%M:%S %Z')}",
            f"- **End:** {end if end != 'now' else end_dt.strftime('%Y-%m-%d %H:%M:%S %Z')}",
            f"",
            f"**Breakdown:**",
            f"- Days: {days}",
            f"- Hours: {hours}",
            f"- Minutes: {minutes}",
            f"- Total seconds: {total_seconds:,}",
        ]
        
        return "\n".join(lines)
        
    except Exception as e:
        return f"❌ Error calculating time delta: {str(e)}\n\nTip: Use ISO 8601 format (YYYY-MM-DDTHH:MM:SS) or YYYY-MM-DD"


# ============================================================================
# Main Entry Point
# ============================================================================


def main():
    """Main entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
