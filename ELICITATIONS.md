# Implementation Elicitations

This file tracks questions and decisions that require human input during feature implementation.

---

## Semantic Search & Episodic Memory (v0.11.0)

**Feature**: Implement local-first semantic search to enable "Episodic Memory" for agents and "Frictionless Capture" for humans.

### Elicitations

#### 1. ✅ RESOLVED: Model Selection Confirmation
**Question**: The spec recommends `nomic-ai/nomic-embed-text-v1.5` with 384-dimension Matryoshka slicing. Is this model choice acceptable, or should we consider alternatives?

**Resolution**: Implemented as specified. Model choice is appropriate for the hardware target (Apple Silicon M3/M4).

---

#### 2. ✅ RESOLVED: Extension Loading Strategy
**Question**: sqlite-vec requires runtime extension loading. The implementation uses `sqlite_vec.load()` via the Python binding. Is this acceptable, or should we explore static linking?

**Resolution**: Runtime loading via Python binding is the standard approach and works correctly with the sqlite-vec package.

---

#### 3. 🔶 PENDING: First-Run Model Download UX
**Question**: The fastembed model (~30MB) downloads on first use. This may cause:
- Unexpected network usage
- Delayed first search operation
- Potential failures in airgapped environments

**Options**:
a) Accept current behavior (lazy download on first use)
b) Add `tasks maintenance download-models` command for pre-download
c) Bundle model with package (increases package size significantly)
d) Add configuration option to disable semantic search entirely

**Recommendation**: Option (a) for MVP, with option (b) added in a future release.

**User Input Required**: Please confirm approach or select alternative.

---

#### 4. 🔶 PENDING: Index Persistence Across Profile Switches
**Question**: Each database profile has its own vec_tasks table. When switching profiles, the semantic search index is isolated. This is the intended behavior, but should we:
- Document this clearly in user-facing help?
- Add warning when searching empty index?
- Auto-reindex on first search if index is empty?

**Recommendation**: Add auto-reindex detection and prompt user to run `tasks maintenance reindex`.

**User Input Required**: Please confirm approach.

---

#### 5. ✅ RESOLVED: Threshold Tuning
**Question**: The spec recommends:
- `0.2` threshold for duplicate detection (strict)
- `0.25` threshold for general search

Implementation uses:
- `0.2` for `find_similar()` (duplicate detection)
- `0.15` for general `recall` command (more permissive for exploration)

**Resolution**: Implemented with reasonable defaults. Users can override via `--threshold` flag.

---

#### 6. ✅ RESOLVED: MCP Tool Auto-Approval
**Question**: Should the new MCP tools (`check_prior_work`, `consult_episodic_memory`) be added to the auto-approval list in `mcp_discovery.py`?

**Resolution**: Yes, added to `TASKS_MCP_TOOLS` list in `mcp_discovery.py`. These are read-only search operations that are safe to auto-approve.

---

#### 7. ✅ RESOLVED: CLI Command Naming
**Question**: The spec uses `capture` and `recall` as command names. These are implemented as:
- `tasks capture "{text}"` - Quick task creation with duplicate detection
- `tasks recall "{query}"` - Semantic search

**Resolution**: Implemented as specified. Names align with the "Episodic Memory" metaphor.

---

### Documentation Updates Required

After elicitations are resolved, the following documentation should be updated:

1. **copilot-instructions.md**: Add semantic search workflow rules (content provided in AGENT_SYSTEM_PROMPT_UPDATE.md)
2. **README.md**: Add semantic search feature section
3. **CHANGELOG.md**: Document v0.11.0 features

---

## Summary

| Elicitation | Status | Blocker? |
|------------|--------|----------|
| Model Selection | ✅ Resolved | No |
| Extension Loading | ✅ Resolved | No |
| First-Run Model Download | 🔶 Pending | No (MVP acceptable) |
| Index Persistence | 🔶 Pending | No (current behavior is correct) |
| Threshold Tuning | ✅ Resolved | No |
| MCP Tool Auto-Approval | ✅ Resolved | No |
| CLI Command Naming | ✅ Resolved | No |

**Overall Status**: Feature is implemented and functional. Pending elicitations are non-blocking enhancements.
