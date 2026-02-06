Technical Specification: Semantic Search & Episodic Memory (v0.11.0)
Target System: Tasks Project (Python 3.12, SQLModel, SQLite) Hardware Target: Apple Silicon (M3/M4), 16GB RAM Primary Objective: Implement local-first semantic search to enable "Episodic Memory" for agents and "Frictionless Capture" for humans.

1. Architecture & Technology Decisions
1.1 The "Sidecar" Database Pattern

To preserve the lightweight nature of the core Task model and minimize token usage during standard list operations, embeddings will be stored in a separate virtual table.

Core Table: tasks (Existing SQLModel)

Vector Table: vec_tasks (sqlite-vec Virtual Table)

Relationship: 1:1 mapping via rowid (which corresponds to task.id).

1.2 The Embedding Stack

Library: fastembed (Lightweight, dependency-free, ONNX-based).

Model: nomic-ai/nomic-embed-text-v1.5

Dimensions: 384 (Matryoshka slicing enabled).

Constraint: Although Nomic is natively 768d, we strictly use the first 384 dimensions to reduce storage by 50% and increase retrieval speed.

Context Window: 8192 tokens (Enables full stack trace indexing).

2. Implementation Steps
Phase 1: Dependencies & Configuration

Add Dependencies:

fastembed

sqlite-vec

Update pyproject.toml: Ensure compatible versions for Python 3.12.

Phase 2: Database Migration (alembic)

Create a new Alembic revision. Do not add fields to models.py. The migration must execute raw SQL to initialize the virtual table.

SQL
-- Migration SQL
-- We must load the extension first if not statically linked,
-- though typically sqlite-vec is loaded at runtime connection.
-- This SQL assumes the extension is loaded by the app connection.

CREATE VIRTUAL TABLE IF NOT EXISTS vec_tasks USING vec0(
    task_id INTEGER PRIMARY KEY,
    embedding FLOAT[384]
);
Phase 3: Core Service (taskmanager/services/search.py)

Create SemanticSearchService class.

Key Methods:

__init__:

Lazy-load the TextEmbedding model (prevent CLI startup lag).

Use cache directory: ~/.cache/fastembed.

_generate_embedding(text, mode):

Crucial: Nomic requires prefixes.

If mode=storage: Prepend "search_document: ".

If mode=query: Prepend "search_query: ".

Return: List[float] of length 384.

index_task(task: Task):

Content: f"{task.title}\n{task.description}\n{str(task.tags)}"

Action: Upsert into vec_tasks.

search(query: str, limit: int = 5, threshold: float = 0.25):

SQL: SELECT task_id, distance FROM vec_tasks WHERE embedding MATCH ? AND k = ? ORDER BY distance

Logic: Fetch Task objects by ID for the results. Return List[Tuple[Task, float]].

Phase 4: Integration Hooks

Modify taskmanager/service.py (TaskService):

Create Hook: Inside create_task, after DB commit -> SemanticSearchService.index_task(new_task).

Update Hook: Inside update_task, after DB commit -> SemanticSearchService.index_task(updated_task).

Reindex Command: Add a utility function to iterate all tasks and re-index them (for the initial migration).

Phase 5: CLI Features (taskmanager/cli.py)

Command: tasks capture "{text}"

Behavior:

Generate embedding for {text}.

Search vec_tasks with strict threshold (0.2).

If Match Found:

Print: ⚠️ Similar task found: [ID] {Title} (Score: 0.15)

Prompt: Add as comment to existing task? [y/N]

If No Match:

Create new task with status PENDING.

Print: ✅ Task created.

Command: tasks recall "{query}"

Behavior:

Perform semantic search.

Output table: ID | Score | Status | Title

Render Score as visual bar: [|||||.....]

Phase 6: MCP Server Tools (mcp_server/server.py)

Tool: check_prior_work

Input: query (string)

Logic: Search all tasks.

Output: JSON list of top 3 matches with similarity scores.

Purpose: Agent uses this before creation to avoid duplication.

Tool: consult_episodic_memory

Input: problem_context (string)

Logic:

Search vec_tasks.

Filter: STRICTLY status IN (COMPLETED, ARCHIVED).

Fetch: Return description and comments (resolution details).

Purpose: Agent uses this to learn from past solutions.

3. Deliverables
A. Code Implementation

taskmanager/services/search.py

Updated taskmanager/service.py

Updated taskmanager/cli.py

Updated mcp_server/server.py

New Migration file.

B. Documentation Update

Create a new file named AGENT_SYSTEM_PROMPT_UPDATE.md. This file must contain the exact markdown text to be copy-pasted into copilot-instructions.md (or the system prompt).

Content for AGENT_SYSTEM_PROMPT_UPDATE.md:

Markdown
## Semantic Search & Episodic Memory Capabilities
You now have access to semantic search tools. You are required to use them to prevent work duplication and learn from the project's history.

### Workflow Rules:
1.  **Before Creating Tasks:** You MUST use `check_prior_work(query="...")`.
    * If a similar task exists, update it instead of creating a new one.
    * If the similar task is "STUCK", read its comments to understand why.
2.  **Before Solving Complex Bugs:** You MUST use `consult_episodic_memory(problem_context="...")`.
    * Search for similar error messages or feature requests from the past.
    * Apply patterns from successful "COMPLETED" tasks.
4. Verification Plan (Definition of Done)
Migration: Run alembic upgrade head succeeds without error.

Reindex: Run tasks maintenance reindex (new command) and confirm vec_tasks is populated via sqlite3 shell.

Test Capture: Run tasks capture "Fix the login bug" twice. The second time must trigger a "Duplicate Warning."

Test MCP: Using mcp-inspector or Claude, invoke consult_episodic_memory with a query like "database migration issues" and receive relevant closed tasks.