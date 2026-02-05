# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Custom Profile Support** (#53):
  - Removed hardcoded profile validation to allow arbitrary custom profile names
  - Support for profile-specific database paths via `ProfileModifier.database_url`
  - Automatic fallback database generation for unconfigured custom profiles
  - Profile name validation: alphanumeric characters, hyphens, and underscores allowed
  - Examples: `client-a`, `my-project`, `project-2024`, etc.

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
