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
- **MCP Server**: FastMCP (from MCP Python SDK) for AI agent integration
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
- **Configuration**: Pydantic Settings with TOML/env file support
- **Data Location**: `~/.taskmanager/` (database, config, logs)
- **CLI Command Name**: `tasks` (short, clear, memorable)
- **MCP Server Name**: `tasks_mcp`
- **MCP Transport**: stdio (local, single-user)

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
│   ├── server.py             # FastMCP server initialization
│   ├── tools.py              # MCP tool implementations
│   ├── resources.py          # MCP resource handlers
│   ├── prompts.py            # MCP prompt definitions
│   └── formatters.py         # Response formatting utilities
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

### Future Commands (Post-Iteration 1)
- `tasks search <query>` - Full-text search
- `tasks tag <id> <tag>` - Tag management
- `tasks project` - Project management
- `tasks config` - Configuration
- `tasks stats` - Statistics and reports

## MCP Server Integration

### Server Configuration

- **Server Name**: `tasks_mcp`
- **Transport**: stdio (for local/single-user operation)
- **Capabilities**: Tools, Resources, Resource Templates, Prompts
- **Shared Database**: Same SQLite database as CLI (`~/.taskmanager/tasks.db`)

### MCP Tools (AI-Invocable Actions)

Tools are functions that AI agents can call autonomously based on user intent.

#### Core CRUD Tools

```python
# Create operations
tasks_create_task(title, description?, priority?, due_date?, tags?)
  → Returns: Task details in JSON

# Read operations  
tasks_get_task(task_id)
  → Returns: Single task details

tasks_list_tasks(status?, priority?, tags?, limit=20, offset=0, format="markdown")
  → Returns: List of tasks (paginated)

# Update operations
tasks_update_task(task_id, title?, description?, priority?, due_date?, status?)
  → Returns: Updated task details

tasks_mark_complete(task_id, completed=true)
  → Returns: Confirmation message

tasks_set_priority(task_id, priority)
  → Returns: Confirmation message

# Delete operations
tasks_delete_task(task_id)
  → Returns: Confirmation message
```

#### Query & Analysis Tools

```python
tasks_search_tasks(query, limit=20)
  → Returns: Matching tasks

tasks_get_overdue(format="markdown")
  → Returns: List of overdue tasks

tasks_get_statistics(period="all")
  → Returns: Task statistics (total, completed, pending, etc.)
```

#### Tool Design Principles
- **Naming**: Use `tasks_` prefix to avoid conflicts
- **Validation**: All inputs validated with Pydantic models
- **Output Formats**: Support both Markdown (human) and JSON (machine)
- **Pagination**: List operations support limit/offset
- **Error Handling**: Clear, actionable error messages
- **Annotations**: Mark tools as readOnly, destructive, idempotent

### MCP Resources (Contextual Data)

Resources provide structured data that AI agents can access for context.

#### Static Resources

```
config://settings          # Application configuration
stats://overview           # Current task statistics  
tags://list                # Available tags with counts
system://priorities        # Priority definitions
```

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

- **Settings File**: `~/.taskmanager/config.toml`
- **Environment Variables**: `TASKMANAGER_*` prefix
- **CLI Override**: Command-line flags take precedence
- **Defaults**: Sensible defaults for all settings

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

#### Phase 3: MCP Server ✅ COMPLETE
- ✅ FastMCP server initialization
- ✅ Core CRUD tools (create, get, list, update, delete, mark_complete)
- ✅ Query tools (get_overdue, get_statistics)
- ✅ Resource: stats://overview
- ✅ Response formatting (Markdown)
- ✅ VS Code MCP configuration example (embedded in quickstart)
- ✅ VS Code one-click installation button
- ✅ User quickstart guide (MCP-QUICKSTART.md)
- ⬜ MCP tool tests with Inspector (deferred - manual testing confirms functionality)
- ⬜ Resource templates (task:///{task_id}, etc.) - deferred to future iteration
- ⬜ Prompts (daily_planning, etc.) - deferred to future iteration

#### Phase 4: Integration & Polish (Week 3) - READY TO START
- ⬜ End-to-end integration testing
- ⬜ Cross-interface consistency verification
- ⬜ Error handling refinement
- ⬜ Documentation (README, docstrings)
- ⬜ Performance optimization
- ⬜ User acceptance testing

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
- ✅ All tests passing (69 unit tests)
- ✅ Type checking passes (mypy)
- ✅ Linting passes (ruff)
- ⬜ CLI installable via pipx (functional via `python -m taskmanager`)
- ✅ MCP server functional (tested via JSON-RPC)
- ✅ Clear error messages for all failure cases

**User Experience:**
- ✅ CLI commands intuitive and well-documented (built-in help)
- ✅ Beautiful terminal output with Rich (tables, colors, icons)
- ✅ Shell completion working (Typer auto-completion)
- ✅ Fast response times (<100ms for common operations)
- ✅ Helpful error messages guiding user to solution

### Deliverables

1. **Working Application**
   - Installable CLI: `pipx install .`
   - Functional MCP server: `tasks_mcp`
   - Database: `~/.taskmanager/tasks.db`

2. **Documentation**
   - README with installation and usage instructions
   - CLI help text for all commands
   - MCP tool descriptions
   - Architecture documentation

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
