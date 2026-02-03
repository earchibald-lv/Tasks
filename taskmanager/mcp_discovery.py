"""MCP Tool Discovery and Configuration.

This module discovers available MCP tools for use in claude CLI sessions.
Tasks-mcp tools are hardcoded (known at build time).
Atlassian-mcp tools are discovered at runtime if the server is available.
"""

import subprocess
import json
from typing import List

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
