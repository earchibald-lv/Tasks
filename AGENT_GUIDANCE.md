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

**Use the MCP tool to read the attached prompt**:

Use `mcp_tasks-mcp_get_attachment_content` with:
- `task_id`: The numeric ID from Step 1
- `filename`: Partial match for the attached prompt (typically contains "PROMPT" or "DESIGN")

Example:
```python
# Use the MCP tool to retrieve the prompt
response = mcp_tasks_mcp_get_attachment_content(
    task_id=int(task_id),
    filename="PROMPT"  # Partial match - will find 20260204_183302_TASK_57_PROMPT.md
)
prompt_content = response  # This is the full text of the attached prompt
```

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

**If you cannot retrieve the prompt**:
1. Verify you're in a worktree (path should NOT be the main Tasks project)
2. Verify the task exists in the dev profile: `tasks --profile dev show {{id}}`
3. List attachments: `tasks --profile dev attach list {{id}}`
4. If no attachments exist, ask the human to attach the prompt file to the task

**If the prompt file is corrupted or incomplete**:
1. Save a copy: `tasks --profile dev attach get {{id}} {{filename}} > prompt_backup.txt`
2. Report the issue to the human
3. Wait for updated prompt attachment

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

1. **Delegation**: Human creates task with detailed prompt attached
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

- **Task Prompts**: Always attached to tasks via `tasks attach add`, never stored in repository
- **Local Copies**: Delete any local copies after attachment (file is in task database)
- **MCP Tool Reference**: Use `mcp_tasks-mcp_get_attachment_content` for retrieval—this is essential for delegation workflow
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
