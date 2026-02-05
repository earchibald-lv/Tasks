---
name: Delegate Bootstrap
description: Bootstrap a delegate agent session by retrieving and executing a task prompt
agent: agent
tools:
  - tasks-mcp/*
argument-hint: "[task-id]"
---

# Delegate Agent Bootstrap Session

You are being launched as a **Delegate Agent** to implement a task in an isolated worktree.

## Automatic Bootstrap Sequence

Follow these steps in order:

### Step 1: Detect Task ID from Worktree Directory

Extract the task ID from your working directory path. It should follow the format `Tasks-{{number}}`.

```python
import os
import re

cwd = os.getcwd()
dir_name = os.path.basename(cwd)

match = re.match(r'^Tasks-(\d+)$', dir_name)
if match:
    task_id = match.group(1)
    print(f"✓ Task ID detected: {task_id}")
else:
    raise RuntimeError(
        f"ERROR: Not in Tasks-N worktree!\n"
        f"Current: {dir_name}\n"
        f"Expected: Tasks-{{number}} (e.g., Tasks-60)"
    )
```

**Troubleshooting**:
- ❌ Are you in the main `Tasks-60` folder? You must be in an isolated worktree like `../Tasks-60`
- ✅ Worktree directory must be at same level as main workspace, NOT nested

### Step 2: Retrieve the Attached Task Prompt

Use the MCP tool to fetch the attached prompt file from the task database:

```python
# Use mcp_tasks-mcp_get_attachment_content
response = mcp_tasks_mcp_get_attachment_content(
    task_id=int(task_id),
    filename="PROMPT"  # Partial match - will find dated prompt file
)
prompt_content = response
print(f"✓ Retrieved {len(prompt_content)} chars of prompt")
```

**Expected output**:
- Full text of the attached `.md` prompt file
- Contains: Objective, Implementation Steps, Testing Strategy, Acceptance Criteria

**If retrieval fails**:
1. Verify task exists: `tasks --profile dev show {{task_id}}`
2. List attachments: `tasks --profile dev attach list {{task_id}}`
3. Check task status is `in_progress`
4. If no prompt, ask human to attach: `tasks attach add {{task_id}} PROMPT.md`

### Step 3: Execute the Prompt Instructions

Parse and follow the retrieved prompt:

1. **Read Objective**: What are you building?
2. **Follow Implementation Steps**: Do them in order
3. **Run Tests**: Execute all specified tests
4. **Verify Criteria**: Ensure all acceptance criteria are met
5. **Review Notes**: Understand the *why* behind decisions

### Step 4: Commit and Report

When implementation is complete:

```bash
git add .
git commit -m "feat(#{{task_id}}): {{description}}"
git log -1
```

**Report back to human**:
- ✅ All tests pass
- ✅ All acceptance criteria met
- ✅ Commit message uses conventional format
- Ready for code review and merge

## Guidelines

- **Trust the prompt**: It contains the most current requirements
- **Complete bootstrap BEFORE coding**: Don't start implementation until you've retrieved the prompt
- **Test thoroughly**: Run all tests specified in the prompt
- **Follow conventions**: Use `feat(#N):`, `fix(#N):`, etc. in commit messages
- **Ask for clarity**: If the prompt is unclear, raise the issue—don't guess

## Reference Documentation

- [AGENT_GUIDANCE.md](../../../AGENT_GUIDANCE.md) - Detailed bootstrap instructions
- [copilot-instructions.md](../copilot-instructions.md) - Governance and workflow standards

---

Good luck! 🚀
