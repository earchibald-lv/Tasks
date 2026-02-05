#!/bin/bash
# Bootstrap worktree environment for Tasks project
# Run this in a worktree window to enable MCP tools and set up dev profile
# Usage: bash bootstrap-worktree.sh
# To stop MCP server: bash bootstrap-worktree.sh stop

set -e  # Exit on error

# Handle cleanup command
if [[ "$1" == "stop" ]]; then
    if [[ -f ".mcp_server.pid" ]]; then
        PID=$(cat .mcp_server.pid)
        if kill -0 $PID 2>/dev/null; then
            kill $PID
            echo "✅ Stopped MCP server (PID $PID)"
        fi
        rm .mcp_server.pid
    else
        echo "⚠️  No MCP server PID file found"
    fi
    exit 0
fi

echo "🔧 Bootstrapping worktree environment for Tasks project..."
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Verify we're in a git repository
echo "1️⃣  Checking git repository..."
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo -e "${RED}❌ Not in a git repository${NC}"
    echo "   Run this script from the worktree root directory"
    exit 1
fi
echo -e "${GREEN}✓ Git repository found${NC}"

# 2. Verify we're in a worktree (not main Tasks workspace)
echo ""
echo "2️⃣  Checking if this is a worktree..."
GIT_DIR=$(git rev-parse --git-dir)
if [[ "$GIT_DIR" == ".git" ]]; then
    echo -e "${YELLOW}⚠️  This appears to be the main workspace, not a worktree${NC}"
    echo "   Worktree bootstrap should run in isolated worktree directories"
    echo "   Continuing anyway..."
else
    echo -e "${GREEN}✓ Worktree detected${NC}"
fi

# 3. Find main Tasks project
echo ""
echo "3️⃣  Locating main Tasks project..."
WORKTREE_ROOT=$(pwd)

# For worktrees, .git is a file that points to the actual git directory
# Parse it to find the main project
if [[ -f ".git" ]]; then
    # Extract gitdir from .git file (e.g., "gitdir: /path/to/Tasks/.git/worktrees/Tasks-test")
    GITDIR_PATH=$(cat .git | grep "gitdir:" | sed 's/gitdir: //' | xargs)
    # Navigate up to find the main .git directory
    # Pattern: Tasks/.git/worktrees/Tasks-test -> Tasks
    MAIN_TASKS=$(echo "$GITDIR_PATH" | sed 's|/.git/worktrees/.*||')
else
    # Not a worktree, assume current is main
    MAIN_TASKS="$WORKTREE_ROOT"
fi

# Verify main project exists
if [[ ! -d "$MAIN_TASKS/.git" ]]; then
    echo -e "${RED}❌ Cannot find main Tasks project${NC}"
    echo "   Parsed: $MAIN_TASKS"
    echo "   Worktree: $WORKTREE_ROOT"
    echo "   .git content:"
    cat .git 2>/dev/null || echo "   (no .git file)"
    exit 1
fi
echo -e "${GREEN}✓ Main project found at: $MAIN_TASKS${NC}"

# 4. Copy MCP server configuration
echo ""
echo "4️⃣  Setting up MCP server configuration..."
if [[ -f "$MAIN_TASKS/.vscode/settings.json" ]]; then
    mkdir -p .vscode
    cp "$MAIN_TASKS/.vscode/settings.json" .vscode/
    echo -e "${GREEN}✓ Copied MCP settings.json${NC}"
else
    echo -e "${YELLOW}⚠️  MCP settings.json not found in main project${NC}"
    echo "   This is expected for new installations"
    echo "   You may need to create .vscode/settings.json manually"
    echo "   See: .vscode/settings.json.example (if available)"
fi

# 5. Copy extensions recommendations
echo ""
echo "5️⃣  Setting up VS Code extensions recommendations..."
if [[ -f "$MAIN_TASKS/.vscode/extensions.json" ]]; then
    mkdir -p .vscode
    cp "$MAIN_TASKS/.vscode/extensions.json" .vscode/
    echo -e "${GREEN}✓ Copied extensions.json${NC}"
else
    echo -e "${YELLOW}⚠️  Extensions recommendations not found${NC}"
fi

# 6. Create .env with dev profile default
echo ""
echo "6️⃣  Creating .env with dev profile..."
if [[ -f ".env" ]]; then
    echo -e "${YELLOW}⚠️  .env already exists, preserving existing file${NC}"
else
    cat > .env << 'EOF'
# Development environment for Tasks worktree
# Ensures all task operations use 'dev' profile by default
TASKS_PROFILE=dev

# Add other development settings here
EOF
    echo -e "${GREEN}✓ Created .env with TASKS_PROFILE=dev${NC}"
fi

# 7. Create .gitignore entry for .env
echo ""
echo "7️⃣  Updating .gitignore..."
if [[ -f ".gitignore" ]]; then
    if ! grep -q "^.env$" .gitignore; then
        echo ".env" >> .gitignore
        echo -e "${GREEN}✓ Added .env to .gitignore${NC}"
    else
        echo -e "${GREEN}✓ .env already in .gitignore${NC}"
    fi
else
    echo ".env" > .gitignore
    echo -e "${GREEN}✓ Created .gitignore with .env${NC}"
fi

# 8. Verify Python environment (optional but helpful)
echo ""
echo "8️⃣  Checking Python environment..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    echo -e "${GREEN}✓ Python 3 found: $PYTHON_VERSION${NC}"
else
    echo -e "${YELLOW}⚠️  Python 3 not found${NC}"
    echo "   Install Python 3 before running tasks"
fi

# 9. Start MCP server as background process
echo ""
echo "9️⃣  Starting MCP server as background process..."
# Kill any existing MCP server from this worktree
pkill -f "mcp_server.server" 2>/dev/null || true
sleep 1

# Start new MCP server in background
python3 -m mcp_server.server > .mcp_server.log 2>&1 &
MCP_PID=$!
echo $MCP_PID > .mcp_server.pid
sleep 2

# Verify server started
if kill -0 $MCP_PID 2>/dev/null; then
    echo -e "${GREEN}✓ MCP server started (PID: $MCP_PID)${NC}"
else
    echo -e "${YELLOW}⚠️  Warning: MCP server may not have started${NC}"
    echo "   Check .mcp_server.log for errors"
fi

# 10. Summary and next steps
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ Bootstrap complete!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Next steps:"
echo ""
echo "1️⃣  MCP server is now running (PID in .mcp_server.pid)"
echo ""
echo "2️⃣  Close this terminal (or just VS Code window)"
echo ""
echo "3️⃣  Reopen this worktree: code -n ."
echo "   (VS Code will reload with MCP server running in background)"
echo ""
echo "4️⃣  Verify MCP tools are available in Copilot:"
echo "   - Open Copilot Chat (@mention or Cmd+Shift+L)"
echo "   - Try: @tasks-mcp_list_tasks(profile='dev')"
echo "   - Should show tasks from dev profile"
echo ""
echo "5️⃣  If MCP tools still not available:"
echo "   - Check .mcp_server.log for errors"
echo "   - Verify MCP extension is installed: anthropic.claude-dev"
echo ""
echo "6️⃣  Determine task ID from directory name:"
echo "   Current: $(basename $(pwd))"
echo "   Pattern: Tasks-{{id}} (e.g., Tasks-11)"
echo ""
echo "7️⃣  Retrieve and read your task prompt:"
echo "   @tasks-mcp_get_attachment_content(task_id={{id}}, filename='TASK_{{id}}_PROMPT.md', profile='dev')"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 11. Provide diagnostic info
echo "Diagnostic Information:"
echo "  Worktree Root: $(pwd)"
echo "  Main Project: $MAIN_TASKS"
echo "  Task ID (inferred): $(basename $(pwd) | sed 's/Tasks-//')"
echo "  Python: $(python3 --version 2>&1 || echo 'Not found')"
echo "  Git Branch: $(git rev-parse --abbrev-ref HEAD)"
echo "  MCP Server: PID $MCP_PID (see .mcp_server.log for errors)"
echo ""
