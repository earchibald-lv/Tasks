# Tasks - Personal Task Manager

A dual-interface task management system with a beautiful CLI and an AI-powered MCP server featuring FastMCP 3.0 User Elicitation for interactive forms.

## Features

### Core Capabilities
- ✅ **Dual Interface**: Traditional CLI + MCP server for AI agents
- ✅ **Shared Database**: Both interfaces use the same SQLite database
- ✅ **Beautiful CLI**: Rich terminal output with tables, colors, and emoji
- ✅ **Interactive Forms**: FastMCP 3.0 User Elicitation with accept/decline/cancel workflows
- ✅ **Type-Safe**: Full type hints with Pydantic validation
- ✅ **Layered Architecture**: Clean separation between interfaces, services, and data

### Task Management
- Create, read, update, and delete tasks
- Priority levels: Low, Medium, High, Urgent
- Status tracking: Pending, In Progress, Completed, Archived
- Due date management with overdue detection
- Rich task descriptions and metadata

## Installation

### Prerequisites
- Python 3.12 or 3.13
- pipx (recommended) or pip

### Install CLI & MCP Server

```bash
# Install in editable mode for development
pipx install -e .

# Or install from source
pipx install .
```

This installs two commands:
- `tasks` - CLI interface
- `tasks-mcp` - MCP server for AI agents

### Verify Installation

```bash
# Test CLI
tasks --version

# Test MCP server (shows server info)
tasks-mcp --version
```

## CLI Usage

### Quick Start

```bash
# Add a new task
tasks add "Review PR #123" --priority high --due 2026-02-01

# List all pending tasks
tasks list --status pending

# Show task details
tasks show 1

# Update a task
tasks update 1 --status in_progress

# Mark task complete
tasks complete 1

# Delete a task
tasks delete 1
```

### Commands Reference

#### `tasks add` - Create a new task

```bash
tasks add "<title>" [options]

Options:
  --description TEXT              Task description
  --priority [low|medium|high|urgent]
  --due YYYY-MM-DD               Due date
  --status [pending|in_progress|completed|archived]
  --jira TEXT                    JIRA issue keys (comma-separated)
```

**Examples:**
```bash
tasks add "Implement login feature"
tasks add "Bug fix" --priority urgent --due 2026-01-30
tasks add "Write docs" --description "API documentation" --priority high
tasks add "Fix auth" --jira "SRE-1234,DEVOPS-5678" --priority urgent
```

#### `tasks list` - List tasks

```bash
tasks list [options]

Options:
  --status [pending|in_progress|completed|archived]
  --priority [low|medium|high|urgent]
  --limit INTEGER                Max results (default: 20)
  --offset INTEGER               Pagination offset
```

**Examples:**
```bash
tasks list
tasks list --status pending --priority high
tasks list --limit 50
```

#### `tasks show` - Show task details

```bash
tasks show <task_id>
```

**Example:**
```bash
tasks show 42
```

#### `tasks update` - Update a task

```bash
tasks update <task_id> [options]

Options:
  --title TEXT
  --description TEXT
  --priority [low|medium|high|urgent]
  --status [pending|in_progress|completed|archived]
  --due YYYY-MM-DD
  --jira TEXT                    JIRA issue keys (comma-separated)
  --clear-description            Clear the description
  --clear-due                    Clear the due date
  --clear-jira                   Clear JIRA issues
```

**Examples:**
```bash
tasks update 1 --status in_progress
tasks update 1 --priority urgent --due 2026-01-30
tasks update 1 --title "New title" --description "New description"
tasks update 1 --jira "SRE-1234,DEVOPS-5678"
tasks update 1 --clear-jira
```

#### `tasks complete` - Mark task as complete

```bash
tasks complete <task_id>
```

**Example:**
```bash
tasks complete 1
```

#### `tasks delete` - Delete a task

```bash
tasks delete <task_id>
```

**Example:**
```bash
tasks delete 1
```

## MCP Server Integration

The MCP server enables AI agents (like Claude in VS Code) to manage your tasks through natural language.

### FastMCP 3.0 with User Elicitation

This project uses **FastMCP 3.0.0b1** (beta) with User Elicitation, enabling interactive forms directly in VS Code.

**What is User Elicitation?**
- Interactive data collection through forms
- Pydantic models for validation
- Accept/decline/cancel workflows
- Pre-filled forms showing current values
- Confirmation dialogs for destructive actions

### Setup in VS Code

1. **Install the MCP server** (if not already done):
   ```bash
   pipx install -e .
   ```

2. **Configure VS Code**:
   
   Open your VS Code settings and add to `claude_desktop_config.json` or similar:
   
   ```json
   {
     "mcpServers": {
       "tasks": {
         "command": "tasks-mcp"
       }
     }
   }
   ```

3. **Restart VS Code** to load the MCP server

4. **Try it out** with Claude:
   - "Create a new task for me" → Interactive form appears
   - "Show me all my high priority tasks"
   - "Mark task #5 as complete"
   - "Update task #3" → Pre-filled form with current values

For detailed setup instructions, see [MCP-QUICKSTART.md](MCP-QUICKSTART.md).

### MCP Tools

#### Interactive Tools (User Elicitation)

These tools present interactive forms in VS Code:

- **`create_task_interactive`** - Full task creation form
  - Fields: title, description, priority, due_date
  - Actions: accept (create), decline, cancel

- **`update_task_interactive`** - Pre-filled update form
  - Shows current values for all fields
  - Empty fields keep current value
  - Actions: accept (update), decline, cancel

- **`delete_task_interactive`** - Confirmation dialog
  - Shows task details before deletion
  - Requires confirmation checkbox
  - Actions: accept+confirm (delete), decline, cancel

#### Standard Tools

Direct invocation tools without forms:

- **`create_task`** - Create task with parameters
- **`get_task`** - Get task by ID
- **`list_tasks`** - List tasks with filters
- **`update_task`** - Update task fields
- **`complete_task`** - Mark task complete
- **`delete_task`** - Delete task (⚠️ no confirmation)
- **`get_overdue`** - List overdue tasks

### MCP Resources

Access task statistics:

- **`tasks://stats`** - Current task statistics
  - Total tasks count
  - Status breakdown (pending, in_progress, completed, archived)
  - Priority breakdown (high, medium, low)
  - Overdue count

### MCP Prompts

Prompts are templates that appear as slash commands in AI clients (VS Code, Claude Desktop) to guide natural language interactions:

#### Available Prompts

- **`/newTask`** - Guide through creating a new task
  - Arguments: `task_type` (feature, bug, docs, chore, test)
  - Provides tailored templates and examples
  - Walks through title, description, priority, JIRA links, due date
  
- **`/updateTask`** - Guide through updating an existing task
  - Arguments: `task_id` (required)
  - Lists all updatable fields with examples
  - Shows current task details first
  
- **`/reviewTasks`** - Prompt for reviewing and prioritizing tasks
  - Arguments: `focus` (all, overdue, high-priority, in-progress)
  - Structured review process with actionable steps
  - Helps assess status, blockers, and next actions
  
- **`/planWork`** - Help break down work into manageable tasks
  - Arguments: `project` (name/description of work to plan)
  - Guides through objective, scope, breakdown, prioritization
  - Creates task list with dependencies and estimates
  
- **`/dailyStandup`** - Generate daily standup report
  - No arguments required
  - Formats: Yesterday, Today, Blockers, This Week
  - Based on task activity and status
  
- **`/taskReport`** - Generate comprehensive status report
  - Arguments: `period` (day, week, sprint, month)
  - Includes: completed, in-progress, blocked, planned, metrics
  - Professional reporting format

#### Using Prompts

In VS Code with Claude or other MCP-enabled AI clients:

```
You: /newTask bug
Claude: I'll help you create a new bug task. Let's gather the details:
        
        **1. Task Title** (brief and actionable)
           Example: fix: Resolve issue with X
           ...

You: I need to fix the login redirect on mobile Safari
Claude: [Creates task using the create_task tool with your input]
```

Prompts make it easier to use the task manager naturally - just type the slash command and follow the guided conversation!

## Configuration

The task manager uses a flexible configuration system with TOML files, environment variables, and CLI flags.

### Configuration File Locations

Configuration is loaded in priority order (highest first):

1. **CLI Flags**: `--config`, `--profile`, `--database` (highest priority)
2. **Environment Variables**: `TASKMANAGER_*` prefix
3. **Project Config**: `./taskmanager.toml` (relative to git root, team-shared)
4. **User Config**: `~/.config/taskmanager/config.toml` (XDG standard)
5. **Defaults**: Hardcoded sensible defaults (lowest priority)

### Configuration File Format

The configuration file uses TOML format with the following structure:

```toml
# ~/.config/taskmanager/config.toml

[general]
profile = "default"  # Active profile: default, dev, test

[database]
# Profile-specific database URLs with path tokens
[database.profiles]
default = "sqlite:///{config}/taskmanager/tasks.db"
dev = "sqlite:///{config}/taskmanager/tasks-dev.db"
test = "sqlite:///:memory:"

[defaults]
task_limit = 20          # Default number of tasks in list commands
max_task_limit = 100     # Maximum tasks per query

[logging]
level = "INFO"           # Log level: DEBUG, INFO, WARNING, ERROR
# file = "{config}/taskmanager/taskmanager.log"  # Uncomment to enable file logging

[mcp]
server_name = "tasks_mcp"
transport = "stdio"
```

### Profile System

Profiles allow easy switching between databases without manual URL changes.

**Available Profiles:**
- **`default`**: Production database at `~/.config/taskmanager/tasks.db`
- **`dev`**: Development database at `~/.config/taskmanager/tasks-dev.db`
- **`test`**: In-memory database for testing (`sqlite:///:memory:`)

**Usage:**

```bash
# Use dev profile
tasks --profile dev list

# Use test profile
tasks --profile test add "Test task"

# Override database directly
tasks --database "sqlite:///custom.db" list

# Use custom config file
tasks --config ./my-config.toml list
```

### Path Token Expansion

Configuration paths support tokens for portability:

- **`{config}`**: Expands to `~/.config/taskmanager`
- **`{home}`**: Expands to user home directory (`~`)
- **`{data}`**: Expands to `~/.local/share/taskmanager`

**Example:**
```toml
[database.profiles]
default = "sqlite:///{config}/tasks.db"  # → ~/.config/taskmanager/tasks.db
backup = "sqlite:///{home}/Dropbox/tasks.db"  # → ~/Dropbox/tasks.db
```

### Environment Variables

Override configuration with environment variables:

```bash
export TASKMANAGER_PROFILE=dev
export TASKMANAGER_DATABASE_URL="sqlite:///custom.db"
export TASKMANAGER_LOG_LEVEL=DEBUG

tasks list  # Uses environment config
```

### Configuration Commands

```bash
# Show current effective configuration
tasks config show

# Show config file location
tasks config path

# Open config file in $EDITOR
tasks config edit

# Validate config file syntax
tasks config validate

# Create/reset config file with defaults
tasks config init
tasks config init --force  # Overwrite existing
```

### Auto-Initialization

On first run, the task manager automatically creates:
- Configuration directory: `~/.config/taskmanager/`
- Default config file: `config.toml` with sensible defaults
- Database file (based on active profile)

### Project Configuration

For team-shared settings, create `taskmanager.toml` in your git repository root:

```toml
# ./taskmanager.toml (project config)

[general]
profile = "dev"  # Team uses dev profile by default

[database.profiles]
dev = "sqlite:///{home}/.taskmanager/project-dev.db"
```

**Benefits:**
- Team shares same configuration
- Git-tracked settings
- Per-project database locations
- Still overridable per-user

### MCP Server Configuration

The MCP server uses the same configuration system as the CLI:

```json
{
  "mcpServers": {
    "tasks": {
      "command": "tasks-mcp",
      "env": {
        "TASKMANAGER_PROFILE": "default"
      }
    }
  }
}
```

Set `TASKMANAGER_PROFILE=test` to point the MCP server at a test database.

## JIRA Integration

Link tasks to JIRA issues for seamless project tracking.

### Configuration

Set your JIRA base URL in `~/.config/taskmanager/config.toml`:

```toml
[jira]
jira_url = "https://jira.yourcompany.com"
```

### Usage

**Create task with JIRA issues:**
```bash
tasks add "Fix authentication bug" --jira "SRE-1234,DEVOPS-5678"
```

**Update task's JIRA issues:**
```bash
tasks update 1 --jira "SRE-1234,BACKEND-999"
```

**Clear JIRA issues:**
```bash
tasks update 1 --clear-jira
```

**View task with JIRA links:**
```bash
tasks show 1
```

Output:
```
Task #1
Title: Fix authentication bug
...
JIRA Issues:
  • SRE-1234 (https://jira.yourcompany.com/browse/SRE-1234)
  • DEVOPS-5678 (https://jira.yourcompany.com/browse/DEVOPS-5678)
```

### MCP Integration

The MCP server also supports JIRA issues:

```python
# Create task with JIRA issues
create_task(
    title="Bug fix",
    jira_issues="SRE-1234,DEVOPS-5678"
)

# Update task's JIRA issues
update_task(task_id=1, jira_issues="SRE-9999")
```

JIRA links are formatted as Markdown in responses:
```markdown
**JIRA Issues:**
- [SRE-1234](https://jira.yourcompany.com/browse/SRE-1234)
- [DEVOPS-5678](https://jira.yourcompany.com/browse/DEVOPS-5678)
```

## Database Migrations

The task manager uses **Alembic** for database schema migrations, preserving your data when adding new features.

### Running Migrations

**Upgrade to latest schema:**
```bash
# Default profile
alembic upgrade head

# Specific profile
TASKS_PROFILE=dev alembic upgrade head
TASKS_PROFILE=test alembic upgrade head
```

**Check current version:**
```bash
alembic current
TASKS_PROFILE=dev alembic current
```

**View migration history:**
```bash
alembic history
```

### Creating Migrations

When adding new features that modify the database:

```bash
# Create a new migration
alembic revision -m "add_new_feature"

# Auto-generate from model changes (experimental)
alembic revision --autogenerate -m "add_new_feature"
```

Then edit the generated file in `migrations/versions/` to implement the upgrade/downgrade logic.

### Migration Files

Migrations are stored in:
```
migrations/
├── versions/
│   └── e17cb2e34d2f_add_jira_issues_column.py
├── env.py       # Migration environment configuration
└── script.py.mako
```

### Profile-Aware Migrations

The migration system respects your configuration profiles:

- `alembic upgrade head` → default profile database
- `TASKS_PROFILE=dev alembic upgrade head` → dev profile database
- `tasks --profile test ...` → CLI uses test profile

### First Run

The first time you run a task command, the database is automatically created with the latest schema. No manual migration needed for new databases.

## Architecture

### Layered Design

```
┌─────────────────────────────────────────┐
│   Interface Layer                       │
│  ┌──────────────┐    ┌──────────────┐   │
│  │ CLI (Typer)  │    │ MCP Server   │   │
│  └──────────────┘    └──────────────┘   │
└─────────────────────────────────────────┘
           ↓                  ↓
┌─────────────────────────────────────────┐
│   Service Layer (Business Logic)        │
│  - TaskService                          │
└─────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────┐
│   Repository Layer (Data Access)        │
│  - TaskRepository (Protocol)            │
│  - SQLTaskRepository (Implementation)   │
└─────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────┐
│   Data Layer (SQLModel/SQLite)          │
│  - Task model                           │
└─────────────────────────────────────────┘
```

### Key Principles

- **Shared Business Logic**: CLI and MCP use the same service layer
- **Repository Pattern**: Abstract data access for flexibility
- **Dependency Injection**: Explicit dependencies for testability
- **Single Database**: Both interfaces access the same SQLite file

### Project Structure

```
taskmanager/
├── taskmanager/              # Core application
│   ├── cli.py                # Typer CLI interface
│   ├── models.py             # SQLModel data models
│   ├── repository.py         # Repository protocol
│   ├── repository_impl.py    # SQLite implementation
│   ├── service.py            # Business logic
│   ├── config.py             # Configuration
│   └── utils.py              # Utilities
├── mcp_server/               # MCP server
│   └── server.py             # FastMCP 3.0 server
├── tests/                    # Test suite (69 tests, 92% coverage)
└── pyproject.toml            # Dependencies
```

## Development

### Setup Development Environment

```bash
# Clone repository
git clone <repository-url>
cd taskmanager

# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

### Run Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=taskmanager --cov=mcp_server

# Specific test file
pytest tests/test_service.py
```

### Code Quality

```bash
# Linting
ruff check .

# Formatting
ruff format .

# Type checking
mypy taskmanager/ mcp_server/
```

### Database Location

- **Path**: `~/.taskmanager/tasks.db`
- **Type**: SQLite
- **Schema**: Managed by SQLModel

To reset the database:
```bash
rm ~/.taskmanager/tasks.db
```

The database will be recreated on next use.

## Technology Stack

### Core
- **Python 3.12/3.13** - Modern Python with type hints
- **SQLModel** - Type-safe ORM with Pydantic integration
- **SQLite** - Zero-config persistent storage
- **Typer** - CLI framework with excellent UX
- **Rich** - Beautiful terminal formatting

### MCP Server
- **FastMCP 3.0.0b1** - Latest MCP framework with User Elicitation
- **MCP SDK 1.23+** - Model Context Protocol implementation
- **Pydantic v2** - Data validation and forms

### Development
- **pytest** - Testing framework
- **ruff** - Fast linting and formatting
- **mypy** - Static type checking
- **pipx** - Isolated tool installation

## Roadmap

### Current Version: 1.0.0 (Phase 3 Complete)
- ✅ Core CRUD operations
- ✅ CLI with Rich formatting
- ✅ MCP server with FastMCP 3.0
- ✅ User Elicitation (interactive forms)
- ✅ Shared business logic
- ✅ 69 unit tests, 92% coverage

### Future Iterations
- **v1.1**: Projects and task hierarchy
- **v1.2**: Tags and advanced filtering
- **v1.3**: Full-text search
- **v1.4**: Recurring tasks
- **v1.5**: Time tracking
- **v1.6**: Reports and analytics

## Contributing

This is currently a personal project. If you'd like to contribute:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Ensure all quality checks pass
5. Submit a pull request

## License

[Your license here]

## Support

- **Documentation**: See [Tasks-project-launch.md](Tasks-project-launch.md) for architecture
- **MCP Setup**: See [MCP-QUICKSTART.md](MCP-QUICKSTART.md) for VS Code integration
- **FastMCP 3.0**: See [FASTMCP-3.0-RESEARCH.md](FASTMCP-3.0-RESEARCH.md) for implementation details

## Acknowledgments

- Built with [FastMCP](https://github.com/jlowin/fastmcp) by Marvin/Prefect team
- Uses [Model Context Protocol](https://modelcontextprotocol.io/) by Anthropic
- CLI powered by [Typer](https://typer.tiangolo.com/) and [Rich](https://rich.readthedocs.io/)
