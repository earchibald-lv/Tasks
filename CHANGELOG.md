# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
