#!/bin/bash
# Bootstrap worktree environment for Tasks project
# Run this in a worktree window to set up dev profile and configuration
# Usage: bash bootstrap-worktree.sh

set -e  # Exit on error

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

# 9. Summary and next steps
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ Bootstrap complete!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Your worktree is now ready for Task #$(basename $(pwd) | sed 's/Tasks-//'):"
echo ""
echo "📋 Next steps:"
echo ""
echo "1️⃣  Determine task ID from directory name"
echo "   Current: $(basename $(pwd))"
echo "   Pattern: Tasks-{{id}}"
echo ""
echo "2️⃣  Retrieve your task prompt"
echo "   MCP method (if available):"
echo "     @mcp_tasks-mcp_get_attachment_content(task_id={{id}}, filename='PROMPT', profile='dev')"
echo ""
echo "   CLI fallback (if MCP unavailable):"
echo "     tasks --profile dev attach list {{id}}"
echo "     tasks --profile dev attach get {{id}} TASK_{{id}}_PROMPT.md"
echo ""
echo "3️⃣  Read the prompt and follow all instructions"
echo ""
echo "4️⃣  Implement the feature according to the prompt"
echo ""
echo "5️⃣  Test thoroughly before committing"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Diagnostic Information:"
echo "  Worktree Root: $(pwd)"
echo "  Main Project: $MAIN_TASKS"
echo "  Task ID (inferred): $(basename $(pwd) | sed 's/Tasks-//')"
echo "  Python: $(python3 --version 2>&1 || echo 'Not found')"
echo "  Git Branch: $(git rev-parse --abbrev-ref HEAD)"
echo "  Dev Profile: Available via 'tasks --profile dev' commands"
echo ""
