# Tasks Project - Comprehensive Overview

**Last Updated**: February 6, 2026  
**Current Version**: 0.10.0  
**Project Status**: Production-ready with active development

---

## Executive Summary

The **Tasks** project is an AI-friendly task management system designed to enable multi-agent collaboration through structured workflows. It provides a unified task database with support for multiple profiles, complex attachment handling, and integration with external systems (JIRA, Confluence, MCP servers).

The project serves dual purposes:
1. **User-facing**: A CLI and MCP-based task manager for personal/team productivity
2. **Agent-facing**: Infrastructure for AI agents to coordinate work through standardized task statuses and workflows

---

## Project Architecture

### Core Components

#### 1. **Task Management Engine** (`taskmanager/`)
The business logic layer that handles all task operations:
- **Models**: SQLModel-based data definitions with support for 9 task statuses
- **Repository Pattern**: Abstraction layer for database operations
- **Service Layer**: High-level business logic and validation
- **Database Layer**: SQLite with Alembic migrations, multi-profile support

#### 2. **Interface Layers**

**CLI Interface** (`taskmanager/cli.py`):
- Full-featured command-line interface using Typer/Click
- Interactive forms for complex operations
- Profile support for context switching
- Commands: add, list, show, update, delete, search, backup, etc.

**MCP Server** (`mcp_server/server.py`):
- FastMCP 3.0 implementation exposing task operations as tools
- Enables AI agents and LLMs to interact with tasks programmatically
- Supports all task operations through JSON-RPC interface
- Status-aware operations with emoji indicators for agent communication

#### 3. **Attachment System** (`taskmanager/attachments.py`)
- Dual-filename indexing (original + storage filename)
- Priority-based matching for retrieval
- File content storage and retrieval
- Database-backed metadata tracking
- Workspace-based file organization

#### 4. **Workspace Management** (`taskmanager/workspace.py`)
- Per-task isolated working directories
- Automatic creation and cleanup
- Metadata persistence (creation time, git status, etc.)
- Git repository initialization support

#### 5. **Configuration System** (`taskmanager/config.py`)
- Profile-based database isolation
- 1Password secrets resolution
- Environment variable expansion
- TOML-based configuration
- Atlassian (JIRA/Confluence) integration settings
- Per-profile database URL customization

#### 6. **MCP Discovery** (`taskmanager/mcp_discovery.py`)
- Dynamic MCP server discovery and configuration
- Tasks-MCP and Atlassian-MCP integration
- Claude session ephemeral directory management
- Environment variable injection for agent sessions

---

## Current Features

### Task Management
- **9 Task Statuses**: PENDING, IN_PROGRESS, COMPLETED, CANCELLED, ARCHIVED, ASSIGNED, STUCK, REVIEW, INTEGRATE
- **Priority Levels**: LOW, MEDIUM, HIGH, URGENT
- **Filtering**: By status, priority, due date, tags, search queries
- **Pagination**: Configurable limit/offset for large datasets
- **Sorting**: Most recent first by default
- **JIRA Integration**: Link tasks to JIRA issues with automatic URL generation

### Attachment System
- Store files associated with tasks
- Dual-filename indexing for flexible retrieval
- Priority-based matching (original filename → storage filename → substrings)
- Metadata tracking (creation time, size, original filename)
- Attachment listing with filtering

### Multi-Profile Database Support
- Default profile: User's primary task database
- Dev profile: Development/testing isolated environment
- Test profile: In-memory database for automated tests
- Custom profiles: User-defined with custom database paths
- Automatic database initialization and schema migrations

### Backup & Recovery
- Point-in-time backup creation before schema migrations
- Automatic backup rotation (keep latest 10)
- User-initiated backup/restore operations
- Timestamp-based backup naming

### Statistics & Insights
- Task count by status
- Overdue task detection
- Completion rates
- Priority distribution
- Tag aggregation

---

## Agent Communication Framework

### Multi-Agent Workflow Support
The project implements a sophisticated task status signaling system for coordinating work between multiple AI agents:

**Status Hierarchy**:
- **PENDING/IN_PROGRESS/COMPLETED**: Standard workflow states
- **ASSIGNED**: Main agent delegates work to delegate agent
- **STUCK**: Delegate agent signals blocker requiring main agent intervention
- **REVIEW**: Delegate agent signals work complete, ready for main agent review
- **INTEGRATE**: Main agent approves work for integration to production
- **CANCELLED/ARCHIVED**: Terminal states

### Governance Boundaries
- **Main Agent**: Controls merges to main branch, version bumps, production deployments
- **Delegate Agents**: Develop features in isolated worktrees, cannot merge code without approval
- **Signal Restrictions**: Agents can only mark appropriate statuses for their role

### MCP + CLI Resilience
The system implements dual-path operation patterns:
- **Primary Path**: MCP tools (FastMCP server calls)
- **Fallback Path**: CLI commands (for situations where MCP unavailable)
- Critical operations guaranteed to work regardless of MCP server availability

---

## Development Workflow

### Worktree-Based Development
All feature work uses isolated git worktrees to prevent conflicts:

1. Create task in dev profile (isolated task database)
2. Attach detailed prompt instructions via MCP tool
3. Create feature worktree outside main workspace (sibling directory)
4. Launch isolated VS Code window in worktree
5. Agent retrieves prompt, implements feature
6. Run quality checks locally (lint, type checking, tests)
7. Mark task as "review" when ready
8. Human reviews and merges to main
9. Remove worktree after successful merge

### Quality Gates (Mandatory Before Merge)
- **Linting**: Ruff checks (PEP 8 compliance)
- **Type Checking**: Mypy validation (full coverage)
- **Security Scanning**: Bandit and Safety checks
- **Testing**: Pytest suite with >80% coverage target

### Version Management
- **MAJOR**: Breaking API changes
- **MINOR**: New backward-compatible features
- **PATCH**: Bug fixes

---

## Data Model

### Task Entity
- **Core Fields**: title, description, priority, status
- **Relationships**: JIRA issue links, attachments, tags
- **Timestamps**: created_at, updated_at
- **Workspace**: Isolated working directory per task
- **Metadata**: Serialized tags and JIRA links

### Attachment Entity
- **Dual Filenames**: original_filename (user-provided), storage_filename (timestamped)
- **Metadata**: task_id, size_bytes, created_at
- **File Storage**: Workspace-based file system storage
- **Database Tracking**: Full attachment history per task

### Workspace Metadata
- **Directory Path**: ~/.taskmanager/workspaces/{task_id}/
- **Subdirectories**: notes/, code/, logs/, tmp/
- **Git Status**: Optional initialization and status tracking
- **Creation Time**: Timestamp for workspace age tracking

---

## Integration Points

### External Systems

**JIRA Integration**:
- Link tasks to JIRA issues by key
- Automatic URL generation for browse access
- Atlassian-MCP server for advanced operations
- Authentication via 1Password or environment variables

**Confluence Integration**:
- Documentation and knowledge base interaction
- Page management and search via MCP
- Integration with task attachments and notes

**MCP Servers**:
- Tasks-MCP: Native task management tool suite
- Atlassian-MCP: JIRA/Confluence operations
- Claude integration for AI agent coordination

### Database Connections
- SQLite with multi-profile isolation
- Alembic migrations for schema evolution
- Transaction support for data consistency
- Query optimization with indexes

---

## Recent Work & Status (v0.10.0)

### Latest Release (February 5, 2026)
**Feature**: Agent Communication Status System (#11)

**What Was Added**:
- Four new task statuses (ASSIGNED, STUCK, REVIEW, INTEGRATE) for multi-agent workflows
- Updated MCP server with status mappings and emoji indicators
- MCP + CLI resilience pattern for worktree operations
- Comprehensive governance documentation in copilot-instructions.md
- Bootstrap script simplification for reliability

**Quality Updates**:
- Fixed linting issues (unused imports, whitespace)
- Resolved type checking errors (type hints, union handling)
- Added missing imports for optional dependencies
- Committed quality fixes with proper messaging

**Integration Status**: ✅ Fully integrated to main with quality gates passed

### Prior Releases

**v0.9.0**: Point-in-time database backups with automatic rotation

**v0.8.4**: Governance updates for prompt attachments and dev profile usage

**v0.8.0+**: Custom profile support, attachment filename indexing, MCP resilience

---

## Testing & Quality Assurance

### Test Coverage
- **Unit Tests**: Individual function and class behavior
- **Integration Tests**: Multi-service interactions and workflow validation
- **Performance Tests**: Task operations complete within benchmarks
- **MCP Server Tests**: Tool invocation and status conversion

### Quality Tools
- **Ruff**: Linting and code formatting (PEP 8)
- **Mypy**: Type checking with strict validation
- **Bandit**: Security vulnerability scanning
- **Safety**: Dependency vulnerability checking
- **Pre-commit Hooks**: Automated quality checks on commit

### Known Issues (Non-Critical)
- Test file whitespace warnings (test files out-of-scope for quality gates)
- Some test imports require CLI refactoring (separate task)
- Configuration attribute edge cases in older Python versions

---

## Dependencies & Stack

### Core Dependencies
- **SQLModel**: ORM and data validation (SQL + Pydantic)
- **FastMCP**: MCP server framework (v3.0 compatible)
- **Typer**: CLI framework with interactive forms
- **Alembic**: Database migration management
- **Click**: Advanced CLI utilities
- **Pydantic**: Data validation and serialization

### Optional Dependencies
- **1Password CLI**: Secrets management
- **TOML Libraries**: Configuration parsing (tomli/tomllib)
- **Atlassian SDK**: JIRA/Confluence integration
- **uvx**: MCP server isolation

### Python Version Support
- Primary: Python 3.12+
- Compatible: Python 3.11 (with conditional imports)
- Tools: pip, pipx, pytest, ruff, mypy

---

## File Organization

```
Tasks/
├── taskmanager/              # Core package
│   ├── models.py            # SQLModel definitions
│   ├── repository.py        # Interface definitions
│   ├── repository_impl.py   # SQLAlchemy implementation
│   ├── service.py           # Business logic
│   ├── cli.py               # CLI interface
│   ├── database.py          # Database initialization
│   ├── config.py            # Configuration management
│   ├── attachments.py       # File attachment system
│   ├── workspace.py         # Task workspace management
│   └── mcp_discovery.py     # MCP server discovery
├── mcp_server/              # MCP server implementation
│   └── server.py            # FastMCP 3.0 server
├── tests/                   # Test suite
├── migrations/              # Alembic schema migrations
├── .github/                 # GitHub configuration
│   └── copilot-instructions.md  # AI development governance
├── pyproject.toml           # Package metadata & config
├── CHANGELOG.md             # Release history
├── README.md                # User documentation
└── PROJECT_OVERVIEW.md      # This file
```

---

## Governance & Approval Workflows

### Human Review Required
- Destructive database operations (production migrations)
- File deletions in main workspace
- Git force pushes
- Dependency removals
- Production deployments
- Code merges to main branch
- Version bumps and releases

### Auto-Approved Operations
- Feature development in worktrees
- Quality checks and testing
- Documentation updates
- Development task management

### Delegate Agent Restrictions
- **Cannot merge code to main**: Only humans can authorize
- **Cannot bump versions**: Version management is human-only
- **Cannot mark task as integrate/done**: Final approval is human-only
- **Can signal status**: Mark task as "stuck" or "review" to request intervention

---

## Configuration & Environment

### Profile System
**Built-in Profiles**:
- `default`: Production database at `~/.config/taskmanager/tasks.db`
- `dev`: Development database at `~/.config/taskmanager/tasks-dev.db`
- `test`: In-memory ephemeral database

**Custom Profiles**:
- User-defined via `~/.config/taskmanager/settings.toml`
- Database path customization
- Project-specific isolation

### Environment Variables
- `TASKMANAGER_PROFILE`: Override default profile
- `JIRA_URL`, `JIRA_USERNAME`, `JIRA_PASSWORD`: JIRA integration
- `CONFLUENCE_URL`, `CONFLUENCE_TOKEN`: Confluence integration
- `CLAUDE_CONFIG_DIR`: Claude session configuration
- `OP_SERVICE_ACCOUNT_TOKEN`: 1Password authentication

### Configuration Files
- `~/.config/taskmanager/settings.toml`: User configuration
- `.github/copilot-instructions.md`: AI development governance
- `AGENT_GUIDANCE.md`: Agent-specific workflow guidance
- `.mcp.json`: MCP server configurations (project-level)

---

## Next Development Priorities

### High Priority
1. **Shared Library Rearchitecture**: Enable code reuse across MCP servers (unblocks modular development)
2. **Fix Enum Type Issues**: Resolve type safety issues in current implementation
3. **Test File Cleanup**: Address import errors and whitespace issues in test suite

### Medium Priority
1. **Background Agent Workflow**: Autonomous feature development when Copilot CLI approved
2. **Performance Optimization**: Database indexing and query optimization
3. **Advanced Search**: Full-text search and complex query support

### Lower Priority
1. **Mobile Support**: Web-based interface for mobile devices
2. **Notifications**: Real-time status updates and alerts
3. **Analytics Dashboard**: Project metrics and burndown charts

---

## How Agents Use This Project

### Bootstrap Sequence
When a delegate agent receives a new feature worktree:
1. Detect task ID from directory name: `Tasks-{id}`
2. Retrieve detailed prompt via MCP tool
3. Read instructions and acceptance criteria
4. Implement feature in isolated environment
5. Run quality checks (lint, type checking, tests)
6. Mark task as "review" when complete
7. Wait for human approval and merge

### Prompt Attachment Pattern
Prompts are stored in the task database (not repository):
- Main agent creates detailed prompt file
- Attaches via MCP tool to task
- Delegate agent retrieves via MCP tool
- File never stored in git (clean repository)
- Enables prompt iteration without repository pollution

### MCP Tool Usage
Delegate agents use MCP tools for:
- Task status updates (mark stuck/review)
- Workspace initialization
- Attachment retrieval (prompt files)
- Task listing and filtering
- Time calculations for deadlines

### CLI Fallback
If MCP tools unavailable:
- Same operations available via CLI commands
- Tools automatically detect and fallback
- Ensures reliability in edge cases

---

## Troubleshooting Guide for Agents

### MCP Server Not Responding
- Check if server is running: `tasks-mcp --help`
- Fallback to CLI commands automatically
- Restart terminal session if needed

### Import Errors in Tests
- Run tests with: `pytest tests/ -v`
- Test file imports are not critical for feature work
- Focus on integration tests that cover your feature

### Database Profile Issues
- Always use `--profile dev` for development work
- Default profile for user's personal tasks
- Never pollute default database with development tasks

### Attachment Retrieval Fails
- Check filename matches exactly or partially
- Verify task ID is correct
- Use MCP tool with fallback to filesystem access

### Quality Gate Failures
- Run: `ruff check . && mypy taskmanager/ mcp_server/`
- Fix issues before marking task as "review"
- Pre-commit hooks will catch issues locally

---

## Contact & Documentation

### Key Documents
- **CHANGELOG.md**: Detailed release history and features
- **README.md**: User-facing documentation and installation
- **AGENT_GUIDANCE.md**: Agent-specific workflow documentation
- **.github/copilot-instructions.md**: AI development governance and standards

### Getting Help
- Check AGENT_GUIDANCE.md for common workflows
- Review previous task implementations for patterns
- Consult MCP tool documentation for API details
- Escalate blockers by marking task as "stuck"

---

**Last Updated**: February 6, 2026  
**Document Status**: Current with v0.10.0  
**Audience**: AI agents, developers, and technical collaborators
