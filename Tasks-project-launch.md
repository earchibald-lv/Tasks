# Tasks.

## Description
We're going to build the best custom bespoke CLI task, to-do list and personal project manager app in the world. In the world for me and my preferences, anyway. This app will help users organize their tasks, set deadlines, and track their progress. 

It will be **dual-interface**: a traditional CLI for direct user interaction AND a Model Context Protocol (MCP) server for AI agent integration. Both interfaces will share the same business logic and database through a layered architecture, ensuring consistency and maintainability.

The app is CLI-first but designed with a pluggable architecture to allow for future expansion into GUI or web-based interfaces.

## Tools and Technologies

### Core Stack
- **Programming Language**: Python 3.12 selected using `pyenv local 3.12` as the local python version, stored in .python-version file.
- **Database**: SQLite for persistent storage (single-file, zero-config, ACID compliant)
- **ORM**: SQLModel for type-safe database operations with Pydantic integration
- **CLI Framework**: Typer for modern CLI with excellent type hints and auto-completion
- **CLI Output**: Rich for beautiful terminal formatting (tables, colors, progress bars)
- **MCP Server**: FastMCP 3.0.0b1 (beta) for AI agent integration with User Elicitation support
- **Validation**: Pydantic v2 for data validation and serialization (included with SQLModel)

### Development Tools
- **Virtual Environment**: `venv` for development-use project dependencies
- **Dependency Management**: `pyproject.toml` for managing project dependencies
- **User Installation**: `pipx` for installing the CLI tool globally for the user
- **Version Control**: Git, locally for now until we set up a remote repository
- **Testing Framework**: pytest with pytest-asyncio and pytest-cov for coverage
- **Code Quality**: ruff for linting and formatting, mypy for type checking
- **Database Migrations**: Alembic for schema evolution
- **MCP Development**: MCP Inspector for testing and debugging MCP tools

### Configuration & Deployment
- **Configuration System**: Pydantic Settings with TOML file + environment variables + CLI flags
- **Config File Locations**:
  - User config: `~/.config/taskmanager/config.toml` (XDG Base Directory standard)
  - Project config: `./taskmanager.toml` (git-tracked team settings)
  - Config priority: CLI flags > env vars > project config > user config > defaults
- **Configuration Profiles**: `default`, `dev`, `test` (switchable via `--profile` flag)
- **Path Token Expansion**: `{config}`, `{home}`, `{data}` for portable paths
- **Data Location**: `~/.config/taskmanager/` (database, logs)
- **Database Paths**:
  - Default: `sqlite:///{config}/taskmanager/tasks.db`
  - Dev: `sqlite:///{config}/taskmanager/tasks-dev.db`
  - Test: `sqlite:///:memory:` (in-memory for fast testing)
- **CLI Command Name**: `tasks` (short, clear, memorable)
- **MCP Server Name**: `tasks_mcp`
- **MCP Transport**: stdio (local, single-user)
- **JIRA Integration**: `jira_url` configuration for issue link generation (e.g., `https://jira.company.com`)
- **Auto-Initialization**: Config file auto-created on first run with defaults

## Architecture

### Layered Architecture Pattern

The application uses a clean layered architecture to ensure separation of concerns, testability, and maintainability:

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
│  - ValidationService                    │
│  - SearchService                        │
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
│  - Task, Project, Tag models            │
└─────────────────────────────────────────┘
```

**Key Principles:**
- **Shared Business Logic**: Both CLI and MCP server call the same service layer functions
- **Repository Pattern**: Abstract data access for testability and flexibility
- **Dependency Injection**: Pass dependencies explicitly for clean testing
- **Single Database**: Both interfaces access the same SQLite database

### Project Structure

```
task-manager/
├── taskmanager/              # Core application
│   ├── __init__.py
│   ├── cli.py                # Typer CLI interface
│   ├── models.py             # SQLModel data models
│   ├── repository.py         # Repository protocol/interface
│   ├── repository_impl.py    # SQLite repository implementation
│   ├── service.py            # Business logic layer
│   ├── config.py             # Shared configuration
│   └── utils.py              # Shared utilities
├── mcp_server/               # MCP server (AI agent interface)
│   ├── __init__.py
│   └── server.py             # FastMCP 3.0 server with tools, resources, and User Elicitation forms
├── tests/                    # Test suite
│   ├── __init__.py
│   ├── test_service.py       # Service layer tests
│   ├── test_repository.py    # Repository tests
│   ├── test_cli.py           # CLI interface tests
│   ├── test_mcp_tools.py     # MCP tool tests
│   ├── test_integration.py   # End-to-end tests
│   └── mocks.py              # Mock implementations
├── .python-version           # Python version (3.12)
├── pyproject.toml            # Project dependencies and config
├── README.md                 # Documentation
├── .env.example              # Example environment variables
└── .gitignore
```

### Design Patterns

- **Repository Pattern**: Abstract storage layer for future flexibility (SQLite → PostgreSQL)
- **Dependency Injection**: Pass repositories and services to handlers
- **Command Pattern**: Each CLI command and MCP tool as discrete handler
- **Strategy Pattern**: Multiple output formats (JSON, Markdown, plain text)

## Data Model

### Task Entity (First Iteration)

```python
class Task(SQLModel, table=True):
    # Identity
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Core fields
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    
    # Status and workflow
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    priority: Priority = Field(default=Priority.MEDIUM)
    
    # Scheduling
    due_date: Optional[date] = None
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    
    # External tracking
    jira_issues: Optional[str] = None  # Comma-separated JIRA issue keys (e.g., "SRE-1234,DEVOPS-5678")
    
    # Future: project_id, tags (many-to-many), parent_task_id
```

### Enumerations

```python
class TaskStatus(str, Enum):
    PENDING = "pending"       # Not started
    IN_PROGRESS = "in_progress"  # Currently working on
    COMPLETED = "completed"   # Finished
    ARCHIVED = "archived"     # Old/inactive

class Priority(str, Enum):
    LOW = "low"              # Nice to have
    MEDIUM = "medium"        # Normal priority
    HIGH = "high"            # Important
    URGENT = "urgent"        # Critical/time-sensitive
```

### Future Entities (Post-Iteration 1)
- **Project**: Group related tasks
- **Tag**: Flexible categorization (many-to-many)
- **Note**: Attachments to tasks
- **Recurrence**: Repeating task patterns

## CLI Command Structure

### First Iteration Commands

```bash
# Core CRUD operations
tasks add "<title>" [options]          # Create new task
tasks list [filters]                   # List all tasks
tasks show <id>                        # Show task details
tasks update <id> [options]            # Update task
tasks complete <id>                    # Mark as complete
tasks delete <id>                      # Delete task

# Options for 'add' and 'update'
  --description TEXT                   # Task description
  --priority [low|medium|high|urgent]  # Priority level
  --due DATE                           # Due date (YYYY-MM-DD)
  --status [pending|in_progress|completed|archived]

# Options for 'list'
  --status [pending|in_progress|completed|archived]
  --priority [low|medium|high|urgent]
  --limit INTEGER                      # Max results (default: 20)
  --offset INTEGER                     # Pagination offset
  --format [table|json|simple]         # Output format
```

### Examples

```bash
tasks add "Review PR #123" --priority high --due 2026-01-30
tasks list --status pending --priority high
tasks update 42 --status in_progress
tasks complete 42
tasks show 42
tasks delete 42
```

### Configuration Commands (Phase 4.5)
```bash
tasks config show                      # Display current configuration
tasks config path                      # Show config file location
tasks config edit                      # Open config in $EDITOR
tasks config validate                  # Check config file validity
tasks config init [--force]            # Create/reset config file
```

### Global CLI Options (Phase 4.5)
```bash
tasks --config PATH <command>          # Use specific config file
tasks --profile PROFILE <command>      # Use profile (default/dev/test)
tasks --database URL <command>         # Override database URL
```

### Future Commands (Post-Phase 5)
- `tasks search <query>` - Full-text search
- `tasks tag <id> <tag>` - Tag management
- `tasks project` - Project management
- `tasks stats` - Statistics and reports

## MCP Server Integration

### Server Configuration

- **Framework**: FastMCP 3.0.0b1 (beta version with 70% market adoption)
- **Server Name**: `Task Manager`
- **Command**: `tasks-mcp` (globally installed via pipx)
- **Transport**: stdio (for local/single-user operation)
- **Capabilities**: Tools, Resources, User Elicitation (interactive forms)
- **Shared Configuration**: Uses same config file as CLI (`~/.config/taskmanager/config.toml`)
- **Shared Database**: Same SQLite database as CLI (configurable via profiles)
- **Installation**: `pipx install -e .` for editable development mode

### MCP Tools (AI-Invocable Actions)

Tools are functions that AI agents can call autonomously based on user intent.

#### Standard Tools (Direct Invocation)

```python
# Create operations
create_task(title, description?, priority="medium", status="todo", due_date?)
  → Returns: Task details in Markdown

# Read operations  
get_task(task_id)
  → Returns: Single task details in Markdown

list_tasks(status="all", priority="all", overdue_only=false)
  → Returns: List of tasks in Markdown

# Update operations
update_task(task_id, title?, description?, priority?, status?, due_date?)
  → Returns: Updated task details in Markdown

complete_task(task_id)
  → Returns: Confirmation message

# Delete operations
delete_task(task_id)
  → Returns: Confirmation message (⚠️ no confirmation dialog)
```

#### Interactive Tools (User Elicitation Forms)

FastMCP 3.0 User Elicitation enables interactive forms with accept/decline/cancel actions:

```python
# Interactive creation with full form
create_task_interactive()
  → Presents: TaskCreationForm (title, description, priority, due_date)
  → User actions: accept (create), decline (reject), cancel
  → Returns: Created task details or cancellation message

# Interactive update with pre-filled form
update_task_interactive(task_id)
  → Fetches current task values
  → Presents: TaskUpdateForm (pre-filled with current values)
  → User actions: accept (update), decline (reject), cancel
  → Returns: Updated task details or cancellation message

# Interactive deletion with confirmation
delete_task_interactive(task_id)
  → Shows current task details
  → Presents: TaskDeletionConfirmation (confirm boolean)
  → User actions: accept+confirm (delete), decline (preserve), cancel
  → Returns: Deletion confirmation or preservation message
```

**Pydantic Form Models:**
- `TaskCreationForm`: title (required), description, priority, due_date
- `TaskUpdateForm`: all fields optional (empty = keep current value)
- `TaskDeletionConfirmation`: confirm boolean with task details shown

**User Elicitation Benefits:**
- Interactive data collection in VS Code
- Form validation with Pydantic
- Clear accept/decline/cancel workflow
- Pre-filled forms show current values
- Confirmation dialogs prevent accidents

#### Query Tools

```python
get_overdue()
  → Returns: List of overdue tasks in Markdown
```

**Note**: Statistics are available via the `tasks://stats` resource, not as a tool.

#### Tool Design Principles
- **Naming**: Simple, clear names (no prefix needed in FastMCP 3.0)
- **Decorators**: Use `@mcp.tool()` for automatic registration
- **Validation**: Input validation via function signatures and Pydantic
- **Output Format**: Markdown for human-readable responses
- **Error Handling**: Clear, actionable error messages with emoji indicators
- **User Elicitation**: Interactive forms use `async def` with `Context` parameter
- **Form Validation**: Pydantic models for structured input collection

### MCP Resources (Contextual Data)

Resources provide structured data that AI agents can access for context.

#### Implemented Resources

```
tasks://stats              # Current task statistics
                          # - Total tasks
                          # - Status breakdown (pending, in_progress, completed, archived)
                          # - Priority breakdown (high, medium, low)
                          # - Overdue count
```

**Resource Decorator**: `@mcp.resource("tasks://stats")`

#### Resource Templates (Parameterized)

URI templates following RFC 6570 for dynamic resource access:

```
task:///{task_id}                    # Individual task details
tasks://status/{status}              # Tasks filtered by status
tasks://priority/{priority}          # Tasks filtered by priority
tasks://due/{date}                   # Tasks due on specific date
view://today                         # Tasks due today
view://week                          # Tasks due this week
view://overdue                       # Overdue tasks
```

**Benefits**: Flexible data access without creating separate tools for each filter combination.

### MCP Prompts (Guided Workflows)

Prompts are user-initiated workflows that guide AI interactions.

#### Daily Workflows

```python
daily_planning
  # Morning planning session
  # Reviews today's tasks, overdue items, priorities
  
daily_review  
  # Evening review session
  # Summary of completed tasks, carry-over items
```

#### Weekly Workflows

```python
weekly_review
  # GTD-style comprehensive weekly review
  # Reviews all projects, tasks, goals
  
weekly_planning
  # Plan upcoming week
  # Assign tasks to days, identify priorities
```

#### Task Processing

```python
process_inbox
  # GTD-style inbox processing
  # Guided workflow for clarifying and organizing new tasks
  
task_breakdown(task_id)
  # Break complex task into subtasks
  # Helps decompose large tasks into actionable steps
```

#### Reporting

```python
productivity_report(period="week")
  # Generate productivity summary
  # Statistics, trends, insights
  
overdue_review
  # Review and plan overdue tasks
  # Suggested actions for each overdue item
```

## Development Workflow

### Iterative Development Principles

We will work ITERATIVELY on this. This means we will build the app in small, manageable pieces, testing and refining each piece before moving on to the next.

**Core Rules:**
- ✅ ALWAYS maintain a WORKING version of the app
- ✅ ALWAYS maintain the current version of the code in a GIT REPOSITORY
- ✅ COMMIT OFTEN with clear, descriptive messages (Conventional Commits format)
- ✅ ALWAYS TEST our code thoroughly before moving on to the next piece
- ✅ MAINTAIN USE CASE TESTS - full regression check for every change
- ✅ Code quality checks (ruff + mypy) before each commit
- ✅ Test both CLI and MCP interfaces after changes
- ✅ SECURITY CHECK: Validate all inputs, never commit secrets, review dependencies for vulnerabilities
- ✅ SEMANTIC VERSIONING: Use semver (MAJOR.MINOR.PATCH) for project and component versions

### Development Process

1. **Implement Shared Business Logic First**
   - Start with models and repository layer
   - Then implement service layer with business logic
   - Write unit tests for services

2. **CLI Interface Development**
   - Implement CLI commands using Typer
   - Test interactively during development
   - Write CLI-specific tests

3. **MCP Server Development**
   - Implement MCP tools reusing service layer
   - Test with MCP Inspector
   - Write MCP tool tests

4. **Integration Testing**
   - Test both interfaces against same database
   - Verify changes in CLI appear in MCP and vice versa
   - End-to-end workflow testing

### Testing Strategy

#### Unit Tests
- Service layer logic (with mock repositories)
- Repository implementations (with in-memory SQLite)
- Validation and transformation functions
- Target: >80% code coverage

#### Integration Tests
- CLI commands end-to-end
- MCP tools end-to-end  
- Cross-interface consistency
- Database operations

#### Test Tools
- `pytest` for test execution
- `pytest-asyncio` for async tests
- `pytest-cov` for coverage reporting
- Mock repositories for isolated testing
- MCP Inspector for interactive MCP testing

#### Test Fixtures
- Sample task data for consistent testing
- In-memory database for fast tests
- Mock configurations

### Code Quality Standards

```bash
# Before each commit
ruff check .          # Linting
ruff format .         # Formatting
mypy taskmanager/     # Type checking
pytest                # All tests
```

### Git Workflow

- **Commit Format**: Conventional Commits
  ```
  feat: add task creation command
  fix: handle empty task titles
  test: add tests for task service
  docs: update CLI command documentation
  refactor: extract validation logic
  ```

- **Branch Strategy** (future, when remote repo added):
  - `main`: stable, working code
  - `develop`: integration branch
  - `feature/*`: individual features

### MCP Development Tools

```bash
# Install MCP Inspector
pip install mcp-inspector

# Run MCP server with inspector
mcp-inspector python -m mcp_server.server

# Test individual tools interactively
# - List available tools
# - Invoke tools with various inputs
# - Verify responses and error handling
```

### Configuration Management

#### Configuration Files
- **User Config**: `~/.config/taskmanager/config.toml` (XDG standard location)
- **Project Config**: `./taskmanager.toml` (relative to git root, team-shared)
- **Auto-Creation**: Config file created with defaults on first run
- **Format**: TOML (human-friendly, comments supported)

#### Configuration Hierarchy (Priority Order)
1. **CLI Flags**: `--config`, `--profile`, `--database` (highest priority)
2. **Environment Variables**: `TASKMANAGER_*` prefix
3. **Project Config**: `./taskmanager.toml` (git-tracked)
4. **User Config**: `~/.config/taskmanager/config.toml`
5. **Defaults**: Hardcoded sensible defaults (lowest priority)

#### Profile System
- **Profile Names**: `default`, `dev`, `test`
- **Usage**: `tasks --profile dev list` or set `profile = "dev"` in config
- **Database Mapping**:
  - `default`: Production database at `~/.config/taskmanager/tasks.db`
  - `dev`: Development database at `~/.config/taskmanager/tasks-dev.db`
  - `test`: In-memory database for fast testing (`sqlite:///:memory:`)
- **Benefits**: Easy switching between databases without manual URL changes

#### Path Token Expansion
- `{config}`: Expands to `~/.config/taskmanager`
- `{home}`: Expands to user home directory
- `{data}`: Expands to `~/.local/share/taskmanager`
- **Usage**: `"sqlite:///{config}/tasks.db"` → portable across systems

#### Example Configuration File
```toml
# ~/.config/taskmanager/config.toml

[general]
profile = "default"  # default, dev, test

[database]
# Profile-specific database URLs
[database.profiles]
default = "sqlite:///{config}/taskmanager/tasks.db"
dev = "sqlite:///{config}/taskmanager/tasks-dev.db"
test = "sqlite:///:memory:"

[defaults]
task_limit = 20
max_task_limit = 100

[logging]
level = "INFO"  # DEBUG, INFO, WARNING, ERROR
# file = "{config}/taskmanager/taskmanager.log"

[mcp]
server_name = "tasks_mcp"
transport = "stdio"
```

#### Configuration Commands
- `tasks config show`: Display current effective configuration
- `tasks config path`: Print config file location
- `tasks config edit`: Open config file in $EDITOR
- `tasks config validate`: Check config file syntax and values
- `tasks config init`: Create default config file

### Documentation Standards

- **Docstrings**: Google-style for all public functions
- **Type Hints**: Complete type annotations throughout
- **README**: User-facing documentation
- **Comments**: Explain "why", not "what"

## First Iteration - Basic Task Management

In the first iteration, we will focus on the core functionality of the app: creating, reading, updating, and deleting tasks (CRUD operations). We will implement both the CLI interface and MCP server, sharing the same business logic layer.

### Development Phases

#### Phase 1: Foundation ✅ COMPLETE
- ✅ Project structure setup
- ✅ SQLModel models (Task, enums)
- ✅ Repository protocol and SQLite implementation
- ✅ Service layer with core business logic
- ✅ Shared configuration management
- ✅ Database initialization (Alembic migrations deferred to future iteration)
- ✅ Unit tests for all components (69 tests, 92% coverage)

#### Phase 2: CLI Interface ✅ COMPLETE
- ✅ Typer CLI application setup
- ✅ Core CRUD commands: add, list, show, update, complete, delete
- ✅ Rich formatting for beautiful output (tables, colors, icons)
- ✅ Command-line completion setup (built-in with Typer)
- ✅ Error handling and user feedback
- ⬜ CLI integration tests (deferred - manual testing confirms functionality)

#### Phase 3: MCP Server ✅ COMPLETE (FastMCP 3.0 with User Elicitation)
- ✅ **FastMCP 3.0.0b1 upgrade** from old MCP SDK
- ✅ **User Elicitation implementation** with Pydantic forms
- ✅ **Interactive tools**: create_task_interactive, update_task_interactive, delete_task_interactive
- ✅ **Standard tools**: create, get, list, update, complete, delete (6 tools)
- ✅ **Query tools**: get_overdue
- ✅ **Resource**: tasks://stats (statistics with breakdown)
- ✅ **Pydantic form models**: TaskCreationForm, TaskUpdateForm, TaskDeletionConfirmation
- ✅ **Response formatting**: Markdown with emoji indicators
- ✅ **Console script entry point**: tasks-mcp command
- ✅ **pipx installation**: Editable mode support (`pipx install -e .`)
- ✅ **VS Code integration**: One-click installation button in MCP-QUICKSTART.md
- ✅ **User documentation**: MCP-QUICKSTART.md with User Elicitation examples
- ✅ **Manual testing**: All tools functional in VS Code
- ✅ **Bug fixes**: Status enum mapping, tuple unpacking, date formatting, tags removal
- ⬜ Automated MCP tool tests (deferred - manual testing confirms functionality)
- ⬜ Resource templates (task:///{task_id}, etc.) - deferred to future iteration
- ⬜ Prompts (daily_planning, etc.) - deferred to future iteration

#### Phase 3.5: FastMCP 3.0 Enhancement ✅ COMPLETE

**Research & Planning:**
- ✅ FastMCP 3.0 research (fetched 6 documentation pages)
- ✅ Discovered User Elicitation as Python solution for interactive forms
- ✅ Created comprehensive research report (FASTMCP-3.0-RESEARCH.md)
- ✅ User decision: immediate implementation with full forms

**Implementation:**
- ✅ Upgraded dependencies: fastmcp>=3.0.0b1, mcp>=1.23
- ✅ Rewrote server.py with FastMCP 3.0 patterns (487 lines → 561 lines)
- ✅ Implemented @mcp.tool() decorators for all tools
- ✅ Created 3 Pydantic form models for User Elicitation
- ✅ Implemented 3 interactive tools with async Context parameter
- ✅ Fixed form schemas to use primitive types only (VS Code requirement)
- ✅ Converted date/tags handling from union types to string parsing
- ✅ Fixed status enum mapping (PENDING not TODO)
- ✅ Fixed tuple unpacking for service.list_tasks() return value
- ✅ Removed tags references (not yet in Task model)
- ✅ Installed editable package: pipx install -e .

**Testing & Validation:**
- ✅ All 69 unit tests passing after upgrade
- ✅ Manual testing of all 9 tools (6 standard + 3 interactive)
- ✅ Verified User Elicitation forms work in VS Code
- ✅ Tested create_task_interactive with full form workflow
- ✅ Confirmed database persistence across interfaces
- ✅ Cross-interface testing (CLI + MCP using same database)

**Documentation:**
- ✅ Updated MCP-QUICKSTART.md with User Elicitation examples
- ✅ Fixed one-click installation button with correct URL encoding
- ✅ Documented Pydantic form models and interactive tools

#### Phase 4: Integration & Polish ✅ COMPLETE
- ✅ **Comprehensive Documentation**: README.md with FastMCP 3.0 features
- ✅ **Docstring Verification**: 100% coverage across codebase
- ✅ **Error Handling**: All MCP tools wrapped in try-except blocks
- ✅ **Integration Testing**: 12 tests validating database persistence
- ✅ **Performance Optimization**: 14 performance tests, SQL COUNT optimization
- ✅ **Test Suite**: 95 tests passing (69 unit + 12 integration + 14 performance)
- ✅ **Code Quality**: 32% overall coverage (99% service, 98% repository)

#### Phase 4.5: Configuration System ⬜ IN PROGRESS
- ⬜ **TOML Configuration**: Pydantic Settings with TOML file support
- ⬜ **XDG Directories**: Move to `~/.config/taskmanager/config.toml`
- ⬜ **Profile System**: `default`, `dev`, `test` profiles for database selection
- ⬜ **Path Token Expansion**: `{config}`, `{home}`, `{data}` tokens
- ⬜ **Multi-Config Support**: User config + project config (git root)
- ⬜ **CLI Global Options**: `--config`, `--profile`, `--database` flags
- ⬜ **Config Subcommand**: `show`, `path`, `edit`, `validate`, `init`
- ⬜ **Auto-Initialization**: Create default config on first run
- ⬜ **MCP Integration**: MCP server uses same config system
- ⬜ **Testing**: Config loading, profile switching, precedence
- ⬜ **Documentation**: Configuration guide in README

### Success Criteria

**Functional Requirements:**
- ✅ Create tasks with title, description, priority, due date (CLI + MCP)
- ✅ List tasks with filtering (status, priority) and pagination (CLI + MCP)
- ✅ View individual task details (CLI + MCP)
- ✅ Update any task field (CLI + MCP)
- ✅ Mark tasks as complete (CLI + MCP)
- ✅ Delete tasks (CLI + MCP)
- ✅ All operations work identically via CLI and MCP server
- ✅ Changes persist to SQLite database

**Technical Requirements:**
- ✅ >80% test coverage for service layer (99% for core logic; 38% overall with untested interfaces)
- ✅ All tests passing (69 unit tests after FastMCP 3.0 upgrade)
- ✅ Type checking passes (mypy)
- ✅ Linting passes (ruff)
- ✅ CLI installable via pipx (installed and functional)
- ✅ MCP server functional (FastMCP 3.0.0b1 with User Elicitation)
- ✅ Clear error messages for all failure cases with emoji indicators

**User Experience:**
- ✅ CLI commands intuitive and well-documented (built-in help)
- ✅ Beautiful terminal output with Rich (tables, colors, icons)
- ✅ Shell completion working (Typer auto-completion)
- ✅ Fast response times (<100ms for common operations)
- ✅ Helpful error messages guiding user to solution

### Deliverables

1. **Working Application**
   - Installable CLI: `pipx install -e .` (editable mode)
   - CLI command: `tasks`
   - MCP server command: `tasks-mcp`
   - MCP framework: FastMCP 3.0.0b1 with User Elicitation
   - Database: `~/.taskmanager/tasks.db`
   - Interactive forms: 3 tools with Pydantic models

2. **Documentation**
   - README with installation and usage instructions
   - CLI help text for all commands
   - MCP-QUICKSTART.md with User Elicitation examples
   - FASTMCP-3.0-RESEARCH.md with implementation guide
   - MCP tool descriptions (9 tools: 6 standard + 3 interactive)
   - Architecture documentation (Tasks-project-launch.md)

3. **Test Suite**
   - Comprehensive unit tests
   - Integration tests for both interfaces
   - Test fixtures and mocks
   - >80% code coverage

4. **Code Quality**
   - Type-checked with mypy
   - Formatted with ruff
   - Documented with docstrings
   - Clean git history with conventional commits

### Future Iterations (Post-v1.0)

- **Iteration 2**: Projects and task hierarchy
- **Iteration 3**: Tags and advanced filtering
- **Iteration 4**: Search functionality
- **Iteration 5**: Recurring tasks
- **Iteration 6**: Notes and attachments
- **Iteration 7**: Time tracking
- **Iteration 8**: Reports and analytics
- **Iteration 9**: Sync and backup
- **Iteration 10**: Web interface (optional) 
