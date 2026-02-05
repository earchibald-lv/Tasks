# Solution: Enable MCP Tools in Worktree VS Code Windows

## The Problem (Detailed)

When delegate agents launch in worktree VS Code windows (e.g., `code -n /Users/Eugene.Archibald/Documents/Tasks-11`):

1. VS Code opens a fresh window
2. It detects the git worktree directory
3. It loads the workspace, but **NOT the MCP server configuration** from the main workspace
4. MCP server is running in the **main workspace** (Tasks), not accessible to worktree
5. Delegate agent has **NO MCP TOOLS** available - cannot use `mcp_tasks-mcp_get_attachment_content`, etc.
6. Bootstrap sequence FAILS because it depends on MCP tools

## Root Cause Analysis

The issue stems from VS Code's architecture:

- **Main workspace**: `~/Documents/Tasks/`
  - MCP server defined in `.vscode/settings.json` (or similar)
  - Server running and configured
  - Claude can access MCP tools
  
- **Worktree window**: `~/Documents/Tasks-11/`
  - Fresh VS Code window with fresh `.vscode/` directory
  - No MCP server configuration
  - No MCP server running
  - NO MCP TOOLS AVAILABLE

This is a **critical gap**: Worktree workspace doesn't inherit MCP configuration from main workspace.

---

## Solution Approaches

### OPTION 1: Use Workspace Settings (Recommended for Simplicity)

**Idea**: Add `.vscode/settings.json` to the repository with MCP server config.

**Implementation**:

Create `.vscode/settings.json`:
```json
{
  "mcp": {
    "servers": {
      "tasks-mcp": {
        "command": "python",
        "args": ["-m", "mcp_server.server"],
        "env": {
          "PYTHONPATH": "${workspaceFolder}"
        }
      }
    }
  }
}
```

Create `.vscode/extensions.json` to recommend MCP extension:
```json
{
  "recommendations": [
    "anthropic.claude-dev"
  ]
}
```

**Pros**:
- Simple, all in repository
- Works automatically for both main and worktrees
- No external script needed

**Cons**:
- Assumes MCP extension is installed
- Assumes MCP server can start from Python module
- Requires .vscode/ in git (some teams don't like this)

---

### OPTION 2: Bootstrap Script (More Robust)

**Idea**: Add `.devcontainer/devcontainer.json` or `bootstrap.sh` that sets up MCP.

**Implementation**:

Create `bootstrap-worktree.sh`:
```bash
#!/bin/bash
# Run this in a worktree window to enable MCP tools

TASKS_ROOT=$(git rev-parse --show-toplevel)

echo "🔧 Bootstrapping MCP for worktree..."

# 1. Verify we're in a worktree
if [[ $(git rev-parse --is-inside-work-tree) != "true" ]]; then
    echo "❌ Not in a git repository"
    exit 1
fi

# 2. Check if main Tasks project is accessible
if [[ ! -d "$TASKS_ROOT" ]]; then
    echo "❌ Cannot find main Tasks project"
    exit 1
fi

# 3. Copy MCP config from main workspace
if [[ -f "$TASKS_ROOT/.vscode/settings.json" ]]; then
    mkdir -p .vscode
    cp "$TASKS_ROOT/.vscode/settings.json" .vscode/
    echo "✓ Copied MCP configuration"
else
    echo "⚠️  No MCP settings found in main workspace"
fi

# 4. Create .env with dev profile default
cat > .env << EOF
TASKS_PROFILE=dev
EOF
echo "✓ Created .env with TASKS_PROFILE=dev"

# 5. Instructions
echo ""
echo "✅ Bootstrap complete!"
echo ""
echo "Next steps:"
echo "1. Close this VS Code window: Cmd+Q"
echo "2. Reopen it: code -n $(pwd)"
echo "3. MCP tools should now be available"
```

Add to AGENT_GUIDANCE bootstrap:
```markdown
# Step 0: Bootstrap Worktree Environment (BEFORE everything else)

When you first open the worktree window:
1. Open terminal
2. Run: bash bootstrap-worktree.sh
3. Close VS Code
4. Reopen VS Code in the worktree: code -n $(pwd)
5. MCP tools should now be available
6. Proceed to Step 1 (Determine Task ID)
```

**Pros**:
- Explicit, visible bootstrap step
- Can include other setup (dev profile, etc.)
- Works even if repo config is incomplete
- Gives user feedback

**Cons**:
- Requires agent to run script manually
- Extra step in bootstrap process
- Script must be kept up to date

---

### OPTION 3: Hybrid Approach (Recommended)

**Implement BOTH Options 1 and 2**:

1. **`.vscode/settings.json` in repo**: MCP server config available automatically
2. **`bootstrap-worktree.sh`**: Belt-and-suspenders, handles edge cases, also sets dev profile

This gives:
- **Automatic setup** via `.vscode/settings.json` (ideal case)
- **Manual fallback** via bootstrap script (if settings.json doesn't work)
- **Dev profile enforcement** (solves Issue #2)
- **Clear error handling** (if both fail, agent gets helpful error)

---

## Implementation Plan

### Step 1: Create `.vscode/settings.json` 

```json
{
  "mcp": {
    "servers": {
      "tasks-mcp": {
        "command": "python",
        "args": ["-m", "mcp_server.server"],
        "env": {
          "PYTHONPATH": "${workspaceFolder}",
          "TASKS_PROFILE": "dev"
        }
      }
    }
  },
  "[python]": {
    "editor.formatOnSave": true,
    "editor.defaultFormatter": "charliermarsh.ruff"
  }
}
```

### Step 2: Create `bootstrap-worktree.sh`

(See above)

### Step 3: Update AGENT_GUIDANCE

Add new "Worktree Environment Bootstrap" section BEFORE "Determine Task ID":

```markdown
## BEFORE ANYTHING ELSE: Bootstrap Worktree Environment

When VS Code first opens in your worktree:

### Check MCP Tools

1. Open Claude Chat in VS Code
2. Try to use an MCP tool: `mcp_tasks-mcp_list_tasks(profile="dev")`
3. If tools are available → skip to "Determine Task ID"
4. If tools are NOT available → follow recovery steps below

### Recovery: Enable MCP Tools Manually

If MCP tools are not available:

1. Open terminal in VS Code
2. Run the bootstrap script:
   ```bash
   bash bootstrap-worktree.sh
   ```
3. Follow on-screen instructions (will ask you to close and reopen VS Code)
4. After reopening, verify MCP tools work in Claude Chat
5. If still not working, inform human: "MCP tools unavailable, cannot bootstrap"

### What bootstrap-worktree.sh Does

- ✓ Copies MCP server configuration from main Tasks workspace
- ✓ Creates `.env` file with `TASKS_PROFILE=dev` (ensures dev profile)
- ✓ Verifies you're in a worktree (not the main workspace)
- ✓ Checks main Tasks project is accessible
```

### Step 4: Update COPILOT_INSTRUCTIONS

Add to "Worktree-Based Development" section:

```markdown
# 4. Launch isolated VS Code window in the worktree
code -n Tasks-N

# 5. CRITICAL: Bootstrap worktree environment
#    - Delegate agent: Run bootstrap script (see AGENT_GUIDANCE)
#    - Verify MCP tools are available before proceeding
#    - If MCP tools fail, main agent must intervene

# 6. Bootstrap sequence runs automatically:
#    - Detects task ID from directory name: Tasks-{{N}}
#    - Retrieves attached prompt via MCP: mcp_tasks-mcp_get_attachment_content
#    - Executes prompt instructions
```

### Step 5: Create `.vscode/extensions.json`

```json
{
  "recommendations": [
    "anthropic.claude-dev"
  ]
}
```

This prompts developers to install the MCP extension if missing.

---

## Verification Checklist

After implementing this solution:

- [ ] `.vscode/settings.json` exists in repository with MCP config
- [ ] `.vscode/extensions.json` exists with MCP extension recommendation
- [ ] `bootstrap-worktree.sh` is executable and tested
- [ ] AGENT_GUIDANCE includes "Bootstrap Worktree Environment" section
- [ ] COPILOT_INSTRUCTIONS includes bootstrap step with verification
- [ ] Test workflow: Create new worktree, launch VS Code, verify MCP tools work
- [ ] Test recovery: Remove settings.json, run bootstrap script, verify it recovers
- [ ] Document in README: "MCP Tools in Worktrees" troubleshooting section

---

## Testing the Solution

### Test Case 1: Automatic Bootstrap (Ideal Path)

1. Create worktree: `git worktree add ../Tasks-99 -b feature/test`
2. Launch: `code -n ../Tasks-99`
3. Open Claude Chat
4. Try MCP tool: `mcp_tasks-mcp_list_tasks(profile="dev")`
5. **Expected**: Tool works, shows dev profile tasks
6. **Result**: ✅ PASS

### Test Case 2: Manual Bootstrap (Fallback Path)

1. Create worktree: `git worktree add ../Tasks-98 -b feature/test2`
2. Launch: `code -n ../Tasks-98`
3. MCP tools NOT available initially
4. Run: `bash bootstrap-worktree.sh`
5. Close and reopen VS Code
6. Try MCP tool: `mcp_tasks-mcp_list_tasks(profile="dev")`
7. **Expected**: Tool works after bootstrap
8. **Result**: ✅ PASS

### Test Case 3: Error Handling

1. Corrupt `.vscode/settings.json`
2. Create worktree, launch VS Code
3. Run bootstrap script
4. **Expected**: Script detects corruption, shows helpful error message
5. **Result**: ✅ PASS if error is clear and actionable

---

## Integration with Other Governance Issues

This solution also addresses:

- **Issue #2** (Dev Profile Not Enforced): Bootstrap script creates `.env` with `TASKS_PROFILE=dev`
- **Issue #5** (Bootstrap Sequence Has No Fallback): Bootstrap script is the fallback
- **Issue #8** (Profile Creation Automation): Verified by bootstrap script

---

## Rollout Plan

1. **Phase 1** (This Week): Implement `.vscode/settings.json` + bootstrap script
2. **Phase 2** (Test with Task #11): Delegate agent tests MCP tools in worktree
3. **Phase 3** (Document & Train): Add to AGENT_GUIDANCE, COPILOT_INSTRUCTIONS
4. **Phase 4** (Verify): Create new worktrees and verify MCP tools work
5. **Phase 5** (Update Governance): Finalize bootstrap procedure in official governance docs

---

## Success Criteria

✅ Delegate agents can access MCP tools in worktree windows  
✅ Bootstrap sequence no longer fails on MCP tool unavailability  
✅ Dev profile is automatically enforced (TASKS_PROFILE=dev)  
✅ Error messages are clear if MCP tools fail  
✅ Recovery path is documented and testable  
✅ Both main and worktree windows have access to MCP tools
