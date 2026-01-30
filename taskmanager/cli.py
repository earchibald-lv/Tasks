"""CLI interface for the task manager using Typer.

This module provides the command-line interface that wraps the service layer,
providing user-friendly commands for task management.
"""

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


def get_service() -> TaskService:
    """Create and return a TaskService instance with dependencies."""
    init_db()  # Ensure database is initialized
    session = get_session()
    repository = SQLTaskRepository(session)
    return TaskService(repository)


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
def add_task(
    title: str = typer.Argument(..., help="Task title (required)"),
    description: str | None = typer.Option(None, "--description", "-d", help="Task description"),
    priority: Priority | None = typer.Option(None, "--priority", "-p", help="Task priority"),
    due: str | None = typer.Option(None, "--due", help="Due date (YYYY-MM-DD)"),
    status: TaskStatus | None = typer.Option(None, "--status", "-s", help="Initial status"),
    jira: str | None = typer.Option(None, "--jira", "-j", help="JIRA issue keys (comma-separated)"),
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
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum number of tasks to show"),
    offset: int = typer.Option(0, "--offset", help="Number of tasks to skip"),
    format: str = typer.Option("table", "--format", "-f", help="Output format (table, simple, json)"),
) -> None:
    """List tasks with optional filtering."""
    try:
        service = get_service()

        # Get tasks (service returns tuple of tasks and total count)
        tasks, total = service.list_tasks(
            status=status,
            priority=priority,
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

            for task in tasks:
                # Status with icons
                status_icons = {
                    TaskStatus.PENDING: "○",
                    TaskStatus.IN_PROGRESS: "◐",
                    TaskStatus.COMPLETED: "✓",
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
                    is_overdue = task.due_date < date.today() and task.status not in [TaskStatus.COMPLETED, TaskStatus.ARCHIVED]
                    if is_overdue:
                        due_display = f"[red bold]{task.due_date} ⚠[/red bold]"
                    else:
                        due_display = str(task.due_date)

                table.add_row(
                    str(task.id),
                    task.title,
                    status_display,
                    f"[{priority_style}]{task.priority.value}[/{priority_style}]",
                    due_display,
                )

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

        # Dates
        if task.due_date:
            is_overdue = task.due_date < date.today() and task.status not in [TaskStatus.COMPLETED, TaskStatus.ARCHIVED]
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
    clear_description: bool = typer.Option(False, "--clear-description", help="Clear the description"),
    clear_due: bool = typer.Option(False, "--clear-due", help="Clear the due date"),
    clear_jira: bool = typer.Option(False, "--clear-jira", help="Clear JIRA issues"),
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

        # Update task
        task = service.update_task(
            task_id=task_id,
            title=title,
            description=description,
            priority=priority,
            status=status,
            due_date=due_date,
            jira_issues=jira,
        )

        console.print(f"[green]✓[/green] Updated task #{task.id}: {task.title}", style="bold")

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

        # Confirm deletion unless --force is used
        if not force:
            confirm = typer.confirm(f"Delete task #{task_id}: '{task.title}'?")
            if not confirm:
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



if __name__ == "__main__":
    app()
