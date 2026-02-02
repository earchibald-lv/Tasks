"""CLI interface for the task manager using Typer.

This module provides the command-line interface that wraps the service layer,
providing user-friendly commands for task management.
"""

import os
from datetime import date, datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from taskmanager.config import get_settings
from taskmanager.database import get_session, init_db
from taskmanager.models import Priority, TaskStatus
from taskmanager.repository_impl import SQLTaskRepository
from taskmanager.service import TaskService

# Initialize Typer app
app = typer.Typer(
    name="tasks",
    help="A powerful CLI task manager for organizing your work and life.",
    add_completion=True,
)

# Rich console for beautiful output
console = Console()

# Global automation flag - can be set via environment variable
_automation_mode = os.getenv("TASKS_AUTOMATION", "").lower() in ("1", "true", "yes")


def get_service() -> TaskService:
    """Create and return a TaskService instance with dependencies."""
    settings = get_settings()
    profile = settings.profile
    init_db(profile)  # Ensure database is initialized with correct profile
    session = get_session(profile)  # Get session for correct profile
    repository = SQLTaskRepository(session)
    return TaskService(repository)


def confirm_action(message: str, force: bool = False, yes_flag: bool = False) -> bool:
    """Confirm an action with the user.
    
    Respects automation mode and force/yes flags for non-interactive use.
    
    Args:
        message: The confirmation message to display
        force: Force flag from command (skip confirmation)
        yes_flag: Global yes flag from command (auto-confirm)
        
    Returns:
        True if action confirmed, False otherwise
    """
    # Auto-confirm in automation mode or if force/yes flags are set
    if _automation_mode or force or yes_flag:
        return True
    
    return typer.confirm(message)


def load_from_file_if_needed(value: str | None) -> str | None:
    """Load content from a file if the value starts with @.
    
    This mimics AWS CLI behavior where @filename loads the file content.
    
    Args:
        value: The value to process, potentially starting with @
        
    Returns:
        The file content if value starts with @, otherwise the original value
        
    Raises:
        typer.Exit: If file cannot be read
    """
    if value is None:
        return None
        
    if not value.startswith("@"):
        return value
        
    # Remove @ prefix and get file path
    file_path = Path(value[1:])
    
    try:
        # Read file content
        content = file_path.read_text(encoding="utf-8").strip()
        return content
    except FileNotFoundError:
        console.print(f"[red]Error:[/red] File not found: {file_path}", style="bold")
        raise typer.Exit(1)
    except PermissionError:
        console.print(f"[red]Error:[/red] Permission denied reading: {file_path}", style="bold")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to read {file_path}: {str(e)}", style="bold")
        raise typer.Exit(1)


@app.command("add")
@app.command("new")  # Alias for 'add' command
def add_task(
    title: str = typer.Argument(..., help="Task title (required)"),
    description: str | None = typer.Option(None, "--description", "-d", help="Task description"),
    priority: Priority | None = typer.Option(None, "--priority", "-p", help="Task priority"),
    due: str | None = typer.Option(None, "--due", help="Due date (YYYY-MM-DD)"),
    status: TaskStatus | None = typer.Option(None, "--status", "-s", help="Initial status"),
    jira: str | None = typer.Option(None, "--jira", "-j", help="JIRA issue keys (comma-separated)"),
    tags: str | None = typer.Option(None, "--tags", "-t", help="Tags (comma-separated)"),
) -> None:
    """Create a new task."""
    try:
        service = get_service()
        
        # Load description from file if needed
        description = load_from_file_if_needed(description)

        # Parse due date if provided
        due_date: date | None = None
        if due:
            try:
                due_date = datetime.strptime(due, "%Y-%m-%d").date()
            except ValueError:
                console.print("[red]Error:[/red] Invalid date format. Use YYYY-MM-DD", style="bold")
                raise typer.Exit(1)

        # Create task (using defaults for priority/status if not provided)
        task = service.create_task(
            title=title,
            description=description,
            priority=priority if priority is not None else Priority.MEDIUM,
            due_date=due_date,
            status=status if status is not None else TaskStatus.PENDING,
            jira_issues=jira,
            tags=tags,
        )

        console.print(f"[green]✓[/green] Created task #{task.id}: {task.title}", style="bold")

        # Show task details
        if description:
            console.print(f"  Description: {description}")
        if priority:
            console.print(f"  Priority: {priority.value}")
        if due_date:
            console.print(f"  Due: {due_date}")
        if status:
            console.print(f"  Status: {status.value}")
        if jira:
            console.print(f"  JIRA: {jira}")
        if tags:
            console.print(f"  Tags: {tags}")

    except ValueError as e:
        console.print(f"[red]Error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)


@app.command("list")
def list_tasks(
    status: TaskStatus | None = typer.Option(None, "--status", "-s", help="Filter by status"),
    priority: Priority | None = typer.Option(None, "--priority", "-p", help="Filter by priority"),
    tag: str | None = typer.Option(None, "--tag", help="Filter by tag (partial match)"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum number of tasks to show"),
    offset: int = typer.Option(0, "--offset", help="Number of tasks to skip"),
    format: str = typer.Option("table", "--format", "-f", help="Output format (table, simple, json)"),
    all: bool = typer.Option(False, "--all", "-a", help="Show all tasks including completed, cancelled, and archived"),
    show_tags: bool = typer.Option(False, "--show-tags", help="Show tags column in table"),
    show_jira: int | None = typer.Option(None, "--show-jira", help="Show JIRA issues column. Optionally limit to N issues (e.g., --show-jira 2). Use 0 or omit value for all issues."),
    show_created: bool = typer.Option(False, "--show-created", help="Show created date column in table"),
    show_updated: bool = typer.Option(False, "--show-updated", help="Show updated date column in table"),
) -> None:
    """List tasks with optional filtering.
    
    By default, only shows open tasks (pending and in_progress).
    Use --all to include completed, cancelled, and archived tasks.
    Use --show-* flags to add additional columns to the table view.
    """
    try:
        service = get_service()

        # If no status filter specified and --all not used, filter to open tasks only
        if status is None and not all:
            # Show only pending and in_progress tasks
            tasks_pending, total_pending = service.list_tasks(
                status=TaskStatus.PENDING,
                priority=priority,
                tag=tag,
                limit=limit,
                offset=offset,
            )
            tasks_in_progress, total_in_progress = service.list_tasks(
                status=TaskStatus.IN_PROGRESS,
                priority=priority,
                tag=tag,
                limit=limit,
                offset=0,
            )
            
            # Combine and sort by id
            tasks = sorted(tasks_pending + tasks_in_progress, key=lambda t: t.id or 0)
            total = total_pending + total_in_progress
            
            # Apply limit again after combining
            tasks = tasks[:limit]
        else:
            # Get tasks (service returns tuple of tasks and total count)
            tasks, total = service.list_tasks(
                status=status,
                priority=priority,
                tag=tag,
                limit=limit,
                offset=offset,
            )

        if not tasks:
            console.print("[yellow]No tasks found.[/yellow]")
            return

        # Format output
        if format == "json":
            import json
            task_dicts = [
                {
                    "id": task.id,
                    "title": task.title,
                    "description": task.description,
                    "status": task.status.value,
                    "priority": task.priority.value,
                    "due_date": task.due_date.isoformat() if task.due_date else None,
                    "created_at": task.created_at.isoformat(),
                }
                for task in tasks
            ]
            console.print(json.dumps(task_dicts, indent=2))
        elif format == "simple":
            for task in tasks:
                status_icon = "✓" if task.status == TaskStatus.COMPLETED else "○"
                due_str = f" (due: {task.due_date})" if task.due_date else ""
                console.print(f"{status_icon} #{task.id}: {task.title}{due_str}")
        else:  # table format
            table = Table(title=f"Tasks ({len(tasks)} of {total})")
            table.add_column("ID", style="cyan", no_wrap=True)
            table.add_column("Title", style="white")
            table.add_column("Status", style="yellow")
            table.add_column("Priority", style="magenta")
            table.add_column("Due Date", style="red")
            
            # Add optional columns based on flags
            if show_tags:
                table.add_column("Tags", style="green")
            if show_jira is not None:
                table.add_column("JIRA", style="blue")
            if show_created:
                table.add_column("Created", style="dim")
            if show_updated:
                table.add_column("Updated", style="dim")

            for task in tasks:
                # Status with icons
                status_icons = {
                    TaskStatus.PENDING: "○",
                    TaskStatus.IN_PROGRESS: "◐",
                    TaskStatus.COMPLETED: "✓",
                    TaskStatus.CANCELLED: "✕",
                    TaskStatus.ARCHIVED: "✖",
                }
                status_display = f"{status_icons.get(task.status, '?')} {task.status.value}"

                # Priority colors
                priority_colors = {
                    Priority.LOW: "dim",
                    Priority.MEDIUM: "yellow",
                    Priority.HIGH: "orange1",
                    Priority.URGENT: "red bold",
                }
                priority_style = priority_colors.get(task.priority, "white")

                # Due date with overdue indicator
                due_display = ""
                if task.due_date:
                    is_overdue = task.due_date < date.today() and task.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.ARCHIVED]
                    if is_overdue:
                        due_display = f"[red bold]{task.due_date} ⚠[/red bold]"
                    else:
                        due_display = str(task.due_date)

                # Build row data starting with core columns
                row_data = [
                    str(task.id),
                    task.title,
                    status_display,
                    f"[{priority_style}]{task.priority.value}[/{priority_style}]",
                    due_display,
                ]
                
                # Add optional column data
                if show_tags:
                    tags_display = task.tags if task.tags else ""
                    row_data.append(tags_display)
                if show_jira is not None:
                    # Format JIRA issues with optional limit
                    if task.jira_issues:
                        jira_list = [issue.strip() for issue in task.jira_issues.split(",")]
                        # Limit to show_jira items if > 0, otherwise show all
                        if show_jira > 0 and len(jira_list) > show_jira:
                            jira_display = ", ".join(jira_list[:show_jira]) + f" (+{len(jira_list) - show_jira})"
                        else:
                            jira_display = ", ".join(jira_list)
                    else:
                        jira_display = ""
                    row_data.append(jira_display)
                if show_created:
                    created_display = task.created_at.strftime("%Y-%m-%d") if task.created_at else ""
                    row_data.append(created_display)
                if show_updated:
                    updated_display = task.updated_at.strftime("%Y-%m-%d") if task.updated_at else ""
                    row_data.append(updated_display)
                
                table.add_row(*row_data)

            console.print(table)

    except ValueError as e:
        console.print(f"[red]Error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)


@app.command("show")
def show_task(
    task_id: int = typer.Argument(..., help="Task ID to display"),
) -> None:
    """Show detailed information about a specific task."""
    try:
        service = get_service()
        settings = get_settings()
        task = service.get_task(task_id)

        # Create a panel with task details
        console.print(f"\n[bold cyan]Task #{task.id}[/bold cyan]")
        console.print(f"[bold]Title:[/bold] {task.title}")

        if task.description:
            console.print(f"[bold]Description:[/bold]\n  {task.description}")

        # Status with icon
        status_icons = {
            TaskStatus.PENDING: "○",
            TaskStatus.IN_PROGRESS: "◐",
            TaskStatus.COMPLETED: "✓",
            TaskStatus.CANCELLED: "✕",
            TaskStatus.ARCHIVED: "✖",
        }
        status_icon = status_icons.get(task.status, "?")
        console.print(f"[bold]Status:[/bold] {status_icon} {task.status.value}")

        # Priority with color
        priority_colors = {
            Priority.LOW: "dim",
            Priority.MEDIUM: "yellow",
            Priority.HIGH: "orange1",
            Priority.URGENT: "red bold",
        }
        priority_style = priority_colors.get(task.priority, "white")
        console.print(f"[bold]Priority:[/bold] [{priority_style}]{task.priority.value}[/{priority_style}]")

        # JIRA issues with clickable links
        if task.jira_issues:
            jira_links = service.format_jira_links(task.jira_issues, settings.jira.jira_url)
            if jira_links:
                console.print(f"[bold]JIRA Issues:[/bold]")
                for issue_key, url in jira_links:
                    console.print(f"  • [link={url}]{issue_key}[/link] ({url})")
            else:
                # No JIRA URL configured, just show the keys
                console.print(f"[bold]JIRA Issues:[/bold] {task.jira_issues}")

        # Tags
        if task.tags:
            tag_list = [f"[cyan]{tag.strip()}[/cyan]" for tag in task.tags.split(",")]
            console.print(f"[bold]Tags:[/bold] {', '.join(tag_list)}")

        # Attachments
        attachments = service.list_attachments(task.id)
        if attachments:
            console.print(f"[bold]Attachments:[/bold] {len(attachments)} file(s) - use 'tasks attach list {task.id}' to view")

        # Dates
        if task.due_date:
            is_overdue = task.due_date < date.today() and task.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.ARCHIVED]
            if is_overdue:
                console.print(f"[bold]Due:[/bold] [red bold]{task.due_date} ⚠ OVERDUE[/red bold]")
            else:
                console.print(f"[bold]Due:[/bold] {task.due_date}")

        console.print(f"[bold]Created:[/bold] {task.created_at.strftime('%Y-%m-%d %H:%M')}")
        if task.updated_at:
            console.print(f"[bold]Updated:[/bold] {task.updated_at.strftime('%Y-%m-%d %H:%M')}")

        console.print()  # Empty line

    except ValueError as e:
        console.print(f"[red]Error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)


@app.command("update")
def update_task(
    task_id: int = typer.Argument(..., help="Task ID to update"),
    title: str | None = typer.Option(None, "--title", "-t", help="New title"),
    description: str | None = typer.Option(None, "--description", "-d", help="New description"),
    priority: Priority | None = typer.Option(None, "--priority", "-p", help="New priority"),
    status: TaskStatus | None = typer.Option(None, "--status", "-s", help="New status"),
    due: str | None = typer.Option(None, "--due", help="New due date (YYYY-MM-DD)"),
    jira: str | None = typer.Option(None, "--jira", "-j", help="JIRA issue keys (comma-separated)"),
    tags: str | None = typer.Option(None, "--tags", help="Tags (comma-separated)"),
    clear_description: bool = typer.Option(False, "--clear-description", help="Clear the description"),
    clear_due: bool = typer.Option(False, "--clear-due", help="Clear the due date"),
    clear_jira: bool = typer.Option(False, "--clear-jira", help="Clear JIRA issues"),
    clear_tags: bool = typer.Option(False, "--clear-tags", help="Clear tags"),
) -> None:
    """Update an existing task."""
    try:
        service = get_service()
        
        # Load description from file if needed (unless clearing)
        if not clear_description:
            description = load_from_file_if_needed(description)

        # Parse due date if provided
        due_date = None
        if due:
            try:
                due_date = datetime.strptime(due, "%Y-%m-%d").date()
            except ValueError:
                console.print("[red]Error:[/red] Invalid date format. Use YYYY-MM-DD", style="bold")
                raise typer.Exit(1)

        # Handle clearing fields
        if clear_description:
            description = ""
        if clear_due:
            due_date = None
        if clear_jira:
            jira = ""
        if clear_tags:
            tags = ""

        # Update task
        task = service.update_task(
            task_id=task_id,
            title=title,
            description=description,
            priority=priority,
            status=status,
            due_date=due_date,
            jira_issues=jira,
            tags=tags,
        )

        # Display what was updated
        console.print(f"[green]✓[/green] Updated task #{task.id}: {task.title}", style="bold")
        
        # Show updated fields
        updates = []
        if title is not None:
            updates.append(f"Title: {title}")
        if description is not None:
            if clear_description:
                updates.append("Description: [dim](cleared)[/dim]")
            else:
                # Show first 50 chars of description
                desc_preview = description[:50] + "..." if len(description) > 50 else description
                updates.append(f"Description: {desc_preview}")
        if priority is not None:
            updates.append(f"Priority: {priority.value}")
        if status is not None:
            updates.append(f"Status: {status.value}")
        if due_date is not None or clear_due:
            if clear_due:
                updates.append("Due date: [dim](cleared)[/dim]")
            else:
                updates.append(f"Due date: {due_date}")
        if jira is not None:
            if clear_jira:
                updates.append("JIRA issues: [dim](cleared)[/dim]")
            else:
                updates.append(f"JIRA issues: {jira}")
        if tags is not None:
            if clear_tags:
                updates.append("Tags: [dim](cleared)[/dim]")
            else:
                updates.append(f"Tags: {tags}")
        
        if updates:
            console.print("\n[bold]Updated fields:[/bold]")
            for update in updates:
                console.print(f"  • {update}")

    except ValueError as e:
        console.print(f"[red]Error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)


@app.command("complete")
def complete_task(
    task_id: int = typer.Argument(..., help="Task ID to mark as complete"),
) -> None:
    """Mark a task as complete."""
    try:
        service = get_service()
        task = service.mark_complete(task_id)

        console.print(f"[green]✓ Completed task #{task.id}: {task.title}[/green]", style="bold")

    except ValueError as e:
        console.print(f"[red]Error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)


@app.command("delete")
def delete_task(
    task_id: int = typer.Argument(..., help="Task ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
) -> None:
    """Delete a task permanently."""
    try:
        service = get_service()

        # Get task for confirmation
        task = service.get_task(task_id)

        # Confirm deletion
        if not confirm_action(f"Delete task #{task_id}: '{task.title}'?", force=force):
            console.print("[yellow]Deletion cancelled.[/yellow]")
            raise typer.Exit(0)

        service.delete_task(task_id)
        console.print(f"[red]✓ Deleted task #{task_id}[/red]", style="bold")

    except ValueError as e:
        console.print(f"[red]Error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)


@app.command("tags")
def list_tags() -> None:
    """List all unique tags currently used across all tasks."""
    try:
        service = get_service()
        tags = service.get_all_used_tags()
        
        if not tags:
            console.print("[yellow]No tags found.[/yellow]")
            return
        
        console.print(f"[bold]Found {len(tags)} unique tags:[/bold]\n")
        for tag in tags:
            console.print(f"  • {tag}")
        
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)


# Configuration management subcommand group
config_app = typer.Typer(help="Manage configuration")
app.add_typer(config_app, name="config")


@config_app.command("show")
def config_show() -> None:
    """Display current configuration."""
    from taskmanager.config import get_settings
    
    settings = get_settings()
    
    table = Table(title="Current Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Profile", settings.profile)
    table.add_row("Config Directory", str(settings.get_config_dir()))
    table.add_row("Data Directory", str(settings.get_data_dir()))
    table.add_row("Database URL", settings.get_database_url())
    table.add_row("Task List Limit", str(settings.defaults.task_limit))
    table.add_row("Max Task Limit", str(settings.defaults.max_task_limit))
    table.add_row("Log Level", settings.logging.level)
    table.add_row("MCP Server Name", settings.mcp.server_name)
    
    console.print(table)


@config_app.command("path")
def config_path() -> None:
    """Show configuration file location."""
    from taskmanager.config import get_user_config_path, get_project_config_path
    
    user_config = get_user_config_path()
    project_config = get_project_config_path()
    
    console.print(f"[bold]User config:[/bold] {user_config}")
    if user_config.exists():
        console.print("  [green]✓ exists[/green]")
    else:
        console.print("  [yellow]✗ not found[/yellow]")
    
    if project_config:
        console.print(f"\n[bold]Project config:[/bold] {project_config}")
        if project_config.exists():
            console.print("  [green]✓ exists[/green]")
        else:
            console.print("  [yellow]✗ not found[/yellow]")
    else:
        console.print("\n[yellow]Not in a git repository[/yellow]")


@config_app.command("edit")
def config_edit() -> None:
    """Open configuration file in editor."""
    import os
    import subprocess
    from taskmanager.config import get_user_config_path, create_default_config
    
    config_path = get_user_config_path()
    
    # Create config if it doesn't exist
    if not config_path.exists():
        console.print("[yellow]Config file doesn't exist. Creating default...[/yellow]")
        create_default_config(config_path)
        console.print(f"[green]✓ Created {config_path}[/green]")
    
    # Try to find editor
    editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "nano"))
    
    try:
        subprocess.run([editor, str(config_path)], check=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        console.print(f"[red]Error opening editor '{editor}':[/red] {e}", style="bold")
        console.print(f"\nConfig file location: {config_path}")
        raise typer.Exit(1)


@config_app.command("validate")
def config_validate() -> None:
    """Validate configuration file."""
    from taskmanager.config import find_config_files, get_settings
    import tomllib
    
    config_files = find_config_files()
    
    if not config_files:
        console.print("[yellow]No configuration files found.[/yellow]")
        return
    
    all_valid = True
    
    for config_file in config_files:
        console.print(f"\n[bold]Validating {config_file}...[/bold]")
        
        try:
            # Try to load as TOML
            with open(config_file, "rb") as f:
                tomllib.load(f)
            console.print("  [green]✓ TOML syntax valid[/green]")
            
            # Try to load settings
            get_settings()
            console.print("  [green]✓ Configuration valid[/green]")
            
        except Exception as e:
            console.print(f"  [red]✗ Error:[/red] {e}")
            all_valid = False
    
    if all_valid:
        console.print("\n[green bold]✓ All configuration files are valid[/green bold]")
    else:
        console.print("\n[red bold]✗ Configuration validation failed[/red bold]")
        raise typer.Exit(1)


@config_app.command("init")
def config_init(
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing config"),
) -> None:
    """Create or reset configuration file."""
    from taskmanager.config import get_user_config_path, create_default_config
    
    config_path = get_user_config_path()
    
    if config_path.exists() and not force:
        console.print(f"[yellow]Config file already exists: {config_path}[/yellow]")
        console.print("Use --force to overwrite")
        raise typer.Exit(1)
    
    create_default_config(config_path)
    console.print(f"[green]✓ Created configuration file: {config_path}[/green]")
    console.print("\nDefault configuration:")
    console.print("  • Profile: default")
    console.print("  • Database: ~/.config/taskmanager/taskmanager/tasks.db")
    console.print("  • Dev database: ~/.config/taskmanager/taskmanager/tasks-dev.db")
    console.print("  • Test database: in-memory")


@app.callback()
def main(
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to configuration file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    profile: str | None = typer.Option(
        None,
        "--profile",
        "-p",
        help="Configuration profile (default, dev, test)",
    ),
    database: str | None = typer.Option(
        None,
        "--database",
        "-d",
        help="Database URL override",
    ),
) -> None:
    """
    Tasks - A powerful CLI task manager.

    Manage your tasks, deadlines, and projects from the command line.
    
    Use global options to override configuration:
    
    \b
    • --config: Use specific config file
    • --profile: Switch between default/dev/test profiles  
    • --database: Override database URL directly
    
    Examples:
    
    \b
    tasks --profile dev list
    tasks --database sqlite:///custom.db add "Test task"
    tasks --config ./my-config.toml list
    """
    from taskmanager.config import get_settings
    
    # Get settings and apply overrides
    settings = get_settings()
    
    # Apply CLI overrides
    if profile:
        # Override the profile attribute directly
        settings.profile = profile
    if database:
        settings.set_override("database_url", database)
    # Note: --config would require modifying load_toml_config to accept custom path


# Attachment management subcommand group
attach_app = typer.Typer(help="Manage task attachments")
app.add_typer(attach_app, name="attach")


@attach_app.command("add")
def attach_add(
    task_id: int = typer.Argument(..., help="Task ID to attach file to"),
    file_path: Path = typer.Argument(..., help="Path to file to attach", exists=True),
) -> None:
    """Attach a file to a task."""
    try:
        service = get_service()
        
        if not file_path.is_file():
            console.print(f"[red]Error:[/red] Not a file: {file_path}", style="bold")
            raise typer.Exit(1)
        
        # Add the attachment
        metadata = service.add_attachment(task_id, file_path)
        
        console.print(f"[green]✓[/green] Attached file to task #{task_id}", style="bold")
        console.print(f"  Original name: {metadata['original_name']}")
        console.print(f"  Stored as: {metadata['filename']}")
        console.print(f"  Size: {metadata['size']:,} bytes")
        
    except ValueError as e:
        console.print(f"[red]Error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)


@attach_app.command("list")
def attach_list(
    task_id: int = typer.Argument(..., help="Task ID to list attachments for"),
) -> None:
    """List all attachments for a task."""
    try:
        service = get_service()
        attachments = service.list_attachments(task_id)
        
        if not attachments:
            console.print(f"[yellow]Task #{task_id} has no attachments.[/yellow]")
            return
        
        table = Table(title=f"Attachments for Task #{task_id}")
        table.add_column("Filename", style="cyan")
        table.add_column("Original Name", style="white")
        table.add_column("Size", style="green", justify="right")
        table.add_column("Added", style="yellow")
        
        for attachment in attachments:
            size_kb = attachment["size"] / 1024
            size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
            
            added_dt = datetime.fromisoformat(attachment["added_at"])
            added_str = added_dt.strftime("%Y-%m-%d %H:%M")
            
            table.add_row(
                attachment["filename"],
                attachment["original_name"],
                size_str,
                added_str,
            )
        
        console.print(table)
        
    except ValueError as e:
        console.print(f"[red]Error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)


@attach_app.command("remove")
def attach_remove(
    task_id: int = typer.Argument(..., help="Task ID"),
    filename: str = typer.Argument(..., help="Filename of attachment to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Remove an attachment from a task."""
    try:
        service = get_service()
        
        # Confirm removal
        if not confirm_action(f"Remove attachment '{filename}' from task #{task_id}?", force=force):
            console.print("[yellow]Removal cancelled.[/yellow]")
            raise typer.Exit(0)
        
        removed = service.remove_attachment(task_id, filename)
        
        if removed:
            console.print(f"[green]✓[/green] Removed attachment '{filename}' from task #{task_id}", style="bold")
        else:
            console.print(f"[yellow]Attachment '{filename}' not found.[/yellow]")
            raise typer.Exit(1)
        
    except ValueError as e:
        console.print(f"[red]Error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)


@attach_app.command("open")
def attach_open(
    task_id: int = typer.Argument(..., help="Task ID"),
    filename: str = typer.Argument(..., help="Filename of attachment to open"),
) -> None:
    """Open an attachment file."""
    try:
        import subprocess
        import sys
        
        service = get_service()
        file_path = service.get_attachment_path(task_id, filename)
        
        # Open the file using system default application
        if sys.platform == "darwin":  # macOS
            subprocess.run(["open", str(file_path)])
        elif sys.platform == "win32":  # Windows
            subprocess.run(["start", str(file_path)], shell=True)
        else:  # Linux
            subprocess.run(["xdg-open", str(file_path)])
        
        console.print(f"[green]Opened:[/green] {filename}")
        
    except ValueError as e:
        console.print(f"[red]Error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)


@attach_app.command("path")
def attach_path(
    task_id: int = typer.Argument(..., help="Task ID"),
    filename: str = typer.Argument(..., help="Filename of attachment"),
) -> None:
    """Show the full path to an attachment file."""
    try:
        service = get_service()
        file_path = service.get_attachment_path(task_id, filename)
        
        console.print(str(file_path))
        
    except ValueError as e:
        console.print(f"[red]Error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)


# Workspace management subcommand group
workspace_app = typer.Typer(help="Manage task workspaces")
app.add_typer(workspace_app, name="workspace")


@workspace_app.command("create")
def workspace_create(
    task_id: int = typer.Argument(..., help="Task ID to create workspace for"),
    no_git: bool = typer.Option(False, "--no-git", help="Skip git initialization"),
) -> None:
    """Create a persistent workspace for a task."""
    try:
        service = get_service()

        # Create workspace
        metadata = service.create_workspace(
            task_id=task_id,
            initialize_git=not no_git
        )

        console.print(f"[green]✓[/green] Created workspace for task #{task_id}", style="bold")
        console.print(f"  Path: {metadata['workspace_path']}")
        console.print(f"  Git initialized: {'Yes' if metadata['git_initialized'] else 'No'}")

    except ValueError as e:
        console.print(f"[red]Error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)


@workspace_app.command("info")
def workspace_info(
    task_id: int = typer.Argument(..., help="Task ID"),
) -> None:
    """Show workspace information for a task."""
    try:
        service = get_service()
        metadata = service.get_workspace_info(task_id)

        if not metadata:
            console.print(f"[yellow]No workspace exists for task #{task_id}[/yellow]")
            raise typer.Exit(0)

        from datetime import datetime

        console.print(f"[bold]Workspace for Task #{task_id}[/bold]")
        console.print(f"  Path: {metadata['workspace_path']}")
        console.print(f"  Created: {metadata['created_at']}")
        console.print(f"  Git initialized: {'Yes' if metadata['git_initialized'] else 'No'}")
        if metadata.get('last_accessed'):
            console.print(f"  Last accessed: {metadata['last_accessed']}")

    except ValueError as e:
        console.print(f"[red]Error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)


@workspace_app.command("path")
def workspace_path(
    task_id: int = typer.Argument(..., help="Task ID"),
) -> None:
    """Show the path to a task's workspace."""
    try:
        service = get_service()
        path = service.get_workspace_path(task_id)

        if not path:
            console.print(f"[yellow]No workspace exists for task #{task_id}[/yellow]")
            raise typer.Exit(0)

        console.print(str(path))

    except ValueError as e:
        console.print(f"[red]Error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)


@workspace_app.command("open")
def workspace_open(
    task_id: int = typer.Argument(..., help="Task ID"),
) -> None:
    """Open a task's workspace in Finder (macOS)."""
    try:
        import subprocess
        import sys

        service = get_service()
        path = service.get_workspace_path(task_id)

        if not path:
            console.print(f"[yellow]No workspace exists for task #{task_id}[/yellow]")
            raise typer.Exit(0)

        if not path.exists():
            console.print(f"[red]Workspace directory does not exist:[/red] {path}")
            raise typer.Exit(1)

        # Open the directory
        if sys.platform == "darwin":  # macOS
            subprocess.run(["open", str(path)])
        elif sys.platform == "win32":  # Windows
            subprocess.run(["explorer", str(path)])
        else:  # Linux
            subprocess.run(["xdg-open", str(path)])

        console.print(f"[green]Opened workspace:[/green] {path}")

    except ValueError as e:
        console.print(f"[red]Error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)


@workspace_app.command("delete")
def workspace_delete(
    task_id: int = typer.Argument(..., help="Task ID"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Delete a task's workspace and all its contents."""
    try:
        service = get_service()

        # Check if workspace exists
        path = service.get_workspace_path(task_id)
        if not path:
            console.print(f"[yellow]No workspace exists for task #{task_id}[/yellow]")
            raise typer.Exit(0)

        # Confirm deletion
        if not confirm_action(
            f"Delete workspace for task #{task_id}? This will permanently remove all files in {path}",
            force=force
        ):
            console.print("[yellow]Deletion cancelled.[/yellow]")
            raise typer.Exit(0)

        deleted = service.delete_workspace(task_id)

        if deleted:
            console.print(f"[green]✓[/green] Deleted workspace for task #{task_id}", style="bold")
        else:
            console.print(f"[yellow]Workspace not found.[/yellow]")
            raise typer.Exit(1)

    except ValueError as e:
        console.print(f"[red]Error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)


@workspace_app.command("list")
def workspace_list(
    task_id: int = typer.Argument(..., help="Task ID"),
    subdirectory: str = typer.Option("", "--dir", "-d", help="Subdirectory to list"),
    pattern: str = typer.Option("*", "--pattern", "-p", help="File pattern (e.g., *.py, *.md)"),
) -> None:
    """List files in a task's workspace."""
    try:
        import datetime
        from pathlib import Path

        service = get_service()
        workspace_path = service.get_workspace_path(task_id)

        if not workspace_path:
            console.print(f"[yellow]No workspace exists for task #{task_id}[/yellow]")
            raise typer.Exit(0)

        # Build target path
        target_path = Path(workspace_path) / subdirectory if subdirectory else Path(workspace_path)

        if not target_path.exists():
            console.print(f"[red]Directory not found:[/red] {target_path}")
            raise typer.Exit(1)

        # Get matching files
        if pattern == "*":
            files = list(target_path.rglob("*"))
        else:
            files = list(target_path.rglob(pattern))

        # Filter to only files
        files = [f for f in files if f.is_file()]
        files = [f for f in files if ".git" not in str(f) and "__pycache__" not in str(f)]

        if not files:
            console.print(f"[yellow]No files found[/yellow]")
            raise typer.Exit(0)

        # Sort by modification time
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

        console.print(f"[bold]Files in workspace for task #{task_id}[/bold]")
        console.print(f"Path: {target_path}")
        console.print(f"Pattern: {pattern}")
        console.print(f"Found: {len(files)} file(s)\n")

        for f in files[:50]:
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

            console.print(f"  {relative_path} - {size_str} - {modified.strftime('%Y-%m-%d %H:%M')}")

        if len(files) > 50:
            console.print(f"\n... and {len(files) - 50} more files")

    except ValueError as e:
        console.print(f"[red]Error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)


@workspace_app.command("search")
def workspace_search(
    task_id: int = typer.Argument(..., help="Task ID"),
    query: str = typer.Argument(..., help="Search query"),
    pattern: str = typer.Option("*", "--pattern", "-p", help="File pattern (e.g., *.py, *.md)"),
    case_sensitive: bool = typer.Option(False, "--case-sensitive", "-c", help="Case sensitive search"),
    max_results: int = typer.Option(50, "--max", "-m", help="Maximum results"),
) -> None:
    """Search for content in a task's workspace."""
    try:
        import subprocess

        service = get_service()
        workspace_path = service.get_workspace_path(task_id)

        if not workspace_path:
            console.print(f"[yellow]No workspace exists for task #{task_id}[/yellow]")
            raise typer.Exit(0)

        if not workspace_path.exists():
            console.print(f"[red]Workspace directory not found:[/red] {workspace_path}")
            raise typer.Exit(1)

        # Build ripgrep command
        rg_args = [
            "rg",
            "--color", "always",
            "--line-number",
            "--heading",
            "--max-count", str(max_results),
        ]

        if not case_sensitive:
            rg_args.append("--ignore-case")

        if pattern != "*":
            rg_args.extend(["--glob", pattern])

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

        if result.returncode == 1:
            console.print(f"[yellow]No matches found for:[/yellow] {query}")
            raise typer.Exit(0)

        if result.returncode > 1:
            console.print(f"[red]Search error:[/red] {result.stderr}")
            raise typer.Exit(1)

        # Display results
        console.print(f"[bold]Search results for:[/bold] {query}")
        console.print(f"Pattern: {pattern}\n")
        console.print(result.stdout)

    except subprocess.TimeoutExpired:
        console.print("[red]Search timed out[/red]")
        raise typer.Exit(1)
    except FileNotFoundError:
        console.print("[red]ripgrep not found.[/red] Install with: brew install ripgrep")
        raise typer.Exit(1)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)


@app.command("search")
def search_all(
    query: str = typer.Argument(..., help="Search query"),
    workspaces: bool = typer.Option(True, "--workspaces/--no-workspaces", help="Search workspace files"),
    tasks: bool = typer.Option(True, "--tasks/--no-tasks", help="Search task metadata"),
    pattern: str = typer.Option("*", "--pattern", "-p", help="File pattern for workspace search"),
    case_sensitive: bool = typer.Option(False, "--case-sensitive", "-c", help="Case sensitive search"),
    status: str = typer.Option("all", "--status", "-s", help="Filter by status"),
) -> None:
    """Search across all tasks and workspaces."""
    try:
        import subprocess

        service = get_service()

        # Build filters
        filters = {}
        if status != "all":
            from taskmanager.models import TaskStatus
            filters["status"] = TaskStatus(status)

        # Get all tasks
        all_tasks, total = service.list_tasks(**filters, limit=100)

        if total == 0:
            console.print("[yellow]No tasks found[/yellow]")
            raise typer.Exit(0)

        task_matches = []
        workspace_matches = []

        # Search task metadata
        if tasks:
            query_lower = query.lower() if not case_sensitive else query

            for task in all_tasks:
                matches = []

                title_check = task.title.lower() if not case_sensitive else task.title
                if query_lower in title_check:
                    matches.append("title")

                if task.description:
                    desc_check = task.description.lower() if not case_sensitive else task.description
                    if query_lower in desc_check:
                        matches.append("description")

                if task.tags:
                    tags_check = task.tags.lower() if not case_sensitive else task.tags
                    if query_lower in tags_check:
                        matches.append("tags")

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
        if workspaces:
            for task in all_tasks:
                if not task.workspace_path or not task.id:
                    continue

                workspace_path = service.get_workspace_path(task.id)
                if not workspace_path or not workspace_path.exists():
                    continue

                try:
                    rg_args = [
                        "rg",
                        "--color", "never",
                        "--files-with-matches",
                        "--max-count", "5",
                    ]

                    if not case_sensitive:
                        rg_args.append("--ignore-case")

                    if pattern != "*":
                        rg_args.extend(["--glob", pattern])

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

        # Display results
        if not task_matches and not workspace_matches:
            console.print(f"[yellow]No matches found for:[/yellow] {query}")
            console.print(f"Searched: {total} task(s)")
            return

        console.print(f"[bold]Search Results for:[/bold] {query}\n")
        console.print(f"Searched: {total} task(s)")
        console.print(f"Found: {len(task_matches)} task match(es), {len(workspace_matches)} workspace match(es)\n")

        # Show task matches
        if task_matches:
            console.print("[bold]Task Metadata Matches:[/bold]")
            for match in task_matches[:20]:
                task = match["task"]
                fields = ", ".join(match["fields"])

                from taskmanager.models import TaskStatus
                status_emoji = {
                    TaskStatus.PENDING: "⭕",
                    TaskStatus.IN_PROGRESS: "🔄",
                    TaskStatus.COMPLETED: "✅",
                    TaskStatus.CANCELLED: "❌",
                    TaskStatus.ARCHIVED: "📦",
                }.get(task.status, "❓")

                console.print(f"{status_emoji} [bold]Task #{task.id}:[/bold] {task.title}")
                console.print(f"   Matched in: {fields}")
                if task.workspace_path:
                    console.print("   📁 Has workspace")
                console.print()

        # Show workspace matches
        if workspace_matches:
            console.print("[bold]Workspace Content Matches:[/bold]")
            for match in workspace_matches[:20]:
                task = match["task"]
                files = match["files"]

                from taskmanager.models import TaskStatus
                status_emoji = {
                    TaskStatus.PENDING: "⭕",
                    TaskStatus.IN_PROGRESS: "🔄",
                    TaskStatus.COMPLETED: "✅",
                    TaskStatus.CANCELLED: "❌",
                    TaskStatus.ARCHIVED: "📦",
                }.get(task.status, "❓")

                console.print(f"{status_emoji} [bold]Task #{task.id}:[/bold] {task.title}")
                console.print(f"   Found in {len(files)} file(s):")
                for f in files[:5]:
                    console.print(f"      - {f}")
                if len(files) > 5:
                    console.print(f"      ... and {len(files) - 5} more")
                console.print()

    except FileNotFoundError:
        console.print("[red]ripgrep not found.[/red] Install with: brew install ripgrep")
        raise typer.Exit(1)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {str(e)}", style="bold")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
