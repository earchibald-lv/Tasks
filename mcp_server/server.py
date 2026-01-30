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

    if task.jira_issues:
        from taskmanager.config import get_settings
        from taskmanager.service import TaskService
        
        settings = get_settings()
        jira_links = TaskService.format_jira_links(task.jira_issues, settings.jira.jira_url)
        
        if jira_links:
            lines.append("")
            lines.append("**JIRA Issues:**")
            for issue_key, url in jira_links:
                lines.append(f"- [{issue_key}]({url})")
        else:
            lines.append(f"**JIRA Issues:** {task.jira_issues}")

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
    jira_issues: str = Field(default="", description="JIRA issue keys, comma-separated (e.g., SRE-1234,DEVOPS-5678) (optional)")


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
    jira_issues: str = Field(default="", description="New JIRA issues (comma-separated) (leave empty to keep current)")


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
            jira_issues=task_data.jira_issues if task_data.jira_issues.strip() else None,
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
                return f"❌ Invalid status: {updates.status}. Use: pending, in_progress, completed, cancelled, archived"
        if updates.due_date and updates.due_date.strip():
            try:
                update_dict["due_date"] = datetime.strptime(updates.due_date.strip(), "%Y-%m-%d").date()
            except ValueError:
                return f"❌ Invalid date format: {updates.due_date}. Use YYYY-MM-DD"
        if updates.jira_issues and updates.jira_issues.strip():
            update_dict["jira_issues"] = updates.jira_issues.strip()

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
    jira_issues: str | None = None,
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
        jira_issues: Comma-separated JIRA issue keys (e.g., "SRE-1234,DEVOPS-5678")
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
        jira_issues=jira_issues,
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
    try:
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
def get_task(task_id: int) -> str:
    """Get detailed information about a specific task.

    Args:
        task_id: The ID of the task to retrieve
    """
    try:
        service = get_service()
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
    priority: Literal["low", "medium", "high"] | None = None,
    status: Literal["todo", "in_progress", "done"] | None = None,
    due_date: str | None = None,
    tags: list[str] | None = None,
    jira_issues: str | None = None,
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
        jira_issues: New JIRA issues (comma-separated)
    """
    try:
        service = get_service()

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
def complete_task(task_id: int) -> str:
    """Mark a task as completed.

    Args:
        task_id: The ID of the task to complete
    """
    try:
        service = get_service()
        task = service.update_task(task_id, status=TaskStatus.COMPLETED)
        return f"✅ **Completed task #{task_id}:** {task.title}\n\n{format_task_markdown(task)}"
    except ValueError as e:
        return f"❌ Error: {str(e)}"
    except Exception as e:
        return f"❌ Unexpected error: {str(e)}"


@mcp.tool()
def delete_task(task_id: int) -> str:
    """Delete a task immediately without confirmation (non-interactive version).

    ⚠️ WARNING: This permanently deletes the task without confirmation.
    For safe deletion with confirmation, use delete_task_interactive instead.

    Args:
        task_id: The ID of the task to delete
    """
    try:
        service = get_service()
        task = service.get_task(task_id)
        title = task.title
        service.delete_task(task_id)
        return f"✅ Deleted task #{task_id}: {title}"
    except ValueError as e:
        return f"❌ Error: {str(e)}"
    except Exception as e:
        return f"❌ Unexpected error: {str(e)}"


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
# Main Entry Point
# ============================================================================


def main():
    """Main entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
