"""FastMCP server for task management.

This module provides an MCP server that exposes task management functionality
to AI agents through tools, resources, and prompts.
"""

from datetime import date, datetime

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Resource, TextContent, Tool

from taskmanager.database import get_session, init_db
from taskmanager.models import Priority, Task, TaskStatus
from taskmanager.repository_impl import SQLTaskRepository
from taskmanager.service import TaskService

# Initialize the MCP server
app = Server("tasks_mcp")


def get_service() -> TaskService:
    """Create and return a TaskService instance."""
    init_db()
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
            TaskStatus.COMPLETED, TaskStatus.ARCHIVED
        ]
        due_str = f"{task.due_date} ⚠️ OVERDUE" if is_overdue else str(task.due_date)
        lines.append(f"**Due:** {due_str}")

    lines.extend([
        "",
        f"**Created:** {task.created_at.strftime('%Y-%m-%d %H:%M')}",
    ])

    if task.updated_at:
        lines.append(f"**Updated:** {task.updated_at.strftime('%Y-%m-%d %H:%M')}")

    return "\n".join(lines)


def format_task_list_markdown(tasks: list, total: int) -> str:
    """Format a list of tasks as Markdown."""
    if not tasks:
        return "No tasks found."

    lines = [f"# Tasks ({len(tasks)} of {total})", ""]

    for task in tasks:
        status_icons = {
            TaskStatus.PENDING: "○",
            TaskStatus.IN_PROGRESS: "◐",
            TaskStatus.COMPLETED: "✓",
            TaskStatus.ARCHIVED: "✖",
        }
        icon = status_icons.get(task.status, "?")

        due_str = ""
        if task.due_date:
            is_overdue = task.due_date < date.today() and task.status not in [
                TaskStatus.COMPLETED, TaskStatus.ARCHIVED
            ]
            due_str = f" (due: {task.due_date}{'⚠️' if is_overdue else ''})"

        lines.append(f"- {icon} **#{task.id}**: {task.title}{due_str}")
        if task.description:
            lines.append(f"  - {task.description[:100]}...")
        lines.append(f"  - Priority: {task.priority.value} | Status: {task.status.value}")
        lines.append("")

    return "\n".join(lines)


# Tools - AI-invocable functions
@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name="tasks_create_task",
            description="Create a new task with title and optional details",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Task title (required)",
                    },
                    "description": {
                        "type": "string",
                        "description": "Task description (optional)",
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "urgent"],
                        "description": "Task priority (default: medium)",
                    },
                    "due_date": {
                        "type": "string",
                        "description": "Due date in YYYY-MM-DD format (optional)",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["pending", "in_progress", "completed", "archived"],
                        "description": "Initial status (default: pending)",
                    },
                },
                "required": ["title"],
            },
        ),
        Tool(
            name="tasks_get_task",
            description="Get details of a specific task by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "ID of the task to retrieve",
                    },
                },
                "required": ["task_id"],
            },
        ),
        Tool(
            name="tasks_list_tasks",
            description="List tasks with optional filtering and pagination",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["pending", "in_progress", "completed", "archived"],
                        "description": "Filter by status (optional)",
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "urgent"],
                        "description": "Filter by priority (optional)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of tasks to return (default: 20)",
                        "default": 20,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Number of tasks to skip (default: 0)",
                        "default": 0,
                    },
                },
            },
        ),
        Tool(
            name="tasks_update_task",
            description="Update an existing task's fields",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "ID of the task to update",
                    },
                    "title": {
                        "type": "string",
                        "description": "New title (optional)",
                    },
                    "description": {
                        "type": "string",
                        "description": "New description (optional, empty string to clear)",
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "urgent"],
                        "description": "New priority (optional)",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["pending", "in_progress", "completed", "archived"],
                        "description": "New status (optional)",
                    },
                    "due_date": {
                        "type": "string",
                        "description": "New due date in YYYY-MM-DD format (optional, null to clear)",
                    },
                },
                "required": ["task_id"],
            },
        ),
        Tool(
            name="tasks_mark_complete",
            description="Mark a task as completed",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "ID of the task to complete",
                    },
                },
                "required": ["task_id"],
            },
        ),
        Tool(
            name="tasks_delete_task",
            description="Delete a task permanently",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "ID of the task to delete",
                    },
                },
                "required": ["task_id"],
            },
        ),
        Tool(
            name="tasks_get_overdue",
            description="Get all overdue tasks",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="tasks_get_statistics",
            description="Get task statistics (counts by status, overdue count)",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls from AI agents."""
    service = get_service()

    try:
        if name == "tasks_create_task":
            # Parse arguments
            title = arguments["title"]
            description = arguments.get("description")
            priority = Priority(arguments["priority"]) if "priority" in arguments else Priority.MEDIUM
            status = TaskStatus(arguments["status"]) if "status" in arguments else TaskStatus.PENDING

            due_date = None
            if "due_date" in arguments:
                try:
                    due_date = datetime.strptime(arguments["due_date"], "%Y-%m-%d").date()
                except ValueError:
                    return [TextContent(
                        type="text",
                        text="Error: Invalid date format. Use YYYY-MM-DD",
                    )]

            # Create task
            task = service.create_task(
                title=title,
                description=description,
                priority=priority,
                due_date=due_date,
                status=status,
            )

            return [TextContent(
                type="text",
                text=f"✓ Created task #{task.id}: {task.title}\n\n{format_task_markdown(task)}",
            )]

        elif name == "tasks_get_task":
            task_id = arguments["task_id"]
            task = service.get_task(task_id)

            return [TextContent(
                type="text",
                text=format_task_markdown(task),
            )]

        elif name == "tasks_list_tasks":
            filter_status: TaskStatus | None = TaskStatus(arguments["status"]) if "status" in arguments else None
            filter_priority: Priority | None = Priority(arguments["priority"]) if "priority" in arguments else None
            limit = arguments.get("limit", 20)
            offset = arguments.get("offset", 0)

            tasks, total = service.list_tasks(
                status=filter_status,
                priority=filter_priority,
                limit=limit,
                offset=offset,
            )

            return [TextContent(
                type="text",
                text=format_task_list_markdown(tasks, total),
            )]

        elif name == "tasks_update_task":
            task_id = arguments["task_id"]
            title = arguments.get("title")
            description = arguments.get("description")
            update_priority: Priority | None = Priority(arguments["priority"]) if "priority" in arguments else None
            update_status: TaskStatus | None = TaskStatus(arguments["status"]) if "status" in arguments else None

            due_date = None
            if "due_date" in arguments:
                if arguments["due_date"] is None:
                    due_date = None
                else:
                    try:
                        due_date = datetime.strptime(arguments["due_date"], "%Y-%m-%d").date()
                    except ValueError:
                        return [TextContent(
                            type="text",
                            text="Error: Invalid date format. Use YYYY-MM-DD",
                        )]

            task = service.update_task(
                task_id=task_id,
                title=title,
                description=description,
                priority=update_priority,
                status=update_status,
                due_date=due_date,
            )

            return [TextContent(
                type="text",
                text=f"✓ Updated task #{task.id}\n\n{format_task_markdown(task)}",
            )]

        elif name == "tasks_mark_complete":
            task_id = arguments["task_id"]
            task = service.mark_complete(task_id)

            return [TextContent(
                type="text",
                text=f"✓ Completed task #{task.id}: {task.title}",
            )]

        elif name == "tasks_delete_task":
            task_id = arguments["task_id"]
            service.delete_task(task_id)

            return [TextContent(
                type="text",
                text=f"✓ Deleted task #{task_id}",
            )]

        elif name == "tasks_get_overdue":
            tasks = service.get_overdue_tasks()

            if not tasks:
                return [TextContent(
                    type="text",
                    text="No overdue tasks. Great job! 🎉",
                )]

            lines = [f"# Overdue Tasks ({len(tasks)})", ""]
            for task in tasks:
                days_overdue = (date.today() - task.due_date).days if task.due_date else 0
                lines.append(f"- ⚠️ **#{task.id}**: {task.title}")
                lines.append(f"  - Due: {task.due_date} ({days_overdue} days ago)")
                lines.append(f"  - Priority: {task.priority.value} | Status: {task.status.value}")
                lines.append("")

            return [TextContent(
                type="text",
                text="\n".join(lines),
            )]

        elif name == "tasks_get_statistics":
            stats = service.get_statistics()

            lines = [
                "# Task Statistics",
                "",
                f"**Total Tasks:** {stats['total']}",
                f"**Pending:** {stats['pending']}",
                f"**In Progress:** {stats['in_progress']}",
                f"**Completed:** {stats['completed']}",
                f"**Archived:** {stats['archived']}",
                f"**Overdue:** {stats['overdue']}",
            ]

            return [TextContent(
                type="text",
                text="\n".join(lines),
            )]

        else:
            return [TextContent(
                type="text",
                text=f"Error: Unknown tool '{name}'",
            )]

    except ValueError as e:
        return [TextContent(
            type="text",
            text=f"Error: {str(e)}",
        )]
    except Exception as e:
        return [TextContent(
            type="text",
            text=f"Unexpected error: {str(e)}",
        )]


# Resources - Contextual data access
@app.list_resources()
async def list_resources() -> list[Resource]:
    """List available resources."""
    from mcp.types import AnyUrl
    return [
        Resource(
            uri=AnyUrl("stats://overview"),
            name="Task Statistics Overview",
            description="Overall task statistics and counts",
            mimeType="text/markdown",
        ),
    ]


@app.read_resource()
async def read_resource(uri: str) -> str:
    """Read resource content."""
    service = get_service()

    if uri == "stats://overview":
        stats = service.get_statistics()

        lines = [
            "# Task Statistics Overview",
            "",
            f"- **Total Tasks:** {stats['total']}",
            f"- **Pending:** {stats['pending']}",
            f"- **In Progress:** {stats['in_progress']}",
            f"- **Completed:** {stats['completed']}",
            f"- **Archived:** {stats['archived']}",
            f"- **Overdue:** {stats['overdue']}",
        ]

        return "\n".join(lines)

    raise ValueError(f"Unknown resource: {uri}")


async def main() -> None:
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
