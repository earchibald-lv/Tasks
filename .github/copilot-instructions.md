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
2. **Agent Prompt**: Create detailed prompt instruction file and attach to the task
3. **Worktree Setup**: Create feature branch and worktree at `../Tasks-{{id}}`
4. **VS Code Isolation**: Launch new window with `code -n ../Tasks-{{id}}`
5. **Bootstrap**: Agent reads task ID from worktree directory name and retrieves attached prompt via MCP
6. **Implementation**: Develop in isolated environment following retrieved prompt instructions
7. **Quality Gates**: Lint, security scan, test before merge
8. **Merge & Cleanup**: Fast-forward merge to main, remove worktree

### Prompt File Attachment

**Purpose**: Agent instructions are attached to tasks, not stored in the repository.

**Process**:
1. Move task to in_progress status
2. Create detailed prompt file locally describing the feature requirements, acceptance criteria, and implementation guidance
3. Attach to the task using `tasks attach add {{task-id}} {{prompt-file}}`
4. Name convention: `TASK_PROMPT.md` or `FEATURE_DESIGN.md`
5. Delete local copy: `rm {{prompt-file}}` after successful attachment (file is now stored in task database)
6. When worktree agent retrieves the task, the prompt attachment is available for reading

**Benefits**:
- Repository stays clean (no worktree cruft)
- Prompts versioned with task metadata
- Easier to iterate: update attachment, agent re-reads latest prompt
- Task system becomes single source of truth for agent instructions
- Local copies cleaned up immediately after attachment

### Worktree-Based Development

**Required for**: All feature development, bug fixes, and experiments.

**Why**: Isolation prevents conflicts, enables parallel work, maintains clean git history.

**Pattern**:
```bash
# In main workspace (Tasks-60):
# 1. Create prompt file and attach to task #N
tasks --profile dev attach add N TASK_PROMPT.md

# 2. Create worktree OUTSIDE the main workspace
cd ..  # Go to parent of Tasks-60
git worktree add Tasks-N -b feature/descriptive-name

# 3. Launch isolated VS Code window in the worktree
code -n Tasks-N

# In the worktree (Tasks-N):
# 4. Bootstrap sequence runs automatically:
#    - Detects task ID from directory name: Tasks-{{N}}
#    - Retrieves attached prompt via MCP
#    - Executes prompt instructions
```

**Naming Convention**:
- **Worktree Directory**: `Tasks-{{task-id}}` (e.g., `Tasks-55`, `Tasks-60`) — MUST be at same level as main workspace, NOT nested
- **Branch**: `feature/{{descriptive-name}}` (e.g., `feature/task-attachment-prompts`)
- **Prompt**: Attached to task via `tasks attach add`, stored in task database (not in repository)

**Correct Directory Structure**:
```
/parent-directory/
├── Tasks-60/                 # Main workspace (Tasks project)
│   ├── .git/
│   ├── taskmanager/
│   ├── AGENT_GUIDANCE.md
│   └── ...
├── Tasks-55/                 # Worktree for task #55
│   ├── .git/
│   ├── taskmanager/
│   └── ...
└── Tasks-60-feature-name/    # Worktree for task #60 (alternate naming)
    ├── .git/
    ├── taskmanager/
    └── ...
```

**Committing Changes**:
When work is complete in the worktree:
1. Review changes: `git status` and `git diff`
2. Stage changes: `git add .`
3. Commit with conventional message: `git commit -m "type(#N): description"`
   - Example: `feat(#55): implement task attachment workflow`
   - Reference the task ID in the commit message
4. Verify commit: `git log -1`
5. Ready for merge to main after quality gates pass

**Integration to Main**:
After code review and quality gates pass:
1. Merge with fast-forward: `git merge --ff feature/descriptive-name`
2. Update version in `pyproject.toml` following [Semantic Versioning](#version-management):
   - **MAJOR**: Breaking API changes
   - **MINOR**: New backward-compatible features
   - **PATCH**: Bug fixes and documentation
3. Update `CHANGELOG.md` following [Keep a Changelog](https://keepachangelog.com/) format
4. Commit version bump: `git commit -m "chore(#N): bump to vX.Y.Z"`
5. Install updated package: `pipx install --force -e .`
6. Remove worktree: `git worktree remove ../Tasks-N`
7. Mark task complete: `tasks --profile dev update N --status done`

**Post-Integration Summary** (Required for all feature branch integrations):
Upon completing integration of a feature branch to main, provide a comprehensive summary for visibility:

1. **Integration Status**:
   - Feature branch merged ✓
   - Tests passing ✓
   - Version bumped ✓
   - Package installed ✓
   - Worktree cleaned ✓

2. **What Was Completed**:
   - List the 3-5 key features/changes delivered
   - Include test coverage numbers
   - Note breaking changes (if any)

3. **Pending Work** (If any):
   - List blocked or incomplete items within this task
   - Explain why (e.g., "Awaiting dependency from Task #60")
   - Link to related tasks

4. **Recommendations for Next Work** (Priority-ordered):
   - Identify 2-3 high-priority tasks that:
     - Unblock other features
     - Improve development workflow
     - Are ready to start immediately
   - Include brief rationale (e.g., "Unblocks attachment retrieval," "Critical for agent coordination")
   - Reference task IDs

**Example Summary**:
```
## Task #59 Integration Complete ✅

Feature: Attachment Filename Indexing

**Completed**:
- Dual-filename indexing (original + storage)
- Priority-based pattern matching
- 9 tests passing (100%)
- v0.8.0 released

**Pending**: None - feature fully complete

**Next High-Priority Work**:
1. Task #61 (Status Indicators): Enables agent coordination - START NOW
2. Task #57 (Content Retrieval): Improves agent workflows - Ready to start
3. Task #50 (MCP Attachment): Adds programmatic workflow - Lower priority
```

This practice ensures:
- Visibility into what's done and what remains
- Clear direction for next work (no guessing what to do)
- Documentation of dependencies
- Easier onboarding for new agents or humans reviewing progress

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
- `mcp_tasks-mcp_get_attachment_content` - Retrieve attachment file content (essential for task delegation agents to read attached prompts)
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

### MCP/CLI Feature Parity Exceptions

**Destructive Operations**: Some CLI features intentionally do NOT have MCP equivalents for safety:
- **Profile deletion** (`tasks profile delete <name>`): Only available via CLI
  - Rationale: Prevents accidental database deletion via LLM agents
  - Risk: Agents could misinterpret task requirements and delete production profiles
  - Mitigation: CLI requires user confirmation; forces explicit manual deletion
  
When designing new destructive features, default to CLI-only with explicit confirmation prompts.

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

### Delegate Agent Restrictions

**Critical Safety Boundary**: Delegate agents working on feature branches MUST NOT perform the integration workflow to merge code to `main`.

**Restrictions**:
- **Cannot merge to main**: Even if all quality gates pass, delegate agents cannot execute `git merge`
- **Cannot update version**: Version bumps in `pyproject.toml` and `CHANGELOG.md` must be done by humans
- **Cannot mark task as `integrate`**: Cannot signal merge approval—only main agent can mark `integrate`
- **Cannot mark task as `done`/`completed`**: Cannot mark tasks as complete in the default profile
- **Cannot remove worktrees**: Cleanup of feature worktrees must be done by humans

**Status Signaling (Delegate Agent Capabilities)**:
- **CAN mark**: `stuck` (blocker encountered), `review` (work complete and passing quality gates)
- **CANNOT mark**: `integrate` (merge approval only for main agent), `completed` (final completion only for human)
- When work is ready for integration: Mark task as `review`, not `integrate`
  - Main agent reviews your work, then marks as `integrate` when approved
  - This ensures human authorization before code moves to main

**Why**: The integration workflow is a critical control point. Only humans can authorize code moving to production. This prevents:
- Accidental merges of incomplete or problematic code
- Unauthorized changes to production branches
- Agents circumventing human review processes
- Unintended version bumps or release cycles

**What Delegate Agents CAN Do**:
- Implement features in worktree on feature branch
- Run all quality checks locally (lint, test, security scan)
- Commit changes with proper conventional message
- Mark task as `stuck` when blocked (requests main agent intervention)
- Mark task as `review` when work complete and passing quality gates (requests review)
- Create pull request / request human review
- **Report readiness**: Document what's been completed and what's passing

**Response to Integration Requests**: If asked to complete the integration workflow while on a feature branch, delegate agents MUST:
1. **Refuse politely**: "I cannot merge code to main or mark task as `integrate`. Only human review and approval can authorize that."
2. **Explain the boundary**: Clarify that integration and merge approval is a human-only operation
3. **Summarize progress**: Provide a detailed report of what's complete, what passes quality gates, and what's ready for human review
4. **Signal readiness**: Mark task as `review` to indicate work is ready for evaluation
5. **Direct to human**: "Please review the feature branch and mark task as `integrate` when you're satisfied, then complete the merge."

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

### Temporary Files

**Location Requirement**: All temporary files must use workspace-designated locations. Never write to `/tmp`, `/var/tmp`, or any location outside the workspace without explicit user request.

**Workspace Temp Locations**:
- **Task Prompts**: Attach files to tasks via `tasks attach add` rather than storing in workspace
- **Build/Test Artifacts**: Use `build/`, `htmlcov/`, or `.pytest_cache/` (add to `.gitignore`)
- **Development Scratch**: Create `tmp/` or `.scratch/` directory as needed, add to `.gitignore`

**Rationale**: Agents cannot reliably access `/tmp` paths or request human intervention for file creation outside workspace. Workspace-local paths ensure reproducibility and allow users to clean up artifacts without terminal involvement.

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
├── (mirror of main structure)
│   ├── taskmanager/
│   ├── tests/
│   └── ...

**Note**: Prompt files are attached to tasks in the database, not stored in worktree.
```

---

## Configuration Profiles

### Profile System

- **default**: Production use, stable database (`~/.config/taskmanager/tasks.db`)
- **dev**: Development tasks, isolated database (`~/.config/taskmanager/tasks-dev.db`)
- **test**: Testing, in-memory database (ephemeral)
- **Custom**: User-defined profiles with custom database paths and configurations

### Custom Profiles

Users can define custom profiles for different projects, clients, or contexts. Define custom profiles in `~/.config/taskmanager/settings.toml`:

```toml
[profiles.client-a]
database_url = "sqlite:///{config}/taskmanager/tasks-client-a.db"

[profiles.personal]
database_url = "sqlite:///{config}/taskmanager/tasks-personal.db"

[profiles.project-2024]
database_url = "sqlite:///{config}/taskmanager/tasks-project-2024.db"
```

Then use:
```bash
tasks --profile client-a list
tasks --profile personal add "My personal task"
tasks --profile project-2024 update 123 --status done
```

**Profile Name Rules**:
- Must contain alphanumeric characters, hyphens (-), or underscores (_)
- Examples: `client-a`, `my-project`, `client_1`, `project-2024`
- Invalid: `client@abc`, `my.project`, `project!2024` (special characters not allowed)

**Automatic Fallback**:
If a custom profile is not defined in config, the system automatically creates a database at:
```
~/.config/taskmanager/tasks-{profile}.db
```

This means you can use custom profiles without pre-configuring them in settings.toml.

### Profile Maintenance & Cleanup

**Audit Profile Databases**:
List all existing profile databases:
```bash
ls -lah ~/.config/taskmanager/tasks*.db
```

**Check Profile Contents**:
Before deleting, verify what tasks are in a profile:
```bash
tasks --profile {{profile-name}} list
```

**Delete Stale Profiles**:
Remove accidentally created or stale profile databases:
```bash
rm ~/.config/taskmanager/tasks-{{profile-name}}.db
```

**Remove from Configuration** (if pre-configured):
Edit `~/.config/taskmanager/settings.toml` and remove the profile section:
```toml
# Remove this entire section:
[profiles.stale-profile]
database_url = "sqlite:///{config}/taskmanager/tasks-stale-profile.db"
```

**Best Practice**:
- Document active profiles in `settings.toml` for team/project clarity
- Use naming conventions (e.g., `client-{{name}}`, `project-{{year}}`) to identify purpose
- Audit quarterly: `ls -lah ~/.config/taskmanager/tasks*.db | tail -10` (most recent)
- Delete both the database file AND any settings.toml entry to fully remove a profile

### Profile Selection

**CLI**: `tasks --profile dev ...` or `tasks --profile client-a ...`  
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
