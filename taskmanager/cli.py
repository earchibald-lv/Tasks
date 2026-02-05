"""CLI interface for the task manager using argparse.

This module provides the command-line interface that wraps the service layer,
providing user-friendly commands for task management.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path
from importlib.metadata import version, PackageNotFoundError

try:
    import shtab
    SHTAB_AVAILABLE = True
except ImportError:
    SHTAB_AVAILABLE = False

try:
    from rich.console import Console
    from rich.table import Table
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    Console = None
    Table = None

from taskmanager.config import get_settings
from taskmanager.database import get_session, init_db
from taskmanager.models import Priority, TaskStatus
from taskmanager.repository_impl import SQLTaskRepository
from taskmanager.service import TaskService
from taskmanager.mcp_discovery import get_allowed_tools, create_ephemeral_session_dir


# Global automation flag - can be set via environment variable
_automation_mode = os.getenv("TASKS_AUTOMATION", "").lower() in ("1", "true", "yes")

# Initialize Rich console if available
console = Console() if RICH_AVAILABLE else None


def print_table(headers, rows):
    """Print a formatted table using Rich if available, otherwise plain text."""
    if RICH_AVAILABLE and console and Table:
        table = Table()
        for header in headers:
            table.add_column(header)
        for row in rows:
            table.add_row(*[str(cell) for cell in row])
        console.print(table)
    else:
        # Fallback: plain text table
        print(" | ".join(f"{h:<15}" for h in headers))
        print("-" * (len(headers) * 17))
        for row in rows:
            print(" | ".join(f"{str(v):<15}" for v in row))


class HelpfulArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that shows help on error instead of just error message."""
    
    def error(self, message):
        """Override error to show help text instead of just error."""
        # Print the help for the current parser
        self.print_help(sys.stderr)
        sys.stderr.write(f'\nerror: {message}\n')
        sys.exit(2)


def expand_abbreviations(args, subcommands):
    """Expand abbreviated subcommands in args list."""
    if len(args) > 1:
        potential_cmd = args[1]
        # Check if it's not already a full command or an option
        if not potential_cmd.startswith('-') and potential_cmd not in subcommands:
            # Try to match as abbreviation
            matches = [cmd for cmd in subcommands if cmd.startswith(potential_cmd)]
            if len(matches) == 1:
                args[1] = matches[0]
            elif len(matches) > 1:
                print(f"error: ambiguous command '{potential_cmd}'. Did you mean one of these?", file=sys.stderr)
                for match in matches:
                    print(f"  {match}", file=sys.stderr)
                sys.exit(2)
    return args


def get_version() -> str:
    """Get the package version."""
    try:
        return version("taskmanager")
    except PackageNotFoundError:
        return "unknown"


def get_service() -> TaskService:
    """Create and return a TaskService instance with dependencies."""
    settings = get_settings()
    profile = settings.profile
    init_db(profile)
    session = get_session(profile)
    repository = SQLTaskRepository(session)
    return TaskService(repository, session=session)


def is_glow_available() -> bool:
    """Check if glow is available in the system PATH."""
    return shutil.which("glow") is not None


def confirm_action(message: str, force: bool = False, yes_flag: bool = False) -> bool:
    """Confirm an action with the user."""
    if _automation_mode or force or yes_flag:
        return True
    
    response = input(f"{message} [y/N]: ").strip().lower()
    return response in ('y', 'yes')


def load_from_file_if_needed(value: str | None) -> str | None:
    """Load content from a file if the value starts with @."""
    if value is None or not value.startswith("@"):
        return value
    
    file_path = Path(value[1:])
    try:
        return file_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)
    except PermissionError:
        print(f"Error: Permission denied reading: {file_path}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: Failed to read {file_path}: {str(e)}", file=sys.stderr)
        sys.exit(1)


# Command implementations

def cmd_add(args):
    """Create a new task."""
    try:
        service = get_service()
        description = load_from_file_if_needed(args.description)
        
        due_date = None
        if args.due:
            try:
                due_date = datetime.strptime(args.due, "%Y-%m-%d").date()
            except ValueError:
                print("Error: Invalid date format. Use YYYY-MM-DD", file=sys.stderr)
                sys.exit(1)
        
        task = service.create_task(
            title=args.title,
            description=description,
            priority=Priority[args.priority.upper()] if args.priority else Priority.MEDIUM,
            due_date=due_date,
            status=TaskStatus[args.status.upper()] if args.status else TaskStatus.PENDING,
            jira_issues=args.jira,
            tags=args.tags,
        )
        
        print(f"✓ Created task #{task.id}: {task.title}")
        if description:
            print(f"  Description: {description}")
        if args.priority:
            print(f"  Priority: {args.priority}")
        if due_date:
            print(f"  Due: {due_date}")
        if args.status:
            print(f"  Status: {args.status}")
        if args.jira:
            print(f"  JIRA: {args.jira}")
        if args.tags:
            print(f"  Tags: {args.tags}")
            
    except ValueError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {str(e)}", file=sys.stderr)
        sys.exit(1)


def cmd_list(args):
    """List tasks with optional filtering."""
    try:
        service = get_service()
        
        # Handle status filtering
        status = TaskStatus[args.status.upper()] if args.status else None
        priority = Priority[args.priority.upper()] if args.priority else None
        
        # If no status filter and --all not used, filter to open tasks
        if status is None and not args.all:
            tasks_pending, total_pending = service.list_tasks(
                status=TaskStatus.PENDING,
                priority=priority,
                tag=args.tag,
                limit=args.limit,
                offset=args.offset,
            )
            tasks_in_progress, total_in_progress = service.list_tasks(
                status=TaskStatus.IN_PROGRESS,
                priority=priority,
                tag=args.tag,
                limit=args.limit,
                offset=0,
            )
            tasks = sorted(tasks_pending + tasks_in_progress, key=lambda t: t.id or 0)[:args.limit]
            total = total_pending + total_in_progress
        else:
            tasks, total = service.list_tasks(
                status=status,
                priority=priority,
                tag=args.tag,
                limit=args.limit,
                offset=args.offset,
            )
        
        if not tasks:
            print("No tasks found.")
            return
        
        # Format output
        if args.format == "json":
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
            print(json.dumps(task_dicts, indent=2))
        elif args.format == "simple":
            for task in tasks:
                status_icon = "✓" if task.status == TaskStatus.COMPLETED else "○"
                due_str = f" (due: {task.due_date})" if task.due_date else ""
                print(f"{status_icon} #{task.id}: {task.title}{due_str}")
        else:  # table format
            # Header
            print(f"\nTasks ({len(tasks)} of {total})")
            
            # Column headers
            headers = ["ID", "Title", "Status", "Priority", "Due Date"]
            if args.show_tags:
                headers.append("Tags")
            if args.show_jira is not None:
                headers.append("JIRA")
            if args.show_created:
                headers.append("Created")
            if args.show_updated:
                headers.append("Updated")
            
            # Rows
            rows = []
            for task in tasks:
                status_icons = {
                    TaskStatus.PENDING: "○",
                    TaskStatus.IN_PROGRESS: "◐",
                    TaskStatus.COMPLETED: "✓",
                    TaskStatus.CANCELLED: "✕",
                    TaskStatus.ARCHIVED: "✖",
                }
                status_display = f"{status_icons.get(task.status, '?')} {task.status.value}"
                
                due_display = ""
                if task.due_date:
                    is_overdue = (task.due_date < date.today() and 
                                task.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.ARCHIVED])
                    due_display = f"{task.due_date} {'⚠' if is_overdue else ''}"
                
                row = [
                    str(task.id),
                    task.title[:40],
                    status_display,
                    task.priority.value,
                    due_display,
                ]
                
                if args.show_tags:
                    row.append(task.tags or "")
                if args.show_jira is not None:
                    if task.jira_issues:
                        jira_list = [issue.strip() for issue in task.jira_issues.split(",")]
                        if args.show_jira > 0 and len(jira_list) > args.show_jira:
                            jira_display = ", ".join(jira_list[:args.show_jira]) + f" (+{len(jira_list) - args.show_jira})"
                        else:
                            jira_display = ", ".join(jira_list)
                    else:
                        jira_display = ""
                    row.append(jira_display)
                if args.show_created:
                    row.append(task.created_at.strftime("%Y-%m-%d") if task.created_at else "")
                if args.show_updated:
                    row.append(task.updated_at.strftime("%Y-%m-%d") if task.updated_at else "")
                
                rows.append(row)
            
            print_table(headers, rows)
            
    except ValueError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {str(e)}", file=sys.stderr)
        sys.exit(1)


def cmd_show(args):
    """Show detailed information about a specific task."""
    try:
        service = get_service()
        settings = get_settings()
        task = service.get_task(args.task_id)
        
        print(f"\nTask #{task.id}")
        print(f"Title: {task.title}")
        
        if task.description:
            print(f"Description:\n  {task.description}")
        
        status_icons = {
            TaskStatus.PENDING: "○",
            TaskStatus.IN_PROGRESS: "◐",
            TaskStatus.COMPLETED: "✓",
            TaskStatus.CANCELLED: "✕",
            TaskStatus.ARCHIVED: "✖",
        }
        status_icon = status_icons.get(task.status, "?")
        print(f"Status: {status_icon} {task.status.value}")
        print(f"Priority: {task.priority.value}")
        
        if task.jira_issues:
            jira_links = service.format_jira_links(task.jira_issues, settings.atlassian.jira_url)
            if jira_links:
                print("JIRA Issues:")
                for issue_key, url in jira_links:
                    print(f"  - {issue_key}: {url}")
            else:
                print(f"JIRA Issues: {task.jira_issues}")
        
        if task.tags:
            print(f"Tags: {task.tags}")
        
        attachments = service.list_attachments(task.id)
        if attachments:
            print(f"Attachments: {len(attachments)} file(s) - use 'tasks attach list {task.id}' to view")
        
        if task.due_date:
            is_overdue = (task.due_date < date.today() and 
                        task.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.ARCHIVED])
            print(f"Due: {task.due_date} {'⚠ OVERDUE' if is_overdue else ''}")
        
        print(f"Created: {task.created_at.strftime('%Y-%m-%d %H:%M')}")
        if task.updated_at:
            print(f"Updated: {task.updated_at.strftime('%Y-%m-%d %H:%M')}")
        print()
        
    except ValueError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {str(e)}", file=sys.stderr)
        sys.exit(1)


def cmd_update(args):
    """Update an existing task."""
    try:
        service = get_service()
        description = load_from_file_if_needed(args.description)
        
        due_date = None
        if args.due:
            try:
                due_date = datetime.strptime(args.due, "%Y-%m-%d").date()
            except ValueError:
                print("Error: Invalid date format. Use YYYY-MM-DD", file=sys.stderr)
                sys.exit(1)
        
        updates = {}
        if args.title:
            updates['title'] = args.title
        if description is not None:
            updates['description'] = description
        if args.priority:
            updates['priority'] = Priority[args.priority.upper()]
        if args.status:
            updates['status'] = TaskStatus[args.status.upper()]
        if due_date:
            updates['due_date'] = due_date
        if args.jira:
            updates['jira_issues'] = args.jira
        if args.tags:
            updates['tags'] = args.tags
        
        # Handle clear flags
        if args.clear_description:
            updates['description'] = None
        if args.clear_due:
            updates['due_date'] = None
        if args.clear_jira:
            updates['jira_issues'] = None
        if args.clear_tags:
            updates['tags'] = None
        
        task = service.update_task(args.task_id, **updates)
        print(f"✓ Updated task #{task.id}: {task.title}")
        
    except ValueError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {str(e)}", file=sys.stderr)
        sys.exit(1)


def cmd_complete(args):
    """Mark a task as complete."""
    try:
        service = get_service()
        task = service.update_task(args.task_id, status=TaskStatus.COMPLETED)
        print(f"✓ Completed task #{task.id}: {task.title}")
    except ValueError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {str(e)}", file=sys.stderr)
        sys.exit(1)


def cmd_delete(args):
    """Delete a task permanently."""
    try:
        service = get_service()
        task = service.get_task(args.task_id)
        
        if not args.force and not _automation_mode:
            if not confirm_action(f"Delete task #{task.id} '{task.title}'?"):
                print("Cancelled.")
                return
        
        service.delete_task(args.task_id)
        print(f"✓ Deleted task #{args.task_id}")
        
    except ValueError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {str(e)}", file=sys.stderr)
        sys.exit(1)


def cmd_tags(args):
    """List all unique tags currently used across all tasks."""
    try:
        service = get_service()
        tags = service.list_tags()
        
        if not tags:
            print("No tags found.")
            return
        
        print(f"\nTags ({len(tags)} total):")
        for tag in tags:
            print(f"  - {tag}")
        print()
        
    except Exception as e:
        print(f"Unexpected error: {str(e)}", file=sys.stderr)
        sys.exit(1)


def cmd_search(args):
    """Search across all tasks and workspaces."""
    try:
        service = get_service()
        
        # Build filters
        filters = {}
        if args.status and args.status != "all":
            filters["status"] = TaskStatus[args.status.upper()]
        
        # Get all tasks
        all_tasks, total = service.list_tasks(**filters, limit=100)
        
        if total == 0:
            print("No tasks found")
            sys.exit(0)
        
        task_matches = []
        workspace_matches = []
        
        # Search task metadata
        if args.tasks:
            query_lower = args.query.lower() if not args.case_sensitive else args.query
            
            for task in all_tasks:
                matches = []
                
                title_check = task.title.lower() if not args.case_sensitive else task.title
                if query_lower in title_check:
                    matches.append("title")
                
                if task.description:
                    desc_check = task.description.lower() if not args.case_sensitive else task.description
                    if query_lower in desc_check:
                        matches.append("description")
                
                if task.tags:
                    tags_check = task.tags.lower() if not args.case_sensitive else task.tags
                    if query_lower in tags_check:
                        matches.append("tags")
                
                if task.jira_issues:
                    jira_check = task.jira_issues.lower() if not args.case_sensitive else task.jira_issues
                    if query_lower in jira_check:
                        matches.append("JIRA")
                
                if matches:
                    task_matches.append({"task": task, "fields": matches})
        
        # Search workspaces
        if args.workspaces:
            for task in all_tasks:
                if not task.workspace_path or not task.id:
                    continue
                
                workspace_path = service.get_workspace_path(task.id)
                if not workspace_path or not workspace_path.exists():
                    continue
                
                try:
                    rg_args = ["rg", "--color", "never", "--files-with-matches", "--max-count", "5"]
                    
                    if not args.case_sensitive:
                        rg_args.append("--ignore-case")
                    
                    if args.pattern != "*":
                        rg_args.extend(["--glob", args.pattern])
                    
                    rg_args.extend(["--glob", "!.git", "--glob", "!tmp/*", "--glob", "!*.pyc", "--glob", "!__pycache__"])
                    rg_args.extend([args.query, str(workspace_path)])
                    
                    result = subprocess.run(rg_args, capture_output=True, text=True, timeout=5)
                    
                    if result.returncode == 0:
                        matched_files = result.stdout.strip().split("\n")
                        matched_files = [f.replace(str(workspace_path) + "/", "") for f in matched_files if f]
                        workspace_matches.append({"task": task, "files": matched_files})
                
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    continue
        
        # Display results
        if not task_matches and not workspace_matches:
            print(f"No matches found for: {args.query}")
            print(f"Searched: {total} task(s)")
            return
        
        print(f"Search Results for: {args.query}\n")
        print(f"Searched: {total} task(s)")
        print(f"Found: {len(task_matches)} task match(es), {len(workspace_matches)} workspace match(es)\n")
        
        # Show task matches
        if task_matches:
            print("Task Metadata Matches:")
            for match in task_matches[:20]:
                task = match["task"]
                fields = ", ".join(match["fields"])
                status_emoji = {"pending": "⭕", "in_progress": "🔄", "completed": "✅", "cancelled": "❌", "archived": "📦"}.get(task.status.value, "❓")
                print(f"{status_emoji} Task #{task.id}: {task.title}")
                print(f"   Matched in: {fields}")
                if task.workspace_path:
                    print("   📁 Has workspace")
                print()
        
        # Show workspace matches
        if workspace_matches:
            print("Workspace Content Matches:")
            for match in workspace_matches[:20]:
                task = match["task"]
                files = match["files"]
                status_emoji = {"pending": "⭕", "in_progress": "🔄", "completed": "✅", "cancelled": "❌", "archived": "📦"}.get(task.status.value, "❓")
                print(f"{status_emoji} Task #{task.id}: {task.title}")
                print(f"   Found in {len(files)} file(s):")
                for f in files[:5]:
                    print(f"      - {f}")
                if len(files) > 5:
                    print(f"      ... and {len(files) - 5} more")
                print()
    
    except FileNotFoundError:
        print("Error: ripgrep not found. Install with: brew install ripgrep", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {str(e)}", file=sys.stderr)
        sys.exit(1)


# Config sub-commands
def cmd_config_show(args):
    """Display current configuration."""
    settings = get_settings()
    
    print("\nCurrent Configuration")
    print("-" * 50)
    print(f"Profile:           {settings.profile}")
    print(f"Config Directory:  {settings.get_config_dir()}")
    print(f"Data Directory:    {settings.get_data_dir()}")
    print(f"Database URL:      {settings.get_database_url()}")
    print(f"Task List Limit:   {settings.defaults.task_limit}")
    print(f"Max Task Limit:    {settings.defaults.max_task_limit}")
    print(f"Log Level:         {settings.logging.level}")
    print(f"MCP Server Name:   {settings.mcp.server_name}")
    print()


def cmd_config_path(args):
    """Show configuration file location."""
    from taskmanager.config import get_user_config_path, get_project_config_path
    
    user_config = get_user_config_path()
    project_config = get_project_config_path()
    
    print(f"User config: {user_config}")
    if user_config.exists():
        print("  ✓ exists")
    else:
        print("  ✗ not found")
    
    if project_config:
        print(f"\nProject config: {project_config}")
        if project_config.exists():
            print("  ✓ exists")
        else:
            print("  ✗ not found")
    else:
        print("\nNot in a git repository")


def cmd_config_edit(args):
    """Open configuration file in editor."""
    from taskmanager.config import get_user_config_path, create_default_config
    
    config_path = get_user_config_path()
    
    # Create config if it doesn't exist
    if not config_path.exists():
        print("Config file doesn't exist. Creating default...")
        create_default_config(config_path)
        print(f"✓ Created {config_path}")
    
    # Try to find editor
    editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "nano"))
    
    try:
        subprocess.run([editor, str(config_path)], check=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Error opening editor '{editor}': {e}", file=sys.stderr)
        print(f"\nConfig file location: {config_path}")
        sys.exit(1)


# Profile management commands
def cmd_profile_list(args):
    """List all profile databases with metadata."""
    from taskmanager.repository_impl import SQLTaskRepository
    from taskmanager.service import TaskService

    settings = get_settings()
    service = TaskService(SQLTaskRepository(settings))

    try:
        profiles = service.list_profiles()
    except Exception as e:
        print(f"Error listing profiles: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        # JSON output for scripting
        import json

        output = [
            {
                "name": p.name,
                "database_path": str(p.database_path),
                "exists": p.exists,
                "size_bytes": p.size_bytes,
                "task_count": p.task_count,
                "configured": p.configured,
                "last_modified": p.last_modified.isoformat() if p.last_modified else None,
                "created": p.created.isoformat() if p.created else None,
            }
            for p in profiles
        ]
        print(json.dumps(output, indent=2))
    else:
        # Formatted table output
        if not profiles:
            print("No profiles found.")
            return

        print("\nProfile Database Audit:")
        print("-" * 100)

        headers = ["Profile", "Path", "Tasks", "Size", "Last Modified"]
        rows = []

        for p in profiles:
            size_kb = p.size_bytes / 1024 if p.size_bytes else 0
            last_mod = p.last_modified.strftime("%Y-%m-%d %H:%M") if p.last_modified else "unknown"
            rows.append(
                [
                    p.name,
                    str(p.database_path).replace(str(Path.home()), "~"),
                    str(p.task_count),
                    f"{size_kb:.1f} KB",
                    last_mod,
                ]
            )

        print_table(headers, rows)


def cmd_profile_audit(args):
    """Audit a profile before deletion."""
    from taskmanager.repository_impl import SQLTaskRepository
    from taskmanager.service import TaskService

    settings = get_settings()
    service = TaskService(SQLTaskRepository(settings))

    try:
        audit = service.audit_profile(args.profile)
    except Exception as e:
        print(f"Error auditing profile '{args.profile}': {e}", file=sys.stderr)
        sys.exit(1)

    print(f"\nProfile Audit: {audit.name}")
    print("-" * 60)
    print(f"Location:       {str(audit.location).replace(str(Path.home()), '~')}")
    print(f"Size:           {audit.size_bytes / 1024:.1f} KB")
    print(f"Task Count:     {audit.task_count}")
    print(
        f"Status:         {'Configured in settings.toml' if audit.configured else 'Auto-created'}"
    )
    print(
        f"Last Modified:  {audit.last_modified.strftime('%Y-%m-%d %H:%M %p') if audit.last_modified else 'unknown'}"
    )

    if audit.oldest_task:
        print(f"Oldest Task:    #{audit.oldest_task.id} - {audit.oldest_task.title}")
    else:
        print("Oldest Task:    (none)")

    if audit.newest_task:
        print(f"Newest Task:    #{audit.newest_task.id} - {audit.newest_task.title}")
    else:
        print("Newest Task:    (none)")
    print()


def cmd_profile_delete(args):
    """Delete a profile database and configuration."""
    from taskmanager.repository_impl import SQLTaskRepository
    from taskmanager.service import TaskService

    profile_name = args.profile

    # Protection for built-in profiles
    if profile_name in ["default", "dev", "test"]:
        print(f"❌ Cannot delete built-in profile '{profile_name}'", file=sys.stderr)
        sys.exit(1)

    settings = get_settings()
    service = TaskService(SQLTaskRepository(settings))

    # Show audit first
    try:
        audit = service.audit_profile(profile_name)
    except Exception as e:
        print(f"Error auditing profile '{profile_name}': {e}", file=sys.stderr)
        sys.exit(1)

    print(f"\nProfile to delete: {profile_name}")
    print(f"  Database: {str(audit.location).replace(str(Path.home()), '~')}")
    print(f"  Size: {audit.size_bytes / 1024:.1f} KB")
    print(f"  Tasks: {audit.task_count}")
    print(
        f"  Last modified: {audit.last_modified.strftime('%Y-%m-%d %H:%M %p') if audit.last_modified else 'unknown'}"
    )

    # Explicit confirmation
    confirmation = input(f"\nDelete profile '{profile_name}'? Type 'yes' to confirm: ")

    if confirmation != "yes":
        print("Cancelled.")
        return

    # Delete
    try:
        service.delete_profile(profile_name)
        print(f"✓ Deleted profile '{profile_name}'")
    except Exception as e:
        print(f"Error deleting profile: {e}", file=sys.stderr)
        sys.exit(1)


# Attachment sub-commands
def cmd_attach_add(args):
    """Attach a file to a task from file or stdin."""
    try:
        service = get_service()
        task_id = args.task_id
        file_arg = args.file_path
        filename_arg = args.filename
        
        # Determine source and filename
        if file_arg:
            # File input
            file_path = Path(file_arg)
            if not file_path.is_file():
                print(f"Error: Not a file: {file_arg}", file=sys.stderr)
                sys.exit(1)
            
            # Read file
            with open(file_path, 'rb') as f:
                content = f.read()
            
            # Use provided filename or extract from path
            filename = filename_arg or file_path.name
        else:
            # Stdin input
            if not filename_arg:
                print("Error: --filename is required when reading from stdin", file=sys.stderr)
                print("Usage: echo 'content' | tasks attach add TASK_ID --filename FILENAME.md", file=sys.stderr)
                sys.exit(1)
            
            # Read from stdin (binary mode)
            if hasattr(sys.stdin, 'buffer'):
                # Python 3: binary mode available
                content = sys.stdin.buffer.read()
            else:
                # Fallback: text mode
                content = sys.stdin.read().encode('utf-8')
            
            filename = filename_arg
        
        # Read file content
        file_content = file_path.read_bytes()
        original_filename = file_path.name
        
        # Add to database with dual-filename indexing
        attachment = service.add_db_attachment(args.task_id, original_filename, file_content)
        
        print(f"✓ Attached file to task #{args.task_id}")
        print(f"  Original name: {attachment.original_filename}")
        print(f"  Stored as: {attachment.storage_filename}")
        print(f"  Size: {attachment.size_bytes:,} bytes")
    
    except ValueError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


def cmd_attach_list(args):
    """List all attachments for a task."""
    try:
        service = get_service()
        attachments = service.list_db_attachments(args.task_id)
        
        if not attachments:
            print(f"Task #{args.task_id} has no attachments.")
            return
        
        print(f"\nAttachments for Task #{args.task_id}")
        print("-" * 80)
        
        for attachment in attachments:
            size_kb = attachment.size_bytes / 1024
            size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
            added_str = attachment.created_at.strftime("%Y-%m-%d %H:%M")
            
            print(f"  {attachment.original_filename}")
            print(f"    (stored as: {attachment.storage_filename}, {size_str})")
            print(f"    (added: {added_str})")
            print()
    
    except ValueError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


def cmd_attach_remove(args):
    """Remove an attachment from a task."""
    try:
        service = get_service()
        
        if not confirm_action(f"Remove attachment '{args.filename}' from task #{args.task_id}?", force=args.force):
            print("Removal cancelled.")
            sys.exit(0)
        
        removed = service.remove_attachment(args.task_id, args.filename)
        
        if removed:
            print(f"✓ Removed attachment '{args.filename}' from task #{args.task_id}")
        else:
            print(f"Attachment '{args.filename}' not found.")
            sys.exit(1)
    
    except ValueError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


def cmd_attach_open(args):
    """Open an attachment file."""
    try:
        service = get_service()
        file_path = service.get_attachment_path(args.task_id, args.filename)
        
        # Open the file using system default application
        if sys.platform == "darwin":  # macOS
            subprocess.run(["open", str(file_path)])
        elif sys.platform == "win32":  # Windows
            subprocess.run(["start", str(file_path)], shell=True)
        else:  # Linux
            subprocess.run(["xdg-open", str(file_path)])
        
        print(f"Opened: {args.filename}")
    
    except ValueError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


def cmd_attach_get(args):
    """Retrieve and display attachment content."""
    try:
        service = get_service()
        
        # Get attachment using dual-filename matching
        attachment = service.get_attachment_by_filename(args.task_id, args.filename)
        
        if attachment is None:
            print(f"Attachment '{args.filename}' not found for task #{args.task_id}", file=sys.stderr)
            sys.exit(1)
        
        content = attachment.file_data
        
        # Output based on format
        if args.format == "raw":
            # Raw bytes to stdout
            sys.stdout.buffer.write(content)
        elif args.format == "json":
            # JSON-encoded content
            output_dict = {
                "task_id": args.task_id,
                "original_filename": attachment.original_filename,
                "storage_filename": attachment.storage_filename,
                "content": content.decode('utf-8', errors='replace'),
                "size": len(content)
            }
            print(json.dumps(output_dict, indent=2))
        else:  # text format (default)
            # Decoded text with optional syntax highlighting
            try:
                text = content.decode('utf-8')
                print(text)
            except UnicodeDecodeError:
                print(f"Warning: Could not decode as UTF-8, showing as raw bytes", file=sys.stderr)
                sys.stdout.buffer.write(content)
                
    except Exception as e:
        print(f"Error retrieving attachment: {str(e)}", file=sys.stderr)
        sys.exit(1)


# Workspace sub-commands
def cmd_workspace_create(args):
    """Create a persistent workspace for a task."""
    try:
        service = get_service()
        metadata = service.create_workspace(task_id=args.task_id, initialize_git=not args.no_git)
        
        print(f"✓ Created workspace for task #{args.task_id}")
        print(f"  Path: {metadata['workspace_path']}")
        print(f"  Git initialized: {'Yes' if metadata['git_initialized'] else 'No'}")
    
    except ValueError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


def cmd_workspace_info(args):
    """Show workspace information for a task."""
    try:
        service = get_service()
        metadata = service.get_workspace_info(args.task_id)
        
        if not metadata:
            print(f"No workspace exists for task #{args.task_id}")
            sys.exit(0)
        
        print(f"\nWorkspace for Task #{args.task_id}")
        print(f"  Path: {metadata['workspace_path']}")
        print(f"  Created: {metadata['created_at']}")
        print(f"  Git initialized: {'Yes' if metadata['git_initialized'] else 'No'}")
        if metadata.get('last_accessed'):
            print(f"  Last accessed: {metadata['last_accessed']}")
    
    except ValueError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


def cmd_workspace_path(args):
    """Show the path to a task's workspace."""
    try:
        service = get_service()
        path = service.get_workspace_path(args.task_id)
        
        if not path:
            print(f"No workspace exists for task #{args.task_id}")
            sys.exit(0)
        
        print(str(path))
    
    except ValueError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


def cmd_workspace_open(args):
    """Open a task's workspace in Finder/Explorer."""
    try:
        service = get_service()
        path = service.get_workspace_path(args.task_id)
        
        if not path:
            print(f"No workspace exists for task #{args.task_id}")
            sys.exit(0)
        
        if not path.exists():
            print(f"Workspace directory does not exist: {path}", file=sys.stderr)
            sys.exit(1)
        
        # Open the directory
        if sys.platform == "darwin":  # macOS
            subprocess.run(["open", str(path)])
        elif sys.platform == "win32":  # Windows
            subprocess.run(["explorer", str(path)])
        else:  # Linux
            subprocess.run(["xdg-open", str(path)])
        
        print(f"Opened workspace: {path}")
    
    except ValueError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


def cmd_workspace_delete(args):
    """Delete a task's workspace and all its contents."""
    try:
        service = get_service()
        path = service.get_workspace_path(args.task_id)
        
        if not path:
            print(f"No workspace exists for task #{args.task_id}")
            sys.exit(0)
        
        if not confirm_action(f"Delete workspace for task #{args.task_id}? This will permanently remove all files in {path}", force=args.force):
            print("Deletion cancelled.")
            sys.exit(0)
        
        deleted = service.delete_workspace(args.task_id)
        
        if deleted:
            print(f"✓ Deleted workspace for task #{args.task_id}")
        else:
            print("Workspace deletion failed.")
            sys.exit(1)
    
    except ValueError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


def cmd_workspace_list(args):
    """List files in a task's workspace."""
    try:
        service = get_service()
        workspace_path = service.get_workspace_path(args.task_id)
        
        if not workspace_path:
            print(f"No workspace exists for task #{args.task_id}")
            sys.exit(0)
        
        target_path = Path(workspace_path) / args.subdirectory if args.subdirectory else Path(workspace_path)
        
        if not target_path.exists():
            print(f"Directory not found: {target_path}", file=sys.stderr)
            sys.exit(1)
        
        # Get matching files
        if args.pattern == "*":
            files = list(target_path.rglob("*"))
        else:
            files = list(target_path.rglob(args.pattern))
        
        # Filter to only files
        files = [f for f in files if f.is_file()]
        files = [f for f in files if ".git" not in str(f) and "__pycache__" not in str(f)]
        
        if not files:
            print("No files found")
            sys.exit(0)
        
        # Sort by modification time
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        
        print(f"\nFiles in workspace for task #{args.task_id}")
        print(f"Path: {target_path}")
        print(f"Pattern: {args.pattern}")
        print(f"Found: {len(files)} file(s)\n")
        
        for f in files[:50]:
            relative_path = f.relative_to(workspace_path)
            size = f.stat().st_size
            modified = datetime.fromtimestamp(f.stat().st_mtime)
            
            # Format size
            if size < 1024:
                size_str = f"{size}B"
            elif size < 1024 * 1024:
                size_str = f"{size / 1024:.1f}KB"
            else:
                size_str = f"{size / (1024 * 1024):.1f}MB"
            
            print(f"  {relative_path} - {size_str} - {modified.strftime('%Y-%m-%d %H:%M')}")
        
        if len(files) > 50:
            print(f"\n... and {len(files) - 50} more files")
    
    except ValueError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


def _gather_initial_context(service, settings):
    """Gather initial task context for Claude session.
    
    Args:
        service: TaskService instance
        settings: Settings instance from get_settings()
    
    Returns:
        Tuple of (display_text, context_prompt) where:
        - display_text: Plain text to show user before session starts
        - context_prompt: Structured context to pass to Claude as initial message
    """
    from datetime import date, datetime
    from zoneinfo import ZoneInfo
    from taskmanager.models import TaskStatus, Priority
    
    # Get current time in user's local timezone
    tz = ZoneInfo(settings.timezone)
    now = datetime.now(tz)
    current_time_str = now.strftime("%A, %B %d, %Y at %I:%M %p %Z")
    
    # Gather task statistics
    all_tasks, _ = service.list_tasks(limit=100)  # Get up to 100 tasks for overview
    in_progress = [t for t in all_tasks if t.status == TaskStatus.IN_PROGRESS]
    pending = [t for t in all_tasks if t.status == TaskStatus.PENDING]
    overdue = [t for t in all_tasks if t.due_date and t.due_date < date.today() and t.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]]
    high_priority = [t for t in all_tasks if t.priority == Priority.HIGH and t.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]]
    urgent_priority = [t for t in all_tasks if t.priority == Priority.URGENT and t.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]]
    
    # Build display text for user (plain text, no Rich formatting)
    display_parts = []
    display_parts.append("📊 Current Task Context\n")
    display_parts.append(f"Current time: {current_time_str}")
    
    profile_name = settings.profile
    display_parts.append(f"Profile: {profile_name}")
    display_parts.append(f"Total tasks: {len(all_tasks)}")
    
    if urgent_priority:
        display_parts.append(f"⚡ Urgent: {len(urgent_priority)}")
    if high_priority:
        display_parts.append(f"⚠️  High priority: {len(high_priority)}")
    if overdue:
        display_parts.append(f"⏰ Overdue: {len(overdue)}")
    if in_progress:
        display_parts.append(f"▶️  In progress: {len(in_progress)}")
    if pending:
        display_parts.append(f"⏸️  Pending: {len(pending)}")
    
    display_text = "\n".join(display_parts)
    
    # Build structured context for Claude
    context_parts = []
    context_parts.append("# Initial Task Context\n")
    context_parts.append(f"**Current Time:** {current_time_str}")
    context_parts.append(f"**Today's Date:** {now.strftime('%Y-%m-%d')}")
    context_parts.append(f"**Day of Week:** {now.strftime('%A')}")
    context_parts.append(f"**Timezone:** {settings.timezone}")
    context_parts.append(f"**Weekend:** {'Yes' if now.weekday() >= 5 else 'No'}\n")
    context_parts.append(f"**Profile:** {profile_name}")
    context_parts.append(f"**Total tasks:** {len(all_tasks)}\n")
    
    if urgent_priority:
        context_parts.append(f"## 🚨 Urgent Tasks ({len(urgent_priority)})")
        for task in urgent_priority[:5]:  # Show up to 5
            context_parts.append(f"- **#{task.id}** {task.title} [{task.status.value}]")
        if len(urgent_priority) > 5:
            context_parts.append(f"  _(and {len(urgent_priority) - 5} more)_")
        context_parts.append("")
    
    if overdue:
        context_parts.append(f"## ⏰ Overdue Tasks ({len(overdue)})")
        for task in overdue[:5]:
            context_parts.append(f"- **#{task.id}** {task.title} (due {task.due_date}) [{task.status.value}]")
        if len(overdue) > 5:
            context_parts.append(f"  _(and {len(overdue) - 5} more)_")
        context_parts.append("")
    
    if in_progress:
        context_parts.append(f"## ▶️ In Progress ({len(in_progress)})")
        for task in in_progress[:5]:
            jira_info = f" - JIRA: {task.jira_issues}" if task.jira_issues else ""
            context_parts.append(f"- **#{task.id}** {task.title} [{task.priority.value}]{jira_info}")
        if len(in_progress) > 5:
            context_parts.append(f"  _(and {len(in_progress) - 5} more)_")
        context_parts.append("")
    
    if high_priority and not urgent_priority:
        context_parts.append(f"## ⚠️ High Priority Tasks ({len(high_priority)})")
        for task in high_priority[:3]:
            context_parts.append(f"- **#{task.id}** {task.title} [{task.status.value}]")
        if len(high_priority) > 3:
            context_parts.append(f"  _(and {len(high_priority) - 3} more)_")
        context_parts.append("")
    
    context_parts.append("\n**I'm ready to help you with your tasks. What would you like to work on?**")
    
    context_prompt = "\n".join(context_parts)
    
    return display_text, context_prompt


def cmd_chat(args):
    """Launch Claude agent session with task and JIRA context."""
    try:
        import json
        import tempfile
        import shutil
        from datetime import datetime
        
        service = get_service()
        settings = get_settings()
        
        # Verify claude CLI is available
        try:
            subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                check=True,
                timeout=5
            )
        except (FileNotFoundError, subprocess.CalledProcessError):
            print("Error: 'claude' CLI not found or not working", file=sys.stderr)
            print("Install Claude CLI: https://github.com/anthropics/anthropic-sdk-python")
            sys.exit(1)
        
        # Determine the working directory
        working_dir = Path.cwd()
        if args.task_id:
            # Get or create workspace for the task
            workspace_path = service.get_workspace_path(args.task_id)
            if not workspace_path:
                print(f"No workspace exists for task #{args.task_id}. Creating one...")
                service.create_workspace(task_id=args.task_id, initialize_git=True)
                workspace_path = service.get_workspace_path(args.task_id)
            
            if workspace_path:
                working_dir = workspace_path
                print(f"Opening chat session for task #{args.task_id}")
        
        # Prepare environment with MCP server configuration
        env = os.environ.copy()
        
        # Get current profile to ensure MCP server uses the same profile
        current_profile = settings.profile
        
        # Get profile modifier if configured for this profile
        profile_modifier = settings.get_profile_modifier()
        
        # Build MCP servers configuration for claude CLI
        # Important: Pass profile to tasks-mcp server so all operations use the correct profile
        mcp_servers = {
            "tasks": {
                "command": "tasks-mcp",
                "env": {
                    "TASKMANAGER_PROFILE": current_profile
                }
            }
        }
        
        # Apply profile modifiers to tasks-mcp if configured
        if profile_modifier and "tasks-mcp" in profile_modifier.mcp_servers:
            tasks_modifier = profile_modifier.mcp_servers["tasks-mcp"]
            if tasks_modifier.command:
                mcp_servers["tasks"]["command"] = tasks_modifier.command
            if tasks_modifier.args:
                mcp_servers["tasks"]["args"] = tasks_modifier.args
            if tasks_modifier.env:
                mcp_servers["tasks"]["env"].update(tasks_modifier.env)
        
        # Add atlassian-mcp with credentials from config file
        atlassian_config = settings.atlassian.resolve_secrets()
        
        # Check if we have atlassian credentials configured
        if atlassian_config.jira_url and atlassian_config.jira_token:
            atlassian_env = {
                "JIRA_URL": atlassian_config.jira_url,
                "JIRA_SSL_VERIFY": str(atlassian_config.jira_ssl_verify).lower(),
            }
            
            if atlassian_config.jira_username:
                atlassian_env["JIRA_USERNAME"] = atlassian_config.jira_username
            if atlassian_config.jira_token:
                atlassian_env["JIRA_PERSONAL_TOKEN"] = atlassian_config.jira_token
            
            if atlassian_config.confluence_url:
                atlassian_env["CONFLUENCE_URL"] = atlassian_config.confluence_url
            if atlassian_config.confluence_username:
                atlassian_env["CONFLUENCE_USERNAME"] = atlassian_config.confluence_username
            if atlassian_config.confluence_token:
                atlassian_env["CONFLUENCE_PERSONAL_TOKEN"] = atlassian_config.confluence_token
            if atlassian_config.confluence_url:
                atlassian_env["CONFLUENCE_SSL_VERIFY"] = str(atlassian_config.confluence_ssl_verify).lower()
            
            mcp_servers["atlassian"] = {
                "command": "uvx",
                "args": ["--native-tls", "mcp-atlassian"],
                "env": atlassian_env
            }
            
            # Apply profile modifiers to atlassian-mcp if configured
            if profile_modifier and "atlassian-mcp" in profile_modifier.mcp_servers:
                atlassian_modifier = profile_modifier.mcp_servers["atlassian-mcp"]
                if atlassian_modifier.command:
                    mcp_servers["atlassian"]["command"] = atlassian_modifier.command
                if atlassian_modifier.args:
                    mcp_servers["atlassian"]["args"] = atlassian_modifier.args
                if atlassian_modifier.env:
                    mcp_servers["atlassian"]["env"].update(atlassian_modifier.env)
            
            print("✓ Atlassian credentials loaded from configuration")
        else:
            print("Warning: Atlassian credentials not configured")
            print("  Configure in ~/.taskmanager/config.toml under [atlassian]")
            print("  Required: jira_url, jira_token")
            print("  Optional: jira_username, confluence_url, confluence_username, confluence_token")
        
        # Set environment for claude CLI
        env["MCP_SERVERS"] = json.dumps(mcp_servers)
        
        # Gather and display initial context (unless disabled)
        initial_prompt = None
        if not args.no_context:
            try:
                display_text, context_prompt = _gather_initial_context(service, settings)
                print(f"\n{display_text}\n")
                initial_prompt = context_prompt
            except Exception as e:
                print(f"Warning: Could not load initial context: {e}")
        
        # Build comprehensive system prompt for the claude session
        system_prompt = """# Mission: Smart Assistant for Task & JIRA Management

You are a specialized AI assistant with expertise in task management and JIRA/Confluence operations. Your primary mission is to help users efficiently manage their work using two MCP servers:

## Available MCP Tools

### 1. tasks-mcp Server
The tasks-mcp server provides comprehensive task management capabilities:

**Core Operations:**
- `mcp_tasks-mcp_list_tasks` - List tasks with filtering (status, priority, tag, overdue)
- `mcp_tasks-mcp_get_task` - Get detailed information about a specific task
- `mcp_tasks-mcp_create_task` - Create new tasks (use interactive version for guided creation)
- `mcp_tasks-mcp_update_task` - Update task fields (title, description, priority, status, due date, tags, JIRA issues)
- `mcp_tasks-mcp_complete_task` - Mark a task as completed
- `mcp_tasks-mcp_delete_task` - Delete a task (use interactive version for confirmation)

**Workspace Operations:**
- `mcp_tasks-mcp_create_workspace` - Create persistent workspace directory structure for a task
- `mcp_tasks-mcp_get_workspace_info` - Get workspace metadata and path information
- `mcp_tasks-mcp_get_workspace_path` - Get absolute filesystem path to a task's workspace
- `mcp_tasks-mcp_list_workspace_files` - Browse workspace directory contents
- `mcp_tasks-mcp_search_workspace` - Search for content within a task's workspace files
- `mcp_tasks-mcp_delete_workspace` - Delete a task's workspace (destructive)

**Search & Discovery:**
- `mcp_tasks-mcp_search_all_tasks` - Comprehensive search across task metadata and workspace content

**Time Awareness:**
- `mcp_tasks-mcp_get_current_time` - Get current timestamp with timezone info (ISO 8601, unix timestamp, day of week, weekend detection)
- `mcp_tasks-mcp_format_datetime` - Format and convert datetime strings with timezone support
- `mcp_tasks-mcp_calculate_time_delta` - Calculate time differences for deadline tracking and scheduling

**Best Practices for tasks-mcp:**
- Use interactive versions (`create_task_interactive`, `update_task_interactive`, `delete_task_interactive`) when you need guidance or confirmation
- Always ensure workspace exists before working with task files
- Tasks can have JIRA issues linked via comma-separated keys (e.g., "SRE-1234,DEVOPS-5678")
- Workspaces provide organized structure: notes/, code/, logs/, tmp/
- Use time-awareness tools for accurate schedule operations, deadline calculations, and time-sensitive workflows
- All timezone operations support IANA timezone names (UTC, America/New_York, Europe/London, etc.)

### 2. atlassian-mcp Server
The atlassian-mcp server provides JIRA and Confluence integration (when credentials are configured):

**JIRA Operations:**
- Search and retrieve JIRA issues
- View issue details, comments, and attachments
- Create and update issues
- Manage issue transitions (workflow states)

**Confluence Operations:**
- Search and retrieve Confluence pages
- View page content and metadata
- Create and update pages

**Best Practices for atlassian-mcp:**
- JIRA issue keys follow pattern: PROJECT-NUMBER (e.g., SRE-1234)
- Link JIRA issues to tasks using the jira_issues field
- Search before creating to avoid duplicates

## Initial Context Gathering

When starting a new session, please:

1. **Be aware of current time:**
   - The current date and time are provided in the initial context
   - Use this for deadline discussions and deadline-aware operations
   - Check for overdue tasks by comparing due dates to today's date

2. **Understand the current profile context:**
   - List recent tasks to understand what's in flight
   - Identify high-priority or urgent items
   - Check if there are related JIRA issues

3. **Assess the work environment:**
   - Note which tasks are in progress vs pending
   - Look for high-priority items
   - Check if there are related JIRA issues

4. **Ask clarifying questions:**
   - What would you like to focus on today?
   - Should we review existing tasks or start something new?
   - Are there specific JIRA issues you're working on?

## Operational Guidelines

- **Safety First:** Always confirm before destructive operations (delete, major updates)
- **Context Aware:** Consider task status, priority, and deadlines when making suggestions
- **Time Aware:** Use current time tools to provide accurate schedule information and deadline calculations. Always check current time when discussing due dates or time-sensitive tasks.
- **Proactive:** Suggest related JIRA issues or tasks that might be relevant
- **Organized:** Use workspace features to keep notes, code, and logs structured
- **Efficient:** Batch similar operations when appropriate
- **Transparent:** Explain what you're doing and why, especially for complex operations

## Communication Standards

- **Always Use Numeric Task IDs:** When referring to tasks in your responses, ALWAYS include the numeric task ID (e.g., "task #27" or "#27") even when using natural language descriptions. Never refer to tasks by title alone.
  - ✅ GOOD: "I've updated task #27 (Context initialization defect)"
  - ✅ GOOD: "Let's work on #27"
  - ❌ BAD: "I've updated the context initialization defect task"
  - ❌ BAD: "Let's work on that task"
- **JIRA References:** Similarly, always include JIRA issue keys when discussing JIRA items (e.g., "SRE-1234")
- **Clarity:** This ensures precise communication and avoids ambiguity when discussing multiple tasks

"""
        
        # Add current task context if provided
        if args.task_id:
            task = service.get_task(args.task_id)
            system_prompt += f"\n## Current Task Focus\n\n"
            system_prompt += f"You are currently working in the context of:\n\n"
            system_prompt += f"- **Task ID:** #{task.id}\n"
            system_prompt += f"- **Title:** {task.title}\n"
            system_prompt += f"- **Status:** {task.status.value}\n"
            system_prompt += f"- **Priority:** {task.priority.value}\n"
            if task.description:
                system_prompt += f"- **Description:** {task.description}\n"
            if task.due_date:
                system_prompt += f"- **Due Date:** {task.due_date}\n"
            if task.jira_issues:
                system_prompt += f"- **Related JIRA Issues:** {task.jira_issues}\n"
            if task.tags:
                system_prompt += f"- **Tags:** {', '.join(task.tags)}\n"
            system_prompt += f"- **Workspace:** {working_dir}\n"
            system_prompt += f"\nPlease help the user work on this task efficiently.\n"
        
        # Add profile-specific prompt additions if configured
        if profile_modifier and profile_modifier.prompt_additions:
            system_prompt += f"\n## Profile-Specific Instructions\n\n{profile_modifier.prompt_additions}\n"
        
        try:
            # Launch claude CLI with comprehensive system prompt and initial context
            print("\nStarting Claude agent session...")
            print("Type 'exit' or Ctrl+D to end the session\n")
            
            # Create ephemeral session directory with settings.json
            session_dir, session_env = create_ephemeral_session_dir(system_prompt, str(working_dir))
            
            # Merge session environment with existing environment
            full_env = env.copy()
            full_env.update(session_env)
            
            # Debug: Copy config files to /tmp for inspection
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            debug_dir = Path(f"/tmp/tasks-chat-debug-{timestamp}")
            debug_dir.mkdir(exist_ok=True)
            
            # Copy the config files
            shutil.copy(f"{session_dir}/.claude/settings.json", debug_dir / "settings.json")
            shutil.copy(f"{session_dir}/.mcp.json", debug_dir / "mcp.json")
            
            # Write env vars to a file
            with open(debug_dir / "env.txt", 'w') as f:
                f.write(f"Session directory: {session_dir}\n")
                f.write(f"CLAUDE_CONFIG_DIR: {session_env['CLAUDE_CONFIG_DIR']}\n")
                f.write(f"CLAUDE_CODE_TMPDIR: {session_env.get('CLAUDE_CODE_TMPDIR', 'not set')}\n")
                f.write(f"HOME: {session_env.get('HOME', 'not overridden')}\n")
            
            print(f"Debug config copied to: {debug_dir}\n")
            
            # Build claude command with strict MCP config flags
            # --mcp-config: Specifies the path to our MCP servers JSON
            # --strict-mcp-config: Ignores global MCP servers from ~/.claude.json
            # --allowed-tools: Auto-approve all MCP tools without prompting
            mcp_config_path = session_dir / ".mcp.json"
            claude_cmd = [
                "claude",
                "--mcp-config", str(mcp_config_path),
                "--strict-mcp-config",
                "--allowed-tools", "mcp__tasks-mcp__*", "mcp__atlassian-mcp__*"
            ]
            
            # Run claude with initial prompt via stdin
            subprocess.run(
                claude_cmd,
                cwd=str(working_dir),
                env=full_env,
                input=initial_prompt,
                text=True,
                check=False
            )
            
            print("\n✓ Claude session ended")
            print(f"Debug config at: {debug_dir}")
            print(f"Session dir: {session_dir}")
        except Exception as e:
            print(f"Error: {str(e)}", file=sys.stderr)
            sys.exit(1)
        
    except ValueError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {str(e)}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main entry point for the CLI."""
    # Define all subcommands for abbreviation expansion
    subcommands = ['add', 'new', 'list', 'show', 'update', 'complete', 'delete', 'tags', 'search', 
                   'config', 'attach', 'workspace', 'chat']
    
    # Expand abbreviations in sys.argv before parsing
    sys.argv = expand_abbreviations(sys.argv, subcommands)
    
    # Create the main parser with abbreviation support
    parser = HelpfulArgumentParser(
        prog='tasks',
        description='A powerful CLI task manager for organizing your work and life.',
        allow_abbrev=True,
    )
    
    parser.add_argument('-V', '--version', action='version', version=f'tasks {get_version()}')
    parser.add_argument('-c', '--config', type=Path, help='Path to configuration file')
    parser.add_argument('-p', '--profile', help='Configuration profile (default, dev, test)')
    parser.add_argument('-d', '--database', help='Database URL override')
    
    # Add shell completion support if shtab is available
    if SHTAB_AVAILABLE:
        shtab.add_argument_to(parser, ['-s', '--print-completion'])
    
    # Create subparsers - note: parser_class inherits allow_abbrev from parent
    subparsers = parser.add_subparsers(dest='command', help='Available commands', parser_class=HelpfulArgumentParser)
    
    # Add command
    add_parser = subparsers.add_parser('add', help='Create a new task', aliases=['new'])
    add_parser.add_argument('title', help='Task title')
    add_parser.add_argument('-d', '--description', help='Task description')
    add_parser.add_argument('-p', '--priority', choices=['low', 'medium', 'high', 'urgent'], help='Task priority')
    add_parser.add_argument('--due', help='Due date (YYYY-MM-DD)')
    add_parser.add_argument('-s', '--status', choices=['pending', 'in_progress', 'completed', 'cancelled', 'archived'], help='Initial status')
    add_parser.add_argument('-j', '--jira', help='JIRA issue keys (comma-separated)')
    add_parser.add_argument('-t', '--tags', help='Tags (comma-separated)')
    add_parser.set_defaults(func=cmd_add)
    
    # List command
    list_parser = subparsers.add_parser('list', help='List tasks with optional filtering')
    list_parser.add_argument('-s', '--status', help='Filter by status')
    list_parser.add_argument('-p', '--priority', help='Filter by priority')
    list_parser.add_argument('--tag', help='Filter by tag (partial match)')
    list_parser.add_argument('-l', '--limit', type=int, default=20, help='Maximum number of tasks to show')
    list_parser.add_argument('--offset', type=int, default=0, help='Number of tasks to skip')
    list_parser.add_argument('-f', '--format', choices=['table', 'simple', 'json'], default='table', help='Output format')
    list_parser.add_argument('-a', '--all', action='store_true', help='Show all tasks including completed, cancelled, and archived')
    list_parser.add_argument('--show-tags', action='store_true', help='Show tags column in table')
    list_parser.add_argument('--show-jira', type=int, nargs='?', const=0, default=None, help='Show JIRA issues column')
    list_parser.add_argument('--show-created', action='store_true', help='Show created date column in table')
    list_parser.add_argument('--show-updated', action='store_true', help='Show updated date column in table')
    list_parser.set_defaults(func=cmd_list)
    
    # Show command
    show_parser = subparsers.add_parser('show', help='Show detailed information about a specific task')
    show_parser.add_argument('task_id', type=int, help='Task ID to display')
    show_parser.set_defaults(func=cmd_show)
    
    # Update command
    update_parser = subparsers.add_parser('update', help='Update an existing task')
    update_parser.add_argument('task_id', type=int, help='Task ID to update')
    update_parser.add_argument('-t', '--title', help='New title')
    update_parser.add_argument('-d', '--description', help='New description')
    update_parser.add_argument('-p', '--priority', choices=['low', 'medium', 'high', 'urgent'], help='New priority')
    update_parser.add_argument('-s', '--status', choices=['pending', 'in_progress', 'completed', 'cancelled', 'archived'], help='New status')
    update_parser.add_argument('--due', help='New due date (YYYY-MM-DD)')
    update_parser.add_argument('-j', '--jira', help='JIRA issue keys (comma-separated)')
    update_parser.add_argument('--tags', help='Tags (comma-separated)')
    update_parser.add_argument('--clear-description', action='store_true', help='Clear the description')
    update_parser.add_argument('--clear-due', action='store_true', help='Clear the due date')
    update_parser.add_argument('--clear-jira', action='store_true', help='Clear JIRA issues')
    update_parser.add_argument('--clear-tags', action='store_true', help='Clear tags')
    update_parser.set_defaults(func=cmd_update)
    
    # Complete command
    complete_parser = subparsers.add_parser('complete', help='Mark a task as complete')
    complete_parser.add_argument('task_id', type=int, help='Task ID to complete')
    complete_parser.set_defaults(func=cmd_complete)
    
    # Delete command
    delete_parser = subparsers.add_parser('delete', help='Delete a task permanently')
    delete_parser.add_argument('task_id', type=int, help='Task ID to delete')
    delete_parser.add_argument('--force', action='store_true', help='Skip confirmation')
    delete_parser.set_defaults(func=cmd_delete)
    
    # Tags command
    tags_parser = subparsers.add_parser('tags', help='List all unique tags')
    tags_parser.set_defaults(func=cmd_tags)
    
    # Search command
    search_parser = subparsers.add_parser('search', help='Search across all tasks and workspaces')
    search_parser.add_argument('query', help='Search query')
    search_parser.add_argument('--workspaces', action='store_true', default=True, help='Search workspace files (default: True)')
    search_parser.add_argument('--no-workspaces', action='store_false', dest='workspaces', help='Skip workspace search')
    search_parser.add_argument('--tasks', action='store_true', default=True, help='Search task metadata (default: True)')
    search_parser.add_argument('--no-tasks', action='store_false', dest='tasks', help='Skip task metadata search')
    search_parser.add_argument('-p', '--pattern', default='*', help='File pattern for workspace search')
    search_parser.add_argument('-c', '--case-sensitive', action='store_true', help='Case sensitive search')
    search_parser.add_argument('-s', '--status', default='all', help='Filter by status')
    search_parser.set_defaults(func=cmd_search)
    
    # Config sub-commands
    config_parser = subparsers.add_parser('config', help='Manage configuration')
    config_subparsers = config_parser.add_subparsers(dest='config_command', help='Config commands')
    
    config_show = config_subparsers.add_parser('show', help='Display current configuration')
    config_show.set_defaults(func=cmd_config_show)
    
    config_path = config_subparsers.add_parser('path', help='Show configuration file location')
    config_path.set_defaults(func=cmd_config_path)
    
    config_edit = config_subparsers.add_parser('edit', help='Open configuration file in editor')
    config_edit.set_defaults(func=cmd_config_edit)
    
    # Profile sub-commands
    profile_parser = subparsers.add_parser('profile', help='Manage database profiles')
    profile_subparsers = profile_parser.add_subparsers(dest='profile_command', help='Profile commands')
    
    profile_list = profile_subparsers.add_parser('list', help='List all profile databases')
    profile_list.add_argument('--json', action='store_true', help='Output as JSON for scripting')
    profile_list.add_argument('--configured-only', action='store_true', help='Show only configured profiles (exclude auto-created)')
    profile_list.set_defaults(func=cmd_profile_list)
    
    profile_audit = profile_subparsers.add_parser('audit', help='Audit a profile before deletion')
    profile_audit.add_argument('profile', help='Profile name to audit')
    profile_audit.set_defaults(func=cmd_profile_audit)
    
    profile_delete = profile_subparsers.add_parser('delete', help='Delete a profile (CLI-only for safety)')
    profile_delete.add_argument('profile', help='Profile name to delete')
    profile_delete.set_defaults(func=cmd_profile_delete)
    
    # Attach sub-commands
    attach_parser = subparsers.add_parser('attach', help='Manage task attachments')
    attach_subparsers = attach_parser.add_subparsers(dest='attach_command', help='Attachment commands')
    
    attach_add = attach_subparsers.add_parser('add', help='Attach a file to a task')
    attach_add.add_argument('task_id', type=int, help='Task ID to attach file to')
    attach_add.add_argument('file_path', nargs='?', help='Path to file to attach (optional, reads stdin if missing)')
    attach_add.add_argument('-f', '--filename', help='Attachment filename (required when reading from stdin)')
    attach_add.set_defaults(func=cmd_attach_add)
    
    attach_list = attach_subparsers.add_parser('list', help='List all attachments for a task')
    attach_list.add_argument('task_id', type=int, help='Task ID to list attachments for')
    attach_list.set_defaults(func=cmd_attach_list)
    
    attach_remove = attach_subparsers.add_parser('remove', help='Remove an attachment from a task')
    attach_remove.add_argument('task_id', type=int, help='Task ID')
    attach_remove.add_argument('filename', help='Filename of attachment to remove')
    attach_remove.add_argument('--force', action='store_true', help='Skip confirmation')
    attach_remove.set_defaults(func=cmd_attach_remove)
    
    attach_open = attach_subparsers.add_parser('open', help='Open an attachment file')
    attach_open.add_argument('task_id', type=int, help='Task ID')
    attach_open.add_argument('filename', help='Filename of attachment to open')
    attach_open.set_defaults(func=cmd_attach_open)
    
    attach_get = attach_subparsers.add_parser('get', help='Retrieve attachment file content')
    attach_get.add_argument('task_id', type=int, help='Task ID')
    attach_get.add_argument('filename', help='Attachment filename')
    attach_get.add_argument(
        '-f', '--format',
        choices=['raw', 'text', 'json'],
        default='text',
        help='Output format (default: text)'
    )
    attach_get.set_defaults(func=cmd_attach_get)
    
    # Workspace sub-commands
    workspace_parser = subparsers.add_parser('workspace', help='Manage task workspaces')
    workspace_subparsers = workspace_parser.add_subparsers(dest='workspace_command', help='Workspace commands')
    
    workspace_create = workspace_subparsers.add_parser('create', help='Create a persistent workspace for a task')
    workspace_create.add_argument('task_id', type=int, help='Task ID to create workspace for')
    workspace_create.add_argument('--no-git', action='store_true', help='Skip git initialization')
    workspace_create.set_defaults(func=cmd_workspace_create)
    
    workspace_info = workspace_subparsers.add_parser('info', help='Show workspace information for a task')
    workspace_info.add_argument('task_id', type=int, help='Task ID')
    workspace_info.set_defaults(func=cmd_workspace_info)
    
    workspace_path = workspace_subparsers.add_parser('path', help="Show the path to a task's workspace")
    workspace_path.add_argument('task_id', type=int, help='Task ID')
    workspace_path.set_defaults(func=cmd_workspace_path)
    
    workspace_open = workspace_subparsers.add_parser('open', help="Open a task's workspace in Finder/Explorer")
    workspace_open.add_argument('task_id', type=int, help='Task ID')
    workspace_open.set_defaults(func=cmd_workspace_open)
    
    workspace_delete = workspace_subparsers.add_parser('delete', help="Delete a task's workspace and all its contents")
    workspace_delete.add_argument('task_id', type=int, help='Task ID')
    workspace_delete.add_argument('--force', action='store_true', help='Skip confirmation')
    workspace_delete.set_defaults(func=cmd_workspace_delete)
    
    workspace_list = workspace_subparsers.add_parser('list', help="List files in a task's workspace")
    workspace_list.add_argument('task_id', type=int, help='Task ID')
    workspace_list.add_argument('-d', '--subdirectory', default='', help='Subdirectory to list')
    workspace_list.add_argument('-p', '--pattern', default='*', help='File pattern (e.g., *.py, *.md)')
    workspace_list.set_defaults(func=cmd_workspace_list)
    
    # Chat command
    chat_parser = subparsers.add_parser('chat', help='Launch Claude agent session with task and JIRA context')
    chat_parser.add_argument('task_id', nargs='?', type=int, help='Optional task ID to focus on')
    chat_parser.add_argument('--no-context', action='store_true', help='Skip automatic context loading')
    chat_parser.set_defaults(func=cmd_chat)
    
    # Parse arguments
    args = parser.parse_args()
    
    # Handle global options
    if args.profile or args.database or args.config:
        settings = get_settings()
        if args.profile:
            settings.profile = args.profile
        if args.database:
            settings.database_url = args.database
        # Config file handling would go here
    
    # Execute command
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
