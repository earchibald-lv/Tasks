# Ephemeral Claude Code Wrapper Implementation Guide

## Overview

This document provides a comprehensive guide for implementing ephemeral Claude Code wrapper sessions with custom settings, MCP servers, and auto-approved tool permissions. This approach allows you to programmatically launch Claude Code CLI sessions with isolated, pre-configured environments that preserve user preferences while adding session-specific configurations.

## Key Concepts

### Isolated Mode
When you set `CLAUDE_CONFIG_DIR`, Claude Code enters "isolated mode":
- It treats that directory as the source of truth
- Ignores global `~/.claude.json` to prevent contamination from your "real" home
- You must pre-seed the temporary config directory with all necessary settings

### Configuration Files

1. **`~/.claude/settings.json`** - User-defined global settings (theme, model, env vars, permissions)
2. **`~/.claude.json`** - App state, OAuth sessions, per-project history (managed by Claude)
3. **`.mcp.json`** - Project-level MCP server configurations
4. **`CLAUDE_CONFIG_DIR/.claude/settings.json`** - Ephemeral session settings (merged from global)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Python Wrapper (e.g., tasks chat)                          │
├─────────────────────────────────────────────────────────────┤
│ 1. Load global ~/.claude/settings.json (theme, model, env) │
│ 2. Load global ~/.claude.json (OAuth, history)             │
│ 3. Create ephemeral temp directory                         │
│ 4. Merge global + session-specific settings                │
│ 5. Generate .mcp.json with MCP servers                     │
│ 6. Set CLAUDE_CONFIG_DIR environment variable              │
│ 7. Launch: claude --mcp-config --strict-mcp-config         │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Claude Code CLI (Isolated Session)                         │
├─────────────────────────────────────────────────────────────┤
│ • Reads settings from $CLAUDE_CONFIG_DIR/.claude/           │
│ • Loads MCP servers from specified .mcp.json               │
│ • Auto-approves tools listed in permissions.allow          │
│ • Preserves user theme, model preferences, AWS env vars    │
│ • Isolated from global ~/.claude.json state                │
└─────────────────────────────────────────────────────────────┘
```

## Implementation

### Step 1: Create Ephemeral Session Directory

```python
import tempfile
import json
from pathlib import Path

def create_ephemeral_session_dir(system_prompt: str) -> tuple[Path, dict[str, str]]:
    """Create ephemeral Claude session with configuration."""
    
    # Create unique temporary directory
    temp_dir = Path(tempfile.mkdtemp(prefix="claude-session-"))
    
    # Create required subdirectories
    claude_dir = temp_dir / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    
    tmp_dir = temp_dir / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    
    return temp_dir, claude_dir, tmp_dir
```

### Step 2: Load and Merge Global Settings

```python
def load_global_config():
    """Load user's global Claude configuration files."""
    
    global_settings_path = Path.home() / ".claude" / "settings.json"
    global_claude_json_path = Path.home() / ".claude.json"
    
    base_settings = {}
    claude_json = {}
    
    # Load ~/.claude.json (app state/OAuth/history)
    if global_claude_json_path.exists():
        try:
            with open(global_claude_json_path, 'r') as f:
                claude_json = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    
    # Load ~/.claude/settings.json (user preferences)
    if global_settings_path.exists():
        try:
            with open(global_settings_path, 'r') as f:
                base_settings = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    
    return base_settings, claude_json
```

### Step 3: Generate MCP Server Configuration

```python
def get_mcp_servers_config() -> dict:
    """Generate MCP servers configuration with credentials."""
    
    import shutil
    
    servers = {}
    
    # Example: tasks-mcp server
    tasks_mcp_path = shutil.which("tasks-mcp")
    if tasks_mcp_path:
        servers["tasks-mcp"] = {
            "command": tasks_mcp_path,
            "args": [],
            "env": {}
        }
    
    # Example: atlassian-mcp via uvx with credentials
    uvx_path = shutil.which("uvx")
    if uvx_path:
        # Load your app's config to get credentials
        # from your_app.config import get_settings
        # settings = get_settings()
        # atlassian_config = settings.atlassian.resolve_secrets()
        
        atlassian_env = {
            "JIRA_URL": "https://your-company.atlassian.net",
            "JIRA_USERNAME": "your-email@company.com",
            "JIRA_PERSONAL_TOKEN": "your-token-or-1password-ref",
            "JIRA_SSL_VERIFY": "true",
            "CONFLUENCE_URL": "https://your-company.atlassian.net/wiki",
            "CONFLUENCE_USERNAME": "your-email@company.com",
            "CONFLUENCE_PERSONAL_TOKEN": "your-token",
            "CONFLUENCE_SSL_VERIFY": "true"
        }
        
        servers["atlassian-mcp"] = {
            "command": uvx_path,
            "args": ["--native-tls", "mcp-atlassian"],
            "env": atlassian_env
        }
    
    return servers
```

### Step 4: Generate Auto-Approve Tool List

```python
def get_auto_approve_tools() -> list[str]:
    """Get list of tools to auto-approve in permissions."""
    
    tools = [
        # Default Claude tools
        "Edit",
        "Bash",
        "Read",
        "Write",
        "MultiEdit",
    ]
    
    # Add your MCP server tools
    # Format: mcp__<server-name>__<tool-name>
    TASKS_MCP_TOOLS = [
        "create_task",
        "update_task",
        "list_tasks",
        "complete_task",
        # ... add all your tools
    ]
    
    tools.extend([f"mcp__tasks-mcp__{tool}" for tool in TASKS_MCP_TOOLS])
    
    ATLASSIAN_MCP_TOOLS = [
        "search_issues",
        "get_issue",
        "create_issue",
        "update_issue",
        # ... add all your tools
    ]
    
    tools.extend([f"mcp__atlassian-mcp__{tool}" for tool in ATLASSIAN_MCP_TOOLS])
    
    return tools
```

### Step 5: Build and Write Configuration Files

```python
def setup_ephemeral_session(temp_dir: Path, claude_dir: Path, 
                           system_prompt: str) -> dict[str, str]:
    """Setup all configuration files for ephemeral session."""
    
    # Load global config
    base_settings, claude_json = load_global_config()
    
    # Build settings.json by merging global with session-specific
    settings = {**base_settings}  # Start with global settings
    
    # Override/add session-specific settings
    settings.update({
        "globalInstructions": system_prompt,
        "enableAllProjectMcpServers": True,
        "enabledMcpjsonServers": list(get_mcp_servers_config().keys()),
        "hasTrustDialogAccepted": True,
        "hasCompletedProjectOnboarding": True,
    })
    
    # Merge permissions - combine global with ours
    global_permissions = base_settings.get("permissions", {})
    global_allow = global_permissions.get("allow", [])
    our_allow = get_auto_approve_tools()
    
    # Deduplicate while preserving order
    combined_allow = list(dict.fromkeys(global_allow + our_allow))
    settings["permissions"] = {**global_permissions, "allow": combined_allow}
    
    # Write settings.json
    settings_file = claude_dir / "settings.json"
    with open(settings_file, 'w') as f:
        json.dump(settings, f, indent=2)
    
    # Write .claude.json with app state from global
    session_claude_json = {**claude_json}
    session_claude_json.update({
        "hasTrustDialogAccepted": True,
        "hasCompletedProjectOnboarding": True,
    })
    
    claude_json_file = temp_dir / ".claude.json"
    with open(claude_json_file, 'w') as f:
        json.dump(session_claude_json, f, indent=2)
    
    # Write .mcp.json with MCP server configurations
    mcp_config = {
        "mcpServers": get_mcp_servers_config()
    }
    
    mcp_file = temp_dir / ".mcp.json"
    with open(mcp_file, 'w') as f:
        json.dump(mcp_config, f, indent=2)
    
    # Return environment variables
    tmp_dir = temp_dir / "tmp"
    return {
        "CLAUDE_CONFIG_DIR": str(temp_dir),
        "CLAUDE_CODE_TMPDIR": str(tmp_dir),
    }
```

### Step 6: Launch Claude Code CLI

```python
import subprocess
import os

def launch_claude_session(system_prompt: str, initial_prompt: str,
                         working_dir: str = None):
    """Launch ephemeral Claude Code session."""
    
    # Create ephemeral session
    temp_dir, claude_dir, tmp_dir = create_ephemeral_session_dir(system_prompt)
    
    # Setup configuration files
    session_env = setup_ephemeral_session(temp_dir, claude_dir, system_prompt)
    
    # Merge with existing environment
    full_env = os.environ.copy()
    full_env.update(session_env)
    
    # Build Claude command with strict MCP config
    mcp_config_path = temp_dir / ".mcp.json"
    claude_cmd = [
        "claude",
        "--mcp-config", str(mcp_config_path),
        "--strict-mcp-config"
    ]
    
    # Launch Claude with initial prompt via stdin
    subprocess.run(
        claude_cmd,
        cwd=working_dir or os.getcwd(),
        env=full_env,
        input=initial_prompt,
        text=True,
        check=False
    )
    
    print(f"\nSession ended. Config preserved at: {temp_dir}")
```

## Complete Working Example

```python
#!/usr/bin/env python3
"""
Ephemeral Claude Code wrapper example.
"""

import os
import json
import tempfile
import subprocess
import shutil
from pathlib import Path

def launch_ephemeral_claude(
    system_prompt: str,
    user_prompt: str,
    mcp_servers: dict,
    working_dir: str = None
):
    """Launch Claude Code in an ephemeral isolated session."""
    
    # 1. Create ephemeral workspace
    temp_dir = Path(tempfile.mkdtemp(prefix="claude-code-"))
    config_dir = temp_dir / ".claude"
    config_dir.mkdir()
    tmp_dir = temp_dir / "tmp"
    tmp_dir.mkdir()
    
    # 2. Load global settings
    global_settings_path = Path.home() / ".claude" / "settings.json"
    base_settings = {}
    if global_settings_path.exists():
        with open(global_settings_path) as f:
            base_settings = json.load(f)
    
    # 3. Build session settings (merge global + session-specific)
    settings = {**base_settings}
    settings.update({
        "globalInstructions": system_prompt,
        "enableAllProjectMcpServers": True,
        "hasTrustDialogAccepted": True,
        "hasCompletedProjectOnboarding": True,
        "permissions": {
            "allow": ["Edit", "Bash", "Read", "Write", "MultiEdit"]
        }
    })
    
    settings_file = config_dir / "settings.json"
    with open(settings_file, 'w') as f:
        json.dump(settings, f, indent=2)
    
    # 4. Write .mcp.json
    mcp_config = {"mcpServers": mcp_servers}
    mcp_file = temp_dir / ".mcp.json"
    with open(mcp_file, 'w') as f:
        json.dump(mcp_config, f, indent=2)
    
    # 5. Setup environment
    env = os.environ.copy()
    env["CLAUDE_CONFIG_DIR"] = str(temp_dir)
    env["CLAUDE_CODE_TMPDIR"] = str(tmp_dir)
    
    # 6. Launch Claude
    try:
        subprocess.run(
            ["claude", "--mcp-config", str(mcp_file), "--strict-mcp-config"],
            env=env,
            cwd=working_dir or os.getcwd(),
            input=user_prompt,
            text=True
        )
    finally:
        print(f"\nConfig preserved at: {temp_dir}")

# Usage example
if __name__ == "__main__":
    mcp_servers = {
        "sqlite": {
            "command": "uvx",
            "args": ["mcp-server-sqlite", "--db-path", "/tmp/test.db"],
            "env": {}
        }
    }
    
    launch_ephemeral_claude(
        system_prompt="You are a data engineer. Use the sqlite MCP.",
        user_prompt="Analyze the database schema.",
        mcp_servers=mcp_servers
    )
```

## Key CLI Flags

### `--mcp-config <path>`
Specifies the path to a JSON file containing your `mcpServers` definition.

### `--strict-mcp-config`
Ensures Claude doesn't pull in persistent global servers from `~/.claude.json`. Only loads servers from the specified config file.

## Environment Variables

### `CLAUDE_CONFIG_DIR`
Points to the ephemeral temp directory containing `.claude/settings.json`. When set, Claude enters isolated mode.

### `CLAUDE_CODE_TMPDIR`
Specifies temporary file storage location for the session.

## Configuration Structure

### settings.json
```json
{
  "globalInstructions": "Your custom system prompt",
  "theme": "dark",
  "model": "us.anthropic.claude-sonnet-4-20250514-v1:0",
  "alwaysThinkingEnabled": true,
  "enableAllProjectMcpServers": true,
  "enabledMcpjsonServers": ["tasks-mcp", "atlassian-mcp"],
  "hasTrustDialogAccepted": true,
  "hasCompletedProjectOnboarding": true,
  "permissions": {
    "allow": [
      "Edit",
      "Bash",
      "Read",
      "Write",
      "MultiEdit",
      "mcp__tasks-mcp__create_task",
      "mcp__atlassian-mcp__search_issues"
    ]
  },
  "env": {
    "AWS_PROFILE": "your-profile",
    "AWS_REGION": "us-east-1"
  }
}
```

### .mcp.json
```json
{
  "mcpServers": {
    "tasks-mcp": {
      "command": "/path/to/tasks-mcp",
      "args": [],
      "env": {}
    },
    "atlassian-mcp": {
      "command": "uvx",
      "args": ["--native-tls", "mcp-atlassian"],
      "env": {
        "JIRA_URL": "https://company.atlassian.net",
        "JIRA_USERNAME": "user@company.com",
        "JIRA_PERSONAL_TOKEN": "your-token",
        "JIRA_SSL_VERIFY": "true"
      }
    }
  }
}
```

## Best Practices

1. **Always merge global settings** - Load `~/.claude/settings.json` first to preserve user preferences (theme, model, env vars).

2. **Use `--strict-mcp-config`** - Prevents global MCP servers from contaminating your ephemeral session.

3. **Pre-seed all settings** - When `CLAUDE_CONFIG_DIR` is set, Claude won't look at your global config, so you must provide everything.

4. **Handle credentials securely** - Use environment variables or secret management tools (like 1Password CLI) to resolve sensitive credentials.

5. **Auto-approve tools explicitly** - List all tools you want auto-approved in `permissions.allow` using the format `mcp__<server>__<tool>`.

6. **Preserve session directories** - Keep ephemeral directories for debugging. They're helpful for inspecting what configuration was actually used.

## Troubleshooting

### MCP servers not loading
- Verify `.mcp.json` format is correct
- Check that `--mcp-config` path is absolute
- Ensure `--strict-mcp-config` is set
- Verify MCP server commands are in PATH

### Theme/model prompts appearing
- Ensure you're loading and merging `~/.claude/settings.json`
- Check that `CLAUDE_CONFIG_DIR` is set correctly
- Verify `hasTrustDialogAccepted` and `hasCompletedProjectOnboarding` are true

### Tool permissions being requested
- Add tools to `permissions.allow` array
- Use correct format: `mcp__<server-name>__<tool-name>`
- Include both default tools and MCP tools

### Credentials not working
- Verify environment variables in `.mcp.json` are set
- Check that secret resolution is working (1Password, etc.)
- Ensure SSL verification settings match your infrastructure

## Real-World Example: taskmanager

See the complete implementation in:
- `/Users/Eugene.Archibald/Documents/Tasks/taskmanager/mcp_discovery.py`
- `/Users/Eugene.Archibald/Documents/Tasks/taskmanager/cli.py` (chat command)

This implementation:
- Loads Atlassian credentials from `~/.taskmanager/config.toml`
- Resolves 1Password references automatically
- Merges global Claude settings with session-specific config
- Auto-approves 20+ tasks-mcp tools and 9+ atlassian-mcp tools
- Preserves user theme, model, and AWS environment variables

## References

- Claude Code Documentation: https://docs.anthropic.com/en/docs/build-with-claude/claude-code
- MCP Protocol: https://modelcontextprotocol.io/
- fastMCP: https://github.com/jlowin/fastmcp

## License

This guide is part of the taskmanager project. Use it freely to implement your own ephemeral Claude Code wrapper sessions.
