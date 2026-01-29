# Tasks MCP Server - Quick Start Guide

This guide will help you set up the Tasks MCP server to work with AI assistants in VS Code.

## What is the Tasks MCP Server?

The Tasks MCP (Model Context Protocol) server allows AI assistants like Claude in VS Code to manage your tasks directly. The AI can:
- Create, read, update, and delete tasks
- List tasks with filtering
- Mark tasks as complete
- Get overdue tasks and statistics
- All operations persist to the same SQLite database as the CLI

## Prerequisites

- Python 3.12 installed
- `pipx` installed ([installation guide](https://pipx.pypa.io/stable/installation/))
- VS Code with Claude or another MCP-compatible AI assistant
- Tasks project cloned/downloaded to your machine

## Installation

### Method 1: One-Click Installation (Recommended)

Click the button below to install the Tasks MCP server in VS Code:

[![Install Tasks MCP Server](https://img.shields.io/badge/Install_in_VS_Code-Tasks_MCP-blue?style=for-the-badge&logo=visualstudiocode)](vscode:mcp/install?%7B%22name%22%3A%22tasks-mcp%22%2C%22command%22%3A%22tasks-mcp%22%7D)

**Note:** You must first install the package via `pipx install /path/to/Tasks` before using this one-click configuration.

**After clicking:**
1. VS Code will prompt you to confirm the installation, showing the exact command that will be run
2. Accept the prompt to add the MCP server configuration
3. Reload VS Code or restart the AI assistant
4. The Tasks MCP server will be available to your AI assistant

### Method 2: Manual Configuration

If the one-click installation doesn't work, you can manually configure the MCP server:

### Step 1: Install the package via pipx

```bash
# Install from local project directory
pipx install /absolute/path/to/your/Tasks/project

# Or install in editable mode for development
pipx install --editable /absolute/path/to/your/Tasks/project
```

This installs the `tasks-mcp` command globally, making it available to VS Code.

### Step 2: Find your VS Code MCP settings

Open VS Code Command Palette (`Cmd+Shift+P` on Mac, `Ctrl+Shift+P` on Windows/Linux) and search for "MCP: Edit Configuration" or manually open:
- **macOS**: `~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`
- **Windows**: `%APPDATA%\Code\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json`
- **Linux**: `~/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`

### Step 3: Add the Tasks MCP server configuration

Add the following configuration to your MCP settings file:

```json
{
  "mcpServers": {
    "tasks_mcp": {
      "command": "tasks-mcp"
    }
  }
}
```

**Note:** This assumes you've installed the package via `pipx install /path/to/Tasks` which makes the `tasks-mcp` command globally available.

### Step 4: Reload VS Code

After saving the configuration:
1. Reload VS Code (`Cmd+R` on Mac, `Ctrl+R` on Windows/Linux)
2. Or restart your AI assistant
3. The Tasks MCP server should now be available

## Verifying the Installation

### Check MCP Server Status

In VS Code with Claude or your MCP-compatible assistant:
1. Open a chat
2. Ask: "What MCP servers are available?"
3. You should see `tasks_mcp` listed

### Test the Server

Try these commands to verify the server is working:

**Create a task:**
```
Create a task called "Test MCP integration" with high priority
```

**List tasks:**
```
Show me all my tasks
```

**Get statistics:**
```
What are my task statistics?
```

## Available MCP Tools

The Tasks MCP server provides these tools to AI assistants:

### Core CRUD Operations
- **`tasks_create_task`** - Create a new task
- **`tasks_get_task`** - Get task details by ID
- **`tasks_list_tasks`** - List tasks with filtering (status, priority) and pagination
- **`tasks_update_task`** - Update any task field
- **`tasks_mark_complete`** - Mark a task as completed
- **`tasks_delete_task`** - Delete a task

### Query Operations
- **`tasks_get_overdue`** - Get all overdue tasks
- **`tasks_get_statistics`** - Get task counts by status and overdue count

### Resources
- **`stats://overview`** - Task statistics overview (accessible without function calls)

## Example AI Conversations

### Creating Tasks
```
User: Create a high-priority task to "Review PR #123" due tomorrow
AI: [Creates task using tasks_create_task tool]
✓ Created task #5: Review PR #123
```

### Managing Tasks
```
User: Show me all pending tasks with high priority
AI: [Uses tasks_list_tasks with filters]
# Tasks (3 of 12)
- ○ #5: Review PR #123 (due: 2026-01-30⚠️)
  - Priority: high | Status: pending
...
```

### Getting Insights
```
User: What are my task statistics?
AI: [Uses tasks_get_statistics tool]
# Task Statistics
**Total Tasks:** 12
**Pending:** 5
**In Progress:** 2
**Completed:** 4
**Archived:** 1
**Overdue:** 1
```

## Troubleshooting

### Server Not Appearing

**Issue:** MCP server doesn't show up in available servers

**Solutions:**
1. Ensure the package is installed via pipx: `pipx install /path/to/Tasks`
2. Verify the command is available: `which tasks-mcp`
3. Verify Python 3.12 is installed: `python --version`
4. Check VS Code's output panel for MCP errors
5. Try reloading VS Code completely

### Import Errors

**Issue:** Server fails with module import errors

**Solutions:**
1. Reinstall via pipx with all dependencies:
   ```bash
   pipx install --force /path/to/Tasks/project
   ```

### Database Errors

**Issue:** Can't create or access tasks

**Solutions:**
1. Ensure the `~/.taskmanager/` directory exists and is writable
2. Check database permissions: `ls -la ~/.taskmanager/`
3. Try deleting and recreating the database:
   ```bash
   rm ~/.taskmanager/tasks.db
   python -m taskmanager add "Test task"
   ```

### Testing Outside VS Code

You can test the MCP server directly using the stdio transport:

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}}}' | tasks-mcp
```

You should see a JSON response with server capabilities.

## Database Location

The MCP server uses the same SQLite database as the CLI:
- **Database:** `~/.taskmanager/tasks.db`
- **Configuration:** `~/.taskmanager/config.toml`

Tasks created via the MCP server are immediately visible in the CLI and vice versa:

```bash
# Create a task via CLI
python -m taskmanager add "CLI task"

# Create a task via MCP (through AI assistant)
# Then check both interfaces show all tasks
python -m taskmanager list
```

## Advanced Configuration

### Environment Variables

You can pass environment variables to the MCP server:

```json
{
  "mcpServers": {
    "tasks_mcp": {
      "command": "tasks-mcp",
      "env": {
        "TASKMANAGER_DATA_DIR": "/custom/path/to/data",
        "TASKMANAGER_DATABASE_URL": "sqlite:////custom/path/tasks.db"
      }
    }
  }
}
```

### Multiple Instances

You can run multiple instances with different configurations:

```json
{
  "mcpServers": {
    "tasks_mcp_personal": {
      "command": "tasks-mcp",
      "env": {
        "TASKMANAGER_DATA_DIR": "~/.taskmanager-personal"
      }
    },
    "tasks_mcp_work": {
      "command": "tasks-mcp",
      "env": {
        "TASKMANAGER_DATA_DIR": "~/.taskmanager-work"
      }
    }
  }
}
```

## Next Steps

- Read the [main project documentation](Tasks-project-launch.md) for architecture details
- Use the CLI: `python -m taskmanager --help`
- Explore the [MCP specification](https://modelcontextprotocol.io) for advanced features
- Contribute to the project or report issues

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the project's main documentation
3. Check that all dependencies are correctly installed
4. Verify your Python version is 3.12 or higher

---

**Happy task managing with AI! 🎉**
