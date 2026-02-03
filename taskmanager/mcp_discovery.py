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
    """Get the MCP servers configuration for settings.json.
    
    Returns:
        Dict[str, Any]: MCP servers configuration dictionary.
    """
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
    
    # Check if atlassian-mcp is available
    atlassian_mcp_path = shutil.which("atlassian-mcp")
    if atlassian_mcp_path:
        servers["atlassian-mcp"] = {
            "command": atlassian_mcp_path,
            "args": [],
            "env": {}
        }
    
    return servers


def create_ephemeral_session_dir(system_prompt: str) -> tuple[Path, Dict[str, str]]:
    """Create an ephemeral Claude session directory with configuration.
    
    This creates a unique temporary directory with:
    - settings.json with system prompt and MCP server config
    - Proper directory structure for Claude
    
    Args:
        system_prompt: The system prompt to inject as globalInstructions.
        
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
    
    # Build settings.json
    settings = {
        "globalInstructions": system_prompt,
        "mcpServers": get_mcp_servers_config(),
        "hasTrustDialogAccepted": True,
        "hasCompletedProjectOnboarding": True,
        "autoApproveTools": get_auto_approve_tools(),
        "theme": "dark"
    }
    
    # Write settings.json
    settings_file = claude_dir / "settings.json"
    with open(settings_file, 'w') as f:
        json.dump(settings, f, indent=2)
    
    # Prepare environment variables
    env_vars = {
        "CLAUDE_CONFIG_DIR": str(temp_dir),
        "CLAUDE_CODE_TMPDIR": str(tmp_dir),
        "HOME": str(temp_dir),  # Redirect ~/.claude.json as well
    }
    
    return temp_dir, env_vars
