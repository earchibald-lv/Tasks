"""MCP Tool Discovery and Configuration.

This module discovers available MCP tools for use in claude CLI sessions.
Tasks-mcp tools are hardcoded (known at build time).
Atlassian-mcp tools are discovered at runtime if the server is available.

Also provides configuration generation for ephemeral Claude sessions.
"""

import subprocess
import json
import os
import shutil
from pathlib import Path
from typing import List, Dict, Any

# Known tasks-mcp tools (extracted from mcp_server/server.py at build time)
TASKS_MCP_TOOLS = [
    "calculate_time_delta",
    "complete_task",
    "create_task",
    "create_task_interactive",
    "create_workspace",
    "delete_task",
    "delete_task_interactive",
    "delete_workspace",
    "ensure_workspace",
    "format_datetime",
    "get_current_time",
    "get_task",
    "get_workspace_info",
    "get_workspace_path",
    "list_tasks",
    "list_workspace_files",
    "search_all_tasks",
    "search_workspace",
    "update_task",
    "update_task_interactive",
]

# Default atlassian-mcp tools (from Atlassian integration)
DEFAULT_ATLASSIAN_MCP_TOOLS = [
    "search_issues",
    "get_issue",
    "create_issue",
    "update_issue",
    "transition_issue",
    "search_pages",
    "get_page",
    "create_page",
    "update_page",
]


def discover_atlassian_mcp_tools() -> List[str]:
    """Discover available atlassian-mcp tools by querying the server.
    
    Returns:
        List[str]: List of discovered atlassian-mcp tool names.
                   Falls back to DEFAULT_ATLASSIAN_MCP_TOOLS if discovery fails.
    """
    try:
        # Try to query the atlassian-mcp server for available tools
        # This is a fallback in case the server is running
        result = subprocess.run(
            ["tasks-mcp", "--list-tools"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            try:
                tools_data = json.loads(result.stdout)
                if isinstance(tools_data, list):
                    return tools_data
            except json.JSONDecodeError:
                pass
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    # Fall back to known defaults
    return DEFAULT_ATLASSIAN_MCP_TOOLS


def get_allowed_tools() -> List[str]:
    """Get the complete list of allowed tools for claude CLI.
    
    Returns:
        List[str]: List of tool specifications for --allowedTools flag.
                   Includes default tools + all tasks-mcp tools + atlassian-mcp tools.
    """
    allowed = [
        "Edit",   # Default tools
        "Bash",
        "Read",
    ]
    
    # Add all tasks-mcp tools
    allowed.extend([f"mcp__tasks-mcp__{tool}" for tool in TASKS_MCP_TOOLS])
    
    # Add discovered atlassian-mcp tools
    atlassian_tools = discover_atlassian_mcp_tools()
    allowed.extend([f"mcp__atlassian-mcp__{tool}" for tool in atlassian_tools])
    
    return allowed


def get_auto_approve_tools() -> List[str]:
    """Get the list of tools to auto-approve in settings.json.
    
    Returns:
        List[str]: List of tool names in mcp__server__tool format.
    """
    tools = [
        # Default Claude tools
        "Edit",
        "Bash",
        "Read",
        "Write",
        "MultiEdit",
    ]
    
    # Add all tasks-mcp tools
    tools.extend([f"mcp__tasks-mcp__{tool}" for tool in TASKS_MCP_TOOLS])
    
    # Add all atlassian-mcp tools
    atlassian_tools = discover_atlassian_mcp_tools()
    tools.extend([f"mcp__atlassian-mcp__{tool}" for tool in atlassian_tools])
    
    return tools


def get_mcp_servers_config() -> Dict[str, Any]:
    """Get the MCP servers configuration for .mcp.json.
    
    Returns:
        Dict[str, Any]: MCP servers configuration dictionary.
    """
    from taskmanager.config import get_settings
    
    # Get the tasks-mcp command path
    tasks_mcp_path = shutil.which("tasks-mcp")
    if not tasks_mcp_path:
        tasks_mcp_path = "tasks-mcp"  # Fallback to hoping it's in PATH
    
    servers = {
        "tasks-mcp": {
            "command": tasks_mcp_path,
            "args": [],
            "env": {}
        }
    }
    
    # Add atlassian-mcp via uvx (supports JIRA and Confluence)
    # Check if uvx is available
    uvx_path = shutil.which("uvx")
    if uvx_path:
        # Load config to get Atlassian credentials
        settings = get_settings()
        atlassian_config = settings.atlassian.resolve_secrets()
        
        # Build environment variables for atlassian-mcp
        atlassian_env = {}
        if atlassian_config.jira_url and atlassian_config.jira_token:
            atlassian_env["JIRA_URL"] = atlassian_config.jira_url
            atlassian_env["JIRA_SSL_VERIFY"] = str(atlassian_config.jira_ssl_verify).lower()
            
            if atlassian_config.jira_username:
                atlassian_env["JIRA_USERNAME"] = atlassian_config.jira_username
            if atlassian_config.jira_token:
                atlassian_env["JIRA_PERSONAL_TOKEN"] = atlassian_config.jira_token
            # Set user identifier for lookups (defaults to username if not specified)
            if atlassian_config.jira_user_identifier:
                atlassian_env["JIRA_USER_IDENTIFIER"] = atlassian_config.jira_user_identifier
            elif atlassian_config.jira_username:
                atlassian_env["JIRA_USER_IDENTIFIER"] = atlassian_config.jira_username
            
            if atlassian_config.confluence_url:
                atlassian_env["CONFLUENCE_URL"] = atlassian_config.confluence_url
            if atlassian_config.confluence_username:
                atlassian_env["CONFLUENCE_USERNAME"] = atlassian_config.confluence_username
            if atlassian_config.confluence_token:
                atlassian_env["CONFLUENCE_PERSONAL_TOKEN"] = atlassian_config.confluence_token
            if atlassian_config.confluence_url:
                atlassian_env["CONFLUENCE_SSL_VERIFY"] = str(atlassian_config.confluence_ssl_verify).lower()
            
            servers["atlassian-mcp"] = {
                "command": uvx_path,
                "args": ["--native-tls", "mcp-atlassian"],
                "env": atlassian_env
            }
    
    return servers


def create_ephemeral_session_dir(system_prompt: str, working_dir: str = None) -> tuple[Path, Dict[str, str]]:
    """Create an ephemeral Claude session directory with configuration.
    
    This creates a unique temporary directory with:
    - .claude/settings.json with permissions and preferences (merged with global)
    - .mcp.json with MCP server configurations (project-level)
    - Proper directory structure for Claude
    
    When CLAUDE_CONFIG_DIR is set, Claude Code enters "isolated mode" and ignores
    the global ~/.claude.json. To preserve user preferences (theme, model, env vars),
    we load the global ~/.claude/settings.json and merge it with our session config.
    
    Args:
        system_prompt: The system prompt to inject as globalInstructions.
        working_dir: The working directory for the session (for .mcp.json placement).
        
    Returns:
        tuple[Path, Dict[str, str]]: 
            - Path to the temporary directory
            - Environment variables to set for the session
    """
    import tempfile
    
    # Create unique temporary directory
    temp_dir = Path(tempfile.mkdtemp(prefix="claude-session-"))
    
    # Create .claude subdirectory for settings
    claude_dir = temp_dir / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    
    # Create tmp subdirectory for CLAUDE_CODE_TMPDIR
    tmp_dir = temp_dir / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    
    # Load user's global configuration files
    # ~/.claude.json contains app state/history/OAuth sessions
    # ~/.claude/settings.json contains user-defined settings (theme, model, env, permissions)
    # We need to bring both into the ephemeral session
    global_settings_path = Path.home() / ".claude" / "settings.json"
    global_claude_json_path = Path.home() / ".claude.json"
    
    base_settings = {}
    claude_json = {}
    
    # First load ~/.claude.json (app state/OAuth/history)
    if global_claude_json_path.exists():
        try:
            with open(global_claude_json_path, 'r') as f:
                claude_json = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    
    # Load ~/.claude/settings.json (user settings)
    if global_settings_path.exists():
        try:
            with open(global_settings_path, 'r') as f:
                base_settings = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    
    # Build settings.json by merging global settings with our session config
    # Our settings take precedence for critical keys
    settings = {**base_settings}  # Start with global settings
    
    # Override/add our session-specific settings
    settings.update({
        "globalInstructions": system_prompt,
        # Auto-approve all MCP servers defined in .mcp.json files
        "enableAllProjectMcpServers": True,
        # Also list specific servers for explicit approval
        "enabledMcpjsonServers": list(get_mcp_servers_config().keys()),
        "hasTrustDialogAccepted": True,
        "hasCompletedProjectOnboarding": True,
    })
    
    # Merge permissions - combine global permissions with ours
    global_permissions = base_settings.get("permissions", {})
    global_allow = global_permissions.get("allow", [])
    our_allow = get_auto_approve_tools()
    # Combine both lists, removing duplicates while preserving order
    combined_allow = list(dict.fromkeys(global_allow + our_allow))
    settings["permissions"] = {**global_permissions, "allow": combined_allow}
    
    # Write settings.json
    settings_file = claude_dir / "settings.json"
    with open(settings_file, 'w') as f:
        json.dump(settings, f, indent=2)
    
    # Write .claude.json with app state from global (OAuth, history, etc.)
    # Merge with our session-specific flags
    session_claude_json = {**claude_json}
    session_claude_json.update({
        "hasTrustDialogAccepted": True,
        "hasCompletedProjectOnboarding": True,
    })
    claude_json_file = temp_dir / ".claude.json"
    with open(claude_json_file, 'w') as f:
        json.dump(session_claude_json, f, indent=2)
    
    # Write .mcp.json with MCP server configurations
    # This goes in the config dir root (project-level config)
    mcp_config = {
        "mcpServers": get_mcp_servers_config()
    }
    mcp_file = temp_dir / ".mcp.json"
    with open(mcp_file, 'w') as f:
        json.dump(mcp_config, f, indent=2)
    
    # Prepare environment variables
    # CLAUDE_CONFIG_DIR puts Claude in isolated mode, so we must pre-seed
    # settings.json with the user's preferences (theme, model, env, etc.)
    env_vars = {
        "CLAUDE_CONFIG_DIR": str(temp_dir),
        "CLAUDE_CODE_TMPDIR": str(tmp_dir),
    }
    
    return temp_dir, env_vars
