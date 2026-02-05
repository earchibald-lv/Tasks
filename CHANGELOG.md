# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

## [0.5.2] - 2026-02-04

### Added

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
