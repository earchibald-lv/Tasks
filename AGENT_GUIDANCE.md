# Task #45: Profile Modifiers - Agent Implementation Guidance

## Overview

You are working on **Task #45: Feature: Allow the creation of profile modifiers**

This task adds profile-specific MCP server and prompt customization to the task management system, allowing different configurations (MCP servers, environment variables, prompts) for the `default`, `dev`, and `test` profiles.

## Current State

- Worktree: `/Users/Eugene.Archibald/Documents/Tasks-45`
- Branch: `feature/profile-modifiers`
- Current commit: `529d583` (feat: dynamic profile resolution for MCP server)
- Status: **Ready for implementation** - no partial work

## Task Requirements

From the task description in dev profile:

> Allow the configuration (including for default profile) of mappings for profile MCP servers and their associated env vars and secrets (supporting the same 1password preprocessing as currently), and custom prompt additions/modifications.

### What This Means

1. **MCP Server Customization per Profile**
   - Override MCP server command, arguments, and environment variables
   - Support profile-specific JIRA/Confluence credentials
   - Example: dev profile uses staging JIRA, production profile uses prod JIRA

2. **Secret Support**
   - Reuse existing 1Password reference system (`op://path/to/secret`)
   - Apply same preprocessing as current atlassian config

3. **Custom Prompts per Profile**
   - Add profile-specific instructions to Claude's initial system prompt
   - Example: dev profile prompts extra caution for JIRA modifications

## Implementation Plan

### Phase 1: Configuration Classes (config.py)

**Add two new Pydantic models:**

1. **McpServerModifier** - Per-server customization
   ```python
   class McpServerModifier(BaseModel):
       command: str | None = None      # Override server command
       args: list[str] | None = None   # Override args
       env: dict[str, str] | None = None  # Additional/override env vars (supports 1Password refs)
       
       def resolve_secrets(self) -> "McpServerModifier":
           # Resolve 1Password references in env vars
   ```

2. **ProfileModifier** - Profile-level customizations
   ```python
   class ProfileModifier(BaseModel):
       mcp_servers: dict[str, McpServerModifier] = {}  # Server overrides
       prompt_additions: str | None = None  # Extra system prompt text
       
       def resolve_secrets(self) -> "ProfileModifier":
           # Resolve all 1Password refs in servers
   ```

**Update Settings class:**
- Add field: `profiles: dict[str, ProfileModifier] = Field(default_factory=dict)`
- Add method: `get_profile_modifier(self) -> ProfileModifier | None`
  - Returns resolved modifier for active profile, or None

**Update default config creation:**
- Add sample `[profiles.dev]` section to demonstrate usage
- Include examples of environment-specific JIRA credentials

**Update config file loading:**
- Ensure "profiles" section is parsed from TOML
- Handle in both `load_toml_config()` and `create_settings_for_profile()`

### Phase 2: CLI Integration (cli.py - chat_command)

**Location:** Around line 1731 (MCP server configuration section)

**Changes needed:**

1. After building base `mcp_servers` dict:
   ```python
   profile_modifier = settings.get_profile_modifier()
   ```

2. For tasks-mcp server, apply modifiers if present:
   - Override command if `modifier.command` is set
   - Merge args if `modifier.args` is set
   - Merge environment variables

3. For atlassian-mcp server, apply same modifiers:
   - Allow customizing command/args/env per profile
   - Merge env vars with existing atlassian config

4. System prompt enhancement:
   - After building base system prompt
   - If `profile_modifier.prompt_additions` exists, append to prompt:
   ```python
   if profile_modifier and profile_modifier.prompt_additions:
       system_prompt += f"\n## Profile-Specific Instructions\n\n{profile_modifier.prompt_additions}\n"
   ```

### Phase 3: Testing

**Unit tests needed:**
1. Test McpServerModifier secret resolution
2. Test ProfileModifier secret resolution  
3. Test get_profile_modifier() returns correct profile
4. Test MCP server override application in chat command
5. Test prompt additions are included in system prompt
6. Test profile isolation (changes don't affect other profiles)

**Integration tests:**
1. Load config with profile modifiers
2. Launch chat session with dev profile
3. Verify MCP config contains overrides
4. Verify system prompt contains profile additions

## Configuration Examples

### Basic Usage (config.toml)

```toml
# Default production JIRA in [atlassian] section
[atlassian]
jira_url = "https://prod.atlassian.net"
jira_token = "op://private/prod/jira/token"

# Override for dev profile
[profiles.dev.mcp_servers.atlassian-mcp]
env = {
    "JIRA_URL" = "https://dev.atlassian.net",
    "JIRA_PERSONAL_TOKEN" = "op://private/dev/jira/token"
}

[profiles.dev]
prompt_additions = """You are in DEV profile. Extra caution required:
- Confirm all JIRA updates with user before execution
- Never delete issues without explicit confirmation
- Log all API calls for debugging"""
```

### Advanced Usage (Custom MCP Server)

```toml
[profiles.local.mcp_servers.atlassian-mcp]
command = "python"
args = ["-m", "mcp_atlassian.server"]
env = { "DEBUG" = "true", "LOG_LEVEL" = "DEBUG" }
```

## Key Implementation Details

1. **Backward Compatibility**
   - Existing configs work unchanged
   - Profile modifiers are optional
   - No migration required

2. **Secret Resolution**
   - Reuse `resolve_config_value()` function
   - Call `resolve_secrets()` only when needed (lazy evaluation)
   - Support op:// format for all env var values

3. **Merging Strategy**
   - Profile modifiers override global config
   - Environment variables are merged, not replaced
   - This allows profile-specific additions to base config

4. **Profile Awareness**
   - Modifiers apply to the currently active profile
   - `--profile dev` flag determines which modifier is used
   - Affects both MCP config and Claude system prompt

## Files to Modify

1. **taskmanager/config.py**
   - Add McpServerModifier class
   - Add ProfileModifier class
   - Update Settings class
   - Update config loading functions
   - Update default config template

2. **taskmanager/cli.py**
   - Update chat_command() - MCP server configuration section
   - Update system prompt building section

3. **tests/** (new/updated)
   - test_config.py - Add profile modifier tests
   - test_cli.py - Add chat command with profiles tests

## Success Criteria

- ✅ Profile modifiers can be defined in config.toml
- ✅ MCP server command/args/env are overridden per profile
- ✅ 1Password secrets are resolved in profile env vars
- ✅ Custom prompts are added to Claude system prompt per profile
- ✅ Chat command applies modifiers correctly
- ✅ Existing configs work unchanged (backward compatible)
- ✅ Tests cover all functionality
- ✅ Code follows project patterns and style

## Related Code References

**Existing patterns to follow:**

- Secret resolution: `resolve_config_value()` in config.py (line ~110)
- Atlassian config: `AtlassianConfig.resolve_secrets()` (line ~195)
- CLI context: `chat_command()` in cli.py (line ~1679)
- System prompt building: Lines 1794-1920 in cli.py

## Next Steps

1. Read this entire guide
2. Review current implementation in config.py (no changes yet)
3. Review chat_command in cli.py around line 1731
4. Implement Phase 1 (config classes)
5. Implement Phase 2 (CLI integration)
6. Write tests
7. Test with different profiles
8. Commit with message: "feat: profile modifiers for MCP servers and prompts (#45)"

## Questions?

Review the task requirements, existing code patterns, and this guidance. The implementation is straightforward - mostly adding new config classes and using them in one place (chat_command).

Good luck! 🚀
