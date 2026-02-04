# Quick Start - Task #45 Implementation

## TL;DR

Add profile-specific MCP server and prompt customization.

## 3 Steps

### 1. Add Config Classes to `taskmanager/config.py`

Add after the `AtlassianConfig` class definition (around line 190):

```python
class McpServerModifier(BaseModel):
    """Per-server MCP customization for a profile."""
    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    
    def resolve_secrets(self) -> "McpServerModifier":
        resolved_env = {}
        if self.env:
            for key, value in self.env.items():
                resolved_env[key] = resolve_config_value(value)
        return McpServerModifier(command=self.command, args=self.args, env=resolved_env or None)


class ProfileModifier(BaseModel):
    """Profile-level customizations."""
    mcp_servers: dict[str, McpServerModifier] = Field(default_factory=dict)
    prompt_additions: str | None = None
    
    def resolve_secrets(self) -> "ProfileModifier":
        resolved = {name: mod.resolve_secrets() for name, mod in self.mcp_servers.items()}
        return ProfileModifier(mcp_servers=resolved, prompt_additions=self.prompt_additions)
```

### 2. Update Settings Class

Add to Settings in `config.py`:

```python
# In field definitions section:
profiles: dict[str, ProfileModifier] = Field(
    default_factory=dict,
    description="Profile-specific MCP and prompt customizations"
)

# Add this method:
def get_profile_modifier(self) -> ProfileModifier | None:
    """Get resolved modifier for active profile."""
    if self.profile in self.profiles:
        return self.profiles[self.profile].resolve_secrets()
    return None
```

### 3. Apply in `chat_command()` - cli.py line ~1731

Replace MCP server config section with:

```python
mcp_servers = {"tasks": {"command": "tasks-mcp", "env": {"TASKMANAGER_PROFILE": current_profile}}}
profile_mod = settings.get_profile_modifier()

# Apply tasks-mcp overrides
if profile_mod and "tasks-mcp" in profile_mod.mcp_servers:
    mod = profile_mod.mcp_servers["tasks-mcp"]
    if mod.command: mcp_servers["tasks"]["command"] = mod.command
    if mod.args: mcp_servers["tasks"]["args"] = mod.args
    if mod.env: mcp_servers["tasks"]["env"].update(mod.env)

# (existing atlassian-mcp config code, but add similar override logic)
if profile_mod and "atlassian-mcp" in profile_mod.mcp_servers:
    mod = profile_mod.mcp_servers["atlassian-mcp"]
    # Apply overrides to atlassian config similarly

# Add to system prompt (around line 1910):
if profile_mod and profile_mod.prompt_additions:
    system_prompt += f"\n## Profile-Specific Instructions\n\n{profile_mod.prompt_additions}\n"
```

## Files Changed

- `taskmanager/config.py` - Add 2 classes, update Settings
- `taskmanager/cli.py` - Apply modifiers in chat_command
- `tests/` - Add tests (optional but recommended)

## Config Example

```toml
[profiles.dev.mcp_servers.atlassian-mcp]
env = { "JIRA_URL" = "https://dev.atlassian.net", "JIRA_PERSONAL_TOKEN" = "op://private/dev/token" }

[profiles.dev]
prompt_additions = "You are in DEV - be careful with JIRA changes"
```

## Test It

```bash
tasks --profile dev chat
# Should show dev JIRA config and include dev prompt additions
```

See `AGENT_GUIDANCE.md` for full details.
