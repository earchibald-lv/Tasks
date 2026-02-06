# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.11.0] - 2026-02-06

### Changed

- **Python 3.13 Required**:
  - Updated minimum Python version from 3.12 to 3.13
  - Rationale: Python 3.13's sqlite3 module has extension loading support enabled by default (required for sqlite-vec)
  - Installation: `pipx install -e . --python python3.13`

### Fixed

- **Semantic Search Index Pagination**:
  - Fixed `tasks maintenance reindex` command to properly paginate through all tasks
  - Previous implementation tried to fetch 1000 tasks but service layer limits requests to 100
  - Now uses pagination loop to retrieve all tasks for indexing

- **sqlite-vec Extension Loading**:
  - Added fallback for systems where `enable_load_extension` is not available
  - Checks for attribute before attempting to use it
  - Works with statically-linked sqlite-vec builds

### Added

- **Semantic Search & Episodic Memory** (SPEC-SEMANTIC-SEARCH):
  - New `taskmanager/services/search.py` module with `SemanticSearchService`
  - Integration with `fastembed` (nomic-ai/nomic-embed-text-v1.5, 384 dimensions via Matryoshka slicing)
  - Integration with `sqlite-vec` for vector storage (vec0 virtual table)
  - Lazy model loading to prevent CLI startup lag (~0ms cold start)
  - Nomic-specific prefixes: "search_document:" for indexing, "search_query:" for retrieval

- **CLI Commands** (Episodic Memory):
  - `tasks capture "Quick task description"` - Quick task creation with duplicate detection
  - `tasks recall "search query"` - Semantic search across all tasks with visual similarity bars
  - `tasks maintenance reindex` - Rebuild semantic search index for all tasks

- **MCP Tools** (Agent Memory):
  - `check_prior_work(description)` - Find similar tasks before creating new ones
  - `consult_episodic_memory(problem)` - Search completed tasks for past solutions and patterns
  - Both tools return JSON with similarity scores and recommendations

- **Dependencies**:
  - `fastembed>=0.4.0` - Text embedding model
  - `sqlite-vec>=0.1.1` - SQLite vector extension

### Changed

- **TaskService Integration**:
  - New `enable_semantic_search` parameter for service initialization
  - Automatic indexing on `create_task()` and `update_task()`
  - Automatic removal from index on `delete_task()`

- **MCP Tools Auto-Approval**:
  - Added `check_prior_work` and `consult_episodic_memory` to TASKS_MCP_TOOLS list

## [0.10.0] - 2026-02-05

### Added

- **Agent Communication Status System** (#11):
  - Four new TaskStatus enum values for multi-agent workflows:
    - `ASSIGNED` (⭐): Main agent assigned work to delegate
    - `STUCK` (⛔): Delegate blocked, needs intervention
    - `REVIEW` (🔍): Delegate work ready for review before integration
    - `INTEGRATE` (✅): Approved, ready to merge to main
  - Updated MCP server status mappings to support all new statuses
  - MCP tools support filtering and updating with new statuses
  - Updated `list_tasks` and `search_all_tasks` MCP tools to include emoji indicators for new statuses
  - Result: Complete agent communication protocol for delegated task implementation
  - Implementation: 100% backward compatible with existing statuses

- **MCP + CLI Resilience for Worktree Operations** (#11):
  - System no longer depends on MCP server autostart
  - All critical operations support dual-path: MCP-first, CLI-fallback
  - Operations with fallback: prompt retrieval, task updates, status signaling, task listing
  - Updated AGENT_GUIDANCE.md with Option A (MCP) and Option B (CLI) for all operations
  - Updated copilot-instructions.md with resilience strategy and implementation patterns
  - Result: Delegate agents work reliably even without MCP autostart
  - Result: Clear error messages and fallback guidance when MCP unavailable
  - Bootstrap script simplified to focus on environment setup only

## [0.9.0] - 2026-02-05

### Added

- **Point-in-Time Database Backups** (#1):
  - New `taskmanager backup` subcommand for backup management
  - Automatic backups before Alembic migrations (`backup_before_migration()`)
  - Backup rotation: Keep max 10 backups per profile, auto-delete oldest
  - Backup storage: `~/.config/taskmanager/backups/{profile}/` with timestamp naming
  - CLI commands: `list`, `create`, `restore` with filtering and recovery options
  - Result: Protection against data loss during schema migrations
  - Result: User-friendly backup/recovery with automatic cleanup
  - Implementation: Zero external dependencies (stdlib only)

## [0.8.4] - 2026-02-05

### Changed

- **Governance: MCP Tool for Prompt Attachments** (Governance Update):
  - Updated copilot-instructions.md to mandate MCP tool `mcp_tasks-mcp_add_attachment_from_content` for all prompt attachments
  - Deprecated CLI method `tasks attach add` for governance workflows
  - Rationale: Agent-to-agent communication requires programmatic attachment, no file system dependencies
  - Added detailed explanation: "Why MCP tool over CLI"
  - Result: Cleaner agent-to-agent delegation workflows with atomic operations

- **Governance: Always Use DEV Profile for Development Tasks** (CRITICAL):
  - Updated copilot-instructions.md to emphasize MANDATORY use of `--profile dev` for all Tasks development work
  - Added "Profile Selection" section with clear rules:
    - `dev` profile: For Tasks project development (separate database, isolated)
    - `default` profile: For user's personal task management (NEVER for Tasks development)
  - Added mandatory guidelines with check/cross marks (✅/❌)
  - Updated AGENT_GUIDANCE.md with critical warnings about profile usage
  - Added troubleshooting section in AGENT_GUIDANCE.md documenting correct profile queries
  - Result: Prevents accidental pollution of user's production task database with development tasks

- **Documentation: Enhanced Bootstrap Guidance**:
  - Updated AGENT_GUIDANCE.md "If Bootstrap Fails" section with emphasis on dev profile usage
  - Added MCP tool syntax examples for prompt attachment and retrieval
  - Added "Development Profile (CRITICAL)" section with clear rules and examples
  - Added "Prompt Attachment (MCP Tool)" section explaining why MCP is preferred
  - Added "Retrieving Prompts (MCP Tool)" section with code examples
  - Result: Clearer, more actionable guidance for delegate agents
=======
## [0.9.0] - 2026-02-04

### Added

- **Agent Communication Status System** (#11):
  - New status: `assigned` (⭐) - Main agent assigns work to delegate
  - New status: `stuck` (⛔) - Delegate blocked, needs intervention
  - New status: `review` (🔍) - Delegate work ready for review
  - New status: `integrate` (✅) - Approved, ready to merge to main
  - Enables multi-agent feature development workflows
  - Main and delegate agents can now coordinate via task status signals
  - Clear communication protocol for worktree-based development
  - Prevents unauthorized merges by restricting delegate agent permissions

### Changed

- Updated README.md with new status lifecycle documentation and workflow diagram
- Enhanced AGENT_GUIDANCE.md with status signaling instructions and usage examples
- Updated copilot-instructions.md with delegate agent restrictions and status signaling rules
- Updated CLI help text to show all available statuses (add, update commands)
>>>>>>> feature/agent-communication-statuses

## [0.8.3] - 2026-02-04

### Changed

- **Enhanced Agent Guidance for Worktree Setup** (#1):
  - Added critical warning section to AGENT_GUIDANCE.md explaining worktree location requirement
  - Clarified that worktrees MUST be created at parent directory level (not nested in main project)
  - Provided visual directory structure examples (correct vs. incorrect)
  - Documented the correct git command: `git worktree add ../Tasks-{{N}}` with emphasis on `../` path
  - Result: Prevents agent confusion during worktree bootstrap sequence

## [0.8.2] - 2026-02-04

### Fixed

- **Critical Regression: Attachment Table Missing from Dev Database** (#67):
  - Root cause 1: Database initialization called `SQLModel.metadata.create_all()` without importing models
  - Root cause 2: Alembic migrations were never run (init_db had no migration logic)
  - Root cause 3: Database config paths had double `/taskmanager/` directory
  - Fixed: Import models in database.py to register with SQLModel.metadata
  - Fixed: Implement two-step initialization (SQLModel tables → Alembic migrations)
  - Fixed: Correct database paths in config defaults and user config
  - Fixed: Make attachment migration idempotent (check if table exists before creating)
  - Fixed: Suppress Alembic logging spam in CLI output (INFO logs gone, errors still shown)
  - Result: Attachment table now created correctly for all profiles
  - Result: Migrations properly applied without conflicts or noise

## [0.8.0] - 2026-02-04

### Added

- **Dual-Filename Attachment Indexing** (#59):
  - Attachment table now stores both original and storage filenames
  - Database-backed attachment storage with dual-index support
  - Service methods: `add_db_attachment()`, `get_attachment_by_filename()`, `list_db_attachments()`
  - Pattern-based retrieval with priority-order matching:
    1. Exact match on original filename (e.g., `TASK_59_PROMPT.md`)
    2. Exact match on storage filename (e.g., `20260204_193601_TASK_59_PROMPT.md`)
    3. Substring match on original filename (e.g., `PROMPT` matches `TASK_59_PROMPT.md`)
    4. Substring match on storage filename
  - CLI enhancements: `tasks attach add/list/get` now show both filenames
  - MCP tool `tasks_attach_get_by_filename` uses reliable dual-filename matching
  - Enables reliable AGENT_GUIDANCE.md bootstrap pattern
  - 19 comprehensive tests covering all matching scenarios

## [0.7.0] - 2026-02-04

### Added

- **Profile Management CLI Commands** (#58):
  - New `tasks profile list` command shows all profiles with metadata
  - `tasks profile list --json` outputs structured data for scripting
  - `tasks profile list --configured-only` filters to configured profiles only
  - `tasks profile audit <name>` displays detailed profile information before deletion
  - `tasks profile delete <name>` safely deletes profiles with explicit "yes" confirmation
  - CLI-only deletion (no MCP) per governance: "Safety Over Speed"
  - Built-in profile protection: default, dev, test profiles cannot be deleted
  - Service layer methods: `list_profiles()`, `audit_profile()`, `delete_profile()`
  - 16 comprehensive tests covering all scenarios and edge cases

## [0.6.0] - 2026-02-04

### Added

- **Task Attachments from Stdin and MCP Payload** (#60):
  - CLI `tasks attach add` now accepts stdin input with `--filename` flag
  - Enables piping generated content: `generate-prompt.py | tasks attach add 60 -f TASK_60_PROMPT.md`
  - New MCP tool `tasks_attach_add_content` for programmatic attachment creation
  - Service layer method `add_attachment_from_content()` supports bytes and string input
  - Agents can self-generate and attach prompts without filesystem writes
  - Comprehensive test coverage (19 tests for stdin scenarios)

- **Delegate Bootstrap Prompt Documentation** (#58):
  - New `.github/prompts/delegate-bootstrap.prompt.md` with detailed bootstrap instructions
  - Documents how agents determine task ID from worktree directory and retrieve prompts

- **Delegate Agent Bootstrap Instructions** (#58):
  - AGENT_GUIDANCE.md now contains universal bootstrap sequence for task delegation
  - Agents automatically extract task ID from worktree directory (Tasks-{{id}} format)
  - Retrieve task prompt via `mcp_tasks-mcp_get_attachment_content` MCP tool
  - Execute attached prompt instructions as single source of truth
  - Improves consistency and eliminates per-task instruction duplication

## [0.5.1] - 2026-02-04

### Added

- **Attachment Content Retrieval** (#57):
  - New `tasks attach get <task-id> <filename>` CLI command for retrieving attachment content
  - Supports multiple output formats: raw (default), text, and JSON
  - New `tasks_attach_get_content` MCP tool for programmatic access
  - Enables agents to retrieve attached prompts and documents directly

- **Custom Profile Support** (#53):
  - Removed hardcoded profile validation to allow arbitrary custom profile names
  - Support for profile-specific database paths via `ProfileModifier.database_url`
  - Automatic fallback database generation for unconfigured custom profiles
  - Profile name validation: alphanumeric characters, hyphens, and underscores allowed
  - Examples: `client-a`, `my-project`, `project-2024`, etc.

### Changed

- **Governance & Integration Documentation**:
  - Added semantic versioning to integration workflow in copilot-instructions.md
  - Documented version bumping as required step before merge to main
  - Added temporary file location requirements for agent efficiency
  - Clarified agent workflow for attachment-based task prompts
  - Added `tasks_attach_get_content` tool to tasks-mcp reference

## [0.5.0] - 2026-02-04

### Added

- **Enhanced CLI Help System**:
  - Support for `-h` flag as shorthand for `--help` (native argparse support)
  - Contextual help via `HelpfulArgumentParser` - shows help on missing required arguments instead of just error messages
  - Command abbreviation matching - unambiguous command abbreviations are automatically expanded (e.g., `l` → `list`, `ad` → `add`)
  - Shell completion support via shtab integration for bash, zsh, and tcsh (`--print-completion {bash,zsh,tcsh}`)

- **Auto-approve MCP Tools** (#49):
  - Added `--allowed-tools` flag to `tasks chat` command for auto-approving MCP tools
  - Supports wildcard patterns (e.g., `mcp__tasks-mcp__*` to approve all tasks-mcp tools)
  - Eliminates tool approval prompts during Claude chat sessions

- **Profile System Extensions** (#45):
  - Added `ProfileModifier` and `McpServerModifier` classes for dynamic configuration
  - Support for profile-specific MCP server configurations
  - Enhanced settings resolution with profile-aware defaults

### Changed

- **Major CLI Architecture Overhaul**:
  - Migrated from Typer framework to pure argparse for lighter dependencies
  - Reduced CLI file size by 29% (2,169 → 1,541 lines)
  - Improved error messages and contextual help
  - Plain text output as default with fallback support

- **Table Rendering**:
  - Restored Rich library integration for beautiful table formatting
  - Implemented `print_table()` helper function for consistent output formatting
  - Maintains Rich's visual enhancements while supporting plain text fallback

- **Updated Documentation**:
  - README.md updated to reflect argparse architecture
  - Typer references replaced with argparse references throughout

### Removed

- **Typer Framework** - Migrated to native argparse for reduced complexity and dependencies
  - `typer>=0.12.0` removed from dependencies
  - Custom Typer callbacks replaced with argparse-native alternatives

### Fixed

- **CLI Table Output** - Fixed broken table formatting caused by incomplete argparse migration
  - Restored Rich Table integration while maintaining argparse benefits
  - Proper column alignment and visual formatting

### Dependencies

- **Removed**: `typer>=0.12.0`
- **Added**: `shtab>=1.7.0` for shell completion support
- **Retained**: All core dependencies (sqlmodel, rich, pydantic, fastmcp, mcp, etc.)

## [0.4.1] - 2026-02-04

### Fixed

- Auto-approve MCP tools via CLI `--allowed-tools` flag

## [0.4.0] - 2026-02-04

### Added

- Profile modifiers for MCP servers and prompts

## Previous Versions

See git history for details on versions prior to 0.4.0.

[Unreleased]: https://github.com/yourusername/taskmanager/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/yourusername/taskmanager/compare/v0.4.1...v0.5.0
[0.4.1]: https://github.com/yourusername/taskmanager/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/yourusername/taskmanager/releases/tag/v0.4.0
