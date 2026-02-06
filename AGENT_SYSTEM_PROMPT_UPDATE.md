# Agent System Prompt Update for Semantic Search

This content should be added to `copilot-instructions.md` or the agent's system prompt to enable proper use of semantic search capabilities.

---

## Semantic Search & Episodic Memory Capabilities

You now have access to semantic search tools. You are required to use them to prevent work duplication and learn from the project's history.

### Workflow Rules:

1. **Before Creating Tasks:** You MUST use `check_prior_work(query="...")`.
   - If a similar task exists, update it instead of creating a new one.
   - If the similar task is "STUCK", read its comments to understand why.

2. **Before Solving Complex Bugs:** You MUST use `consult_episodic_memory(problem_context="...")`.
   - Search for similar error messages or feature requests from the past.
   - Apply patterns from successful "COMPLETED" tasks.

### Available Tools:

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `check_prior_work` | Find similar existing tasks | Before creating ANY new task |
| `consult_episodic_memory` | Learn from past solutions | Before implementing features or fixing bugs |

### Example Workflows:

**Creating a New Task:**
```
1. User requests: "Add dark mode support"
2. Agent calls: check_prior_work(query="dark mode support theming")
3. If similar task found → Update existing task
4. If no match → Create new task
```

**Fixing a Bug:**
```
1. User reports: "Database migration fails with constraint error"
2. Agent calls: consult_episodic_memory(problem_context="database migration constraint error alembic")
3. Review past solutions for similar migration issues
4. Apply learned patterns to current fix
```

### CLI Equivalents:

For human users, equivalent CLI commands are available:
- `tasks recall "{query}"` - Semantic search across all tasks
- `tasks capture "{text}"` - Quick task creation with duplicate detection
- `tasks maintenance reindex` - Rebuild search index after data changes
