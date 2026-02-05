# Delegate Agent Bootstrap Instructions

**Purpose**: These instructions enable delegate agents to automatically discover, retrieve, and execute task-specific implementation guidance.

---

## ⚠️ CRITICAL: Worktree Location Requirement

**The worktree directory MUST be at the parent directory level, NOT nested inside the main Tasks project**:

```
CORRECT Structure:
/Users/Eugene.Archibald/Documents/
├── Tasks/                    # Main project (Tasks)
└── Tasks-1/                  # Worktree (at parent level)
    
WRONG Structure (DO NOT CREATE):
/Users/Eugene.Archibald/Documents/Tasks/
├── Tasks-1/                  # ❌ NESTED - WRONG!
```

When creating a worktree, use:
```bash
cd /Users/Eugene.Archibald/Documents
git -C Tasks worktree add ../Tasks-{{N}} -b feature/name
```

The `../Tasks-{{N}}` path ensures the worktree is created at the PARENT directory level.

---

## Automatic Task Discovery

When you are launched in a worktree, follow this **mandatory bootstrap sequence** before beginning implementation:

### Step 1: Determine Task ID from Working Directory

**Verify you are in a Tasks-N worktree**:
- Your current working directory is: `${PWD}`
- The worktree directory MUST be named: `Tasks-{{numeric-id}}` (e.g., `Tasks-55`, `Tasks-58`, `Tasks-60`)
- The worktree MUST be at the parent directory level (not nested in /Tasks/)

**Extract task ID from the worktree directory name**:
```python
import os
import re

cwd = os.getcwd()
dir_name = os.path.basename(cwd)

# Check format: Tasks-{{number}}
match = re.match(r'^Tasks-(\d+)$', dir_name)
if match:
    task_id = match.group(1)
    print(f"✓ Detected task ID: {task_id} from {dir_name}")
else:
    raise RuntimeError(
        f"ERROR: Not in a Tasks-N worktree!\n"
        f"  Current directory: {cwd}\n"
        f"  Directory name: {dir_name}\n"
        f"  Expected format: Tasks-{{numeric-id}} (e.g., Tasks-55, Tasks-60)\n"
        f"  Solution: Create a worktree using:\n"
        f"    git worktree add ../Tasks-{{N}} -b feature/description"
    )
```

**Common mistakes**:
- ❌ Working in `/Tasks-60` (the main project) — You MUST be in an isolated worktree at a different path
- ❌ Directory named `task-60` or `Task-60` — Must be exactly `Tasks-{{number}}`
- ✅ Correct: `/path/to/Tasks-60/` where git worktree is set up

### Step 2: Retrieve the Attached Task Prompt

**Option A: Use MCP tool (Preferred if available)**:

Use `mcp_tasks-mcp_get_attachment_content` with:
- `task_id`: The numeric ID from Step 1
- `filename`: Partial match for the attached prompt (typically contains "PROMPT")
- `profile`: `"dev"`

Example:
```python
# Use the MCP tool to retrieve the prompt
response = mcp_tasks_mcp_get_attachment_content(
    task_id=int(task_id),
    filename="PROMPT",
    profile="dev"
)
prompt_content = response  # Full text of the attached prompt
```

**Option B: Use CLI fallback (if MCP tools unavailable)**:

If MCP tools are not available (no error message, just silently fail), use the CLI:

```bash
# List attachments to find the exact filename
tasks --profile dev attach list {{task_id}}

# Example output:
# Attachments for Task #58:
# - 20260204_183302_TASK_58_PROMPT.md (8.5 KB)

# Retrieve the attachment
tasks --profile dev attach get {{task_id}} {{filename}}

# Example:
tasks --profile dev attach get 58 TASK_58_PROMPT.md > prompt.md

# Read the prompt file
cat prompt.md
```

**Decision Logic**:
1. Try MCP first: `@mcp_tasks-mcp_get_attachment_content(...)`
2. If MCP is not available → use CLI: `tasks --profile dev attach list {{id}}` then `tasks --profile dev attach get {{id}} {{filename}}`
3. Both methods return the same prompt content

### Step 3: Execute the Prompt Instructions

**Parse and follow all instructions** in the retrieved prompt:

1. Read the "Objective" section for what you're building
2. Follow "Implementation Steps" in order
3. Run tests as specified in "Testing Strategy"
4. Verify all "Acceptance Criteria" are met
5. Use "Notes" for context on why certain decisions were made

---

## Critical Success Factors

### Always Follow These Principles

1. **Complete bootstrap before implementation**: Don't start coding until you've retrieved the prompt.
2. **Trust the attached prompt**: It contains the most current requirements and design decisions.
3. **Update if prompt is unclear**: If the attached prompt doesn't make sense, raise the issue to the human—don't guess.
4. **Test thoroughly**: Run all tests specified in the prompt before committing.
5. **Follow commit guidelines**: Use conventional commit format with task ID: `feat(#N): description`

### If Bootstrap Fails

**If you are NOT in a Tasks-N worktree**:
- STOP. The bootstrap process only works in an isolated worktree.
- Ask the human to create a worktree: `git worktree add ../Tasks-{{N}} -b feature/description`
- Then launch VS Code in that worktree: `code -n /path/to/Tasks-{{N}}`
- Return to Step 1 when you're in the correct directory.

**If you cannot retrieve the prompt (MCP unavailable)**:

Fall back to CLI approach:

```bash
# 1. Verify you're in a worktree (not the main Tasks directory)
pwd  # Should NOT be /Users/Eugene.Archibald/Documents/Tasks

# 2. Extract task ID from directory name
TASK_ID=$(basename $(pwd) | sed 's/Tasks-//')
echo "Task ID: $TASK_ID"

# 3. List attachments in dev profile
tasks --profile dev attach list $TASK_ID

# 4. Retrieve the prompt file
# Example: if filename is "20260204_183302_TASK_58_PROMPT.md"
tasks --profile dev attach get $TASK_ID TASK_${TASK_ID}_PROMPT.md > prompt.md

# 5. Read the prompt
cat prompt.md
```

**Verify task exists**:
```bash
tasks --profile dev show {{id}}
# Should show task details and status
# If task not found: ask human to verify task ID matches directory name
```

**If no attachments exist**:
1. Verify the human created and attached the prompt file
2. Ask the human to attach using: `mcp_tasks-mcp_add_attachment_from_content`
3. Parameters: task_id={{id}}, filename=TASK_{{id}}_PROMPT.md, profile=dev
4. Wait for attachment, then retry Step 2

**If the prompt file is corrupted or incomplete**:
1. Save a backup: `tasks --profile dev attach get {{id}} {{filename}} > backup.txt`
2. Report the issue to the human
3. Wait for updated prompt attachment via MCP tool

---

## Example Bootstrap Execution

For Task #58 (Profile Management CLI):

```
1. Working directory: /Users/Eugene.Archibald/Documents/Tasks-58
2. Extract: task_id = "58"
3. Retrieve: mcp_tasks_mcp_get_attachment_content(task_id=58, filename="PROMPT")
4. Read: Retrieved 8.5KB prompt with 3 CLI commands, implementation steps, tests
5. Execute: Follow the 4-step implementation guide in the prompt
6. Test: Run pytest for all test cases
7. Commit: git commit -m "feat(#58): implement profile management CLI commands"
```

---

## Worktree Workflow Context

This bootstrap process is part of the **Worktree-Based Development** workflow documented in `.github/copilot-instructions.md`:

1. **Delegation**: Human creates task in DEV profile with detailed prompt attached via MCP tool
2. **Setup**: Worktree created at `Tasks-{{id}}`, VS Code launched
3. **Bootstrap** (YOU ARE HERE): Retrieve task prompt via this process
4. **Implementation**: Follow prompt instructions in isolated environment
5. **Integration**: Commit, merge, cleanup worktree per governance

The attached prompt is the **single source of truth** for implementation. Trust it.

---

## Delegate Agent Status Signaling

When implementing a task in a worktree, use task status to communicate with the main branch agent. The task status system enables multi-agent coordination for feature development.

### Marking Task as STUCK

Use `stuck` when you encounter a blocker you cannot resolve independently.

**Examples of blockers**:
- Environment setup fails (Python version mismatch, dependency installation error)
- Requirements unclear or conflicting with existing code
- Missing permissions or access (database, external service)
- Design decision needed (requires human judgment)
- Dependency issue preventing progress

**When marking stuck**:
```bash
tasks update {{task_id}} --status stuck
```

Then update the task description with:
1. Detailed blocker explanation
2. Steps already tried to resolve
3. What information/permission/decision is needed
4. Any relevant error logs or stack traces

The main agent will intervene and either:
- Provide missing information/access
- Mark back to `assigned` to retry
- Mark `cancelled` if blocker is unresolvable
- Provide clarification and reassign

### Marking Task as REVIEW

Use `review` when implementation is **complete and all quality gates pass**.

**Checklist before marking review** (must pass ALL):
- [ ] All code committed to feature branch: `git status` shows clean
- [ ] No uncommitted changes: `git status`
- [ ] Linting passes: `ruff check .`
- [ ] Type checking passes: `mypy taskmanager/ mcp_server/`
- [ ] Tests pass: `pytest tests/ -v`
- [ ] Security scan passes: `bandit -r taskmanager/`
- [ ] Feature branch has all commits: `git log --oneline | head -5`

**When marking review**:
```bash
tasks update {{task_id}} --status review
```

Then update the task description with:
1. Summary of changes delivered
2. Test coverage metrics (% passing, test count)
3. Any known limitations or future improvements
4. Performance impact (if relevant)

The main agent will review your work and either:
- Mark `integrate` if approved (you can proceed with integration)
- Mark back to `assigned` with feedback (implement changes, mark `review` again)
- Mark `stuck` if they found a blocker (wait for their guidance)

### Checking for INTEGRATE Signal

Before attempting to merge feature branch to main, verify the task is marked `integrate`:

```bash
tasks show {{task_id}} | grep -i status
# Should show: Status: integrate
```

If not marked `integrate`, **DO NOT MERGE**—wait for approval.

---

## Governance Notes

### Development Profile (CRITICAL)

**Always use `--profile dev` for all development work on Tasks itself**:

```bash
# Correct - for Tasks project development:
tasks --profile dev show {{task-id}}
tasks --profile dev attach list {{task-id}}

# Wrong - pollutes production database:
tasks show {{task-id}}  # Defaults to 'default' profile!
```

**Profile Rules**:
- **`dev` profile**: For creating, managing, and working on Tasks project development tasks
  - Database: `~/.config/taskmanager/tasks-dev.db`
  - Use for: Feature development, bug fixes, experiments on Tasks application itself
  - Isolation: Separate from user's personal task database

- **`default` profile**: For user's personal task management (DO NOT USE for Tasks development)
  - Database: `~/.config/taskmanager/tasks.db`
  - Use for: Personal/production task management
  - WARNING: Using default for development pollutes user's task database with test tasks

### Prompt Attachment (MCP Tool)

Task prompts are attached via the MCP tool `mcp_tasks-mcp_add_attachment_from_content`:

```python
# Correct - using MCP tool (ALWAYS PREFERRED):
mcp_tasks-mcp_add_attachment_from_content(
    task_id=11,
    filename="TASK_11_PROMPT.md",
    content="<full prompt content>",
    profile="dev"
)

# Old/deprecated - using CLI (do not use):
tasks --profile dev attach add 11 TASK_11_PROMPT.md
```

**Why MCP tool is preferred**:
- Agent-to-agent communication: Agents attach prompts programmatically
- No file system dependencies: Content stays in task database
- Atomic operation: Success guaranteed when tool succeeds
- Cleaner: No local file cleanup required

### Retrieving Prompts (MCP Tool)

When bootstrapping in a worktree, retrieve the attached prompt:

```python
# Correct - using MCP tool:
mcp_tasks-mcp_get_attachment_content(
    task_id=11,
    filename="TASK_11_PROMPT.md"
)

# Returns: Full content of the attached prompt file
```

---

## Governance Notes

- **Task Prompts**: Always attached to tasks via MCP tool (`mcp_tasks-mcp_add_attachment_from_content`), never stored in repository
- **Profile Isolation**: ALWAYS use `--profile dev` when working on Tasks development tasks
- **MCP Tool Reference**: Use `mcp_tasks-mcp_get_attachment_content` for retrieval—essential for delegation workflow
- **Confirmation**: If you're uncertain, ask the human for clarification rather than guessing
- **Status Signaling**: Use `stuck` and `review` status to communicate with main agent—this is your primary coordination mechanism

---

**Version**: 0.5.2  
**Last Updated**: 2026-02-04  
**Audience**: Delegate AI agents (Claude, Copilot) implementing tasks in worktrees
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
