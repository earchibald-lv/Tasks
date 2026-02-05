# Tasks Project - AI Development Guidelines

**Audience**: AI coding agents (GitHub Copilot, Claude, etc.) developing this project.

**Purpose**: Governance, workflow, and standards for AI-assisted development.

---

## Core Principles

1. **Conciseness First**: Minimize token usage. Claude is already smart—provide only project-specific context.
2. **Safety Over Speed**: Destructive actions and production deployments require human approval.
3. **Quality Gates**: All code must pass linting, security scanning, and style checks before merging to main.
4. **MCP-First**: Prefer `tasks-mcp` tools over `tasks` CLI commands. CLI gaps are defects—file tasks for them.

---

## Workflow: Feature Development

### Standard Process

1. **Task Creation**: Create task via `tasks-mcp` (dev profile is the queue for development work)
2. **Prompt File**: Create detailed prompt instruction file describing the feature
3. **Worktree Setup**: Create feature branch and worktree
4. **VS Code Isolation**: Launch new window with `code -n {{worktree-path}}`
5. **Implementation**: Develop in isolated environment
6. **Quality Gates**: Lint, security scan, test before merge
7. **Merge & Cleanup**: Fast-forward merge to main, remove worktree

### Worktree-Based Development

**Required for**: All feature development, bug fixes, and experiments.

**Why**: Isolation prevents conflicts, enables parallel work, maintains clean git history.

**Pattern**:
```bash
# Create worktree for task #N
git worktree add ../Tasks-N -b feature/descriptive-name

# Create prompt file first (in main workspace)
# File: Tasks-N/TASK_PROMPT.md or Tasks-N/FEATURE_DESIGN.md

# Launch isolated VS Code window
code -n /path/to/Tasks-N
```

**Naming Convention**:
- Directory: `Tasks-{{task-id}}` (e.g., `Tasks-52`)
- Branch: `feature/N-{{descriptive-name}}` (e.g., `feature/52-enhanced-cli-help`)

### Background Agent Workflow (Future)

**Current Status**: Organization does not permit GitHub Copilot CLI for Background Agents.

**Workaround**: Local Agent creates prompt file → commit → create worktree → launch new VS Code window.

**Future State**: When Copilot CLI is approved, Background Agents will handle worktree creation and feature implementation autonomously.

**Detecting Copilot CLI**:
Periodically check to see if Copilot CLI with Background Agent support is available:
```bash
if command -v copilot &> /dev/null && copilot -p /model | grep -q "can use Background Agent"; then
    # Background Agent workflow available
    echo "Using Background Agent for autonomous feature development"
else
    # Fallback to manual worktree workflow
    echo "Using manual worktree workflow"
fi
```

---

## MCP Integration

### Tool Preference Hierarchy

1. **Preferred**: `tasks-mcp` tools (via MCP server)
2. **Fallback**: `tasks` CLI commands (when MCP equivalent unavailable)
3. **Action on Gap**: File defect task when CLI is required but MCP should handle it

### tasks-mcp Tools

Use for all task operations:
- `mcp_tasks-mcp_create_task` / `mcp_tasks-mcp_create_task_interactive`
- `mcp_tasks-mcp_update_task` / `mcp_tasks-mcp_update_task_interactive`
- `mcp_tasks-mcp_list_tasks`
- `mcp_tasks-mcp_create_workspace` / `mcp_tasks-mcp_ensure_workspace`
- Time utilities: `mcp_tasks-mcp_get_current_time`, `mcp_tasks-mcp_calculate_time_delta`

### atlassian-mcp Tools

**Scope**: Not covered in this document. See `tasks chat` startup prompts for JIRA/Confluence integration.

**Note**: When defining prompts for `tasks chat`, consult separate atlassian-mcp documentation.

### Gap Reporting

If tasks-mcp cannot accomplish something the CLI can:
1. **Acknowledge**: "This should be available via tasks-mcp but isn't. Filing defect task."
2. **File Task**: Create task documenting the gap with priority `medium`
3. **Proceed**: Use `tasks` CLI to unblock current work
4. **Tag**: Add tag `mcp-gap` to the defect task

---

## Code Quality Standards

### Linting & Style

- **Standard**: PEP 8 via `ruff`
- **Configuration**: See `pyproject.toml` → `[tool.ruff]`
- **Enforcement**: Pre-commit hooks and CI checks

**Before merge to main**:
```bash
ruff check .
ruff format .
mypy taskmanager/ mcp_server/
```

### Security Scanning

**Required**: Before any code moves to main or is installed in a live environment.

**Tools**: 
- `bandit` for Python security issues
- `safety` for dependency vulnerabilities

**Exclusions**: Code in worktrees or feature branches may skip scanning until merge-ready.

### Testing Requirements

1. **Unit Tests**: Required for all new functions/classes
   - Location: `tests/`
   - Framework: `pytest`
   - Coverage: Aim for >80% on new code

2. **Integration Tests**: Required for MCP tools and CLI commands
   - Test actual tool invocations
   - Validate against dev profile database

3. **Use Case Tests**: Automated scenarios for common workflows
   - Example: "Create task → update status → list filtered tasks"
   - Validates end-to-end functionality

**Running Tests**:
```bash
pytest tests/ -v
pytest --cov=taskmanager --cov-report=html
```

### Git Hooks

**Pre-commit**: Install hooks to enforce quality gates locally.

```bash
# Install pre-commit hooks
pre-commit install

# Manual run
pre-commit run --all-files
```

**Hooks**:
- `ruff` linting and formatting
- `mypy` type checking
- Trailing whitespace removal
- YAML/TOML validation

---

## Governance & Approvals

### Human Review Required

1. **Destructive Actions**:
   - Database migrations (production)
   - File deletions in main workspace
   - Git force pushes
   - Dependency removals

2. **Production Deployments**:
   <!-- - Publishing to PyPI -->
   - Updating live MCP servers
   - Modifying production configurations

3. **Security Changes**:
   - Authentication/authorization modifications
   - Secret management updates
   - API key rotations

### Auto-Approved

1. **Development Operations**:
   - Creating worktrees
   - Development task management (dev profile)
   - Running tests
   - Linting/formatting

2. **Documentation**:
   - README updates
   - CHANGELOG entries
   - Code comments

3. **Non-Breaking Changes**:
   - Adding new features (in feature branches)
   - Bug fixes (in feature branches)
   - Test additions

---

## Git Practices

### Commit Messages

**Format**: Conventional Commits (https://www.conventionalcommits.org/)

**Structure**:
```
<type>(#<task-id>): <subject>

<body>

<footer>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Code style (formatting, no logic change)
- `refactor`: Code restructuring (no behavior change)
- `test`: Adding/updating tests
- `chore`: Maintenance (dependencies, configs)

**Examples**:
```
feat(#52): implement copilot-instructions.md governance file

- Add workflow guidelines for worktree-based development
- Define MCP tool preference hierarchy
- Document quality gates and testing requirements

Refs: #52
```

```
fix(#49): auto-approve MCP tools via CLI --allowed-tools flag

Added wildcard pattern support for auto-approving tasks-mcp tools
during Claude chat sessions.
```

### Branch Strategy

- **main**: Production-ready code, always stable
- **feature/**: Feature development (worktree-based)
- **fix/**: Bug fixes (worktree-based)
- **experiment/**: Experimental work (may be abandoned)

**Merging**: Fast-forward preferred. Squash if history is messy.

---

## File Organization

### Protected Directories

**Never auto-modify without explicit user instruction**:
- `.git/`
- `.vscode/` (may contain user-specific settings)
- `migrations/` (database migrations are sensitive)
- Production config files

### Workspace Structure

```
Tasks/                          # Main workspace
├── .github/
│   └── copilot-instructions.md # This file
├── taskmanager/                # Core package
│   ├── cli.py                  # CLI interface (argparse)
│   ├── models.py               # SQLModel data models
│   ├── service.py              # Business logic layer
│   └── ...
├── mcp_server/                 # MCP server implementation
├── tests/                      # Test suite
├── pyproject.toml              # Package configuration
└── CHANGELOG.md                # Release history

Tasks-N/                        # Feature worktrees (isolated)
├── TASK_PROMPT.md              # Feature design/requirements
└── (mirror of main structure)
```

---

## Configuration Profiles

### Profile System

- **default**: Production use, stable database (`~/.config/taskmanager/tasks.db`)
- **dev**: Development tasks, isolated database (`~/.config/taskmanager/tasks-dev.db`)
- **test**: Testing, in-memory database (ephemeral)

### Profile Selection

**CLI**: `tasks --profile dev ...`  
**MCP Tools**: `profile` parameter (defaults to `default`)

**Development Guideline**: Use `dev` profile for all project development tasks.

---

## Dependencies & Package Management

### Adding Dependencies

1. Add to `pyproject.toml` → `dependencies` or `[project.optional-dependencies]`
2. Justify in commit message (why needed, what it provides)
3. Update requirements if lockfile used
4. Test installation: `pipx install --force -e .`

### Removing Dependencies

**⚠️ Requires Human Review**: May break existing functionality.

**Process**:
1. Verify no imports remain: `rg "import {{package}}" --type py`
2. Remove from `pyproject.toml`
3. Document in CHANGELOG under `### Removed`
4. Test full test suite
5. Request user approval before merge

---

## Version Management

### Semantic Versioning

**Format**: `MAJOR.MINOR.PATCH` (https://semver.org/)

- **MAJOR**: Breaking changes (API incompatible)
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Release Process

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md` (follow https://keepachangelog.com/)
3. Commit: `chore: bump to vX.Y.Z`
4. Test: `pipx install --force -e .`
5. **Human approval required** before publishing

---

## Troubleshooting

### Common Issues

1. **MCP Tool Not Found**:
   - Verify server is running: Check MCP status in editor
   - Check tool name: `mcp__tasks-mcp__{{tool-name}}`
   - Fallback: Use `tasks` CLI

2. **Import Errors After Dependency Changes**:
   - Reinstall: `pipx install --force -e .`
   - Check `pyproject.toml` for typos

3. **Test Failures**:
   - Check profile: Tests may use `test` profile
   - Database state: Migrations up-to-date?
   - Isolation: Run in clean environment

4. **Merge Conflicts**:
   - Rebase feature branch: `git rebase main`
   - Resolve conflicts manually
   - Verify tests pass after rebase

---

## Reference Documents

### Internal

- `README.md`: Project overview, installation, usage
- `CHANGELOG.md`: Release history and changes
- `pyproject.toml`: Package configuration, dependencies, tool settings
- `tests/`: Test suite examples

### External

- [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Semantic Versioning](https://semver.org/)
- [PEP 8](https://peps.python.org/pep-0008/)

---

## Updates to This Document

**Process**:
1. Discuss changes with project owner
2. Create task for update (dev profile)
3. Implement in feature worktree
4. Test with AI agents (validate clarity)
5. Merge after approval

**Changelog**: Document significant updates in git commit messages.

---

**Last Updated**: 2026-02-04  
**Version**: 0.1.0  
**Maintainer**: Eugene Archibald
