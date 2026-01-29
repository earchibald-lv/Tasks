# FastMCP 3.0 Beta Research & Implementation Report

**Date:** January 2025  
**Current Version:** MCP SDK 0.9.0 (using older FastMCP patterns)  
**Target Version:** FastMCP 3.0.0 Beta 1  
**Status:** Research Complete - Awaiting Decision

---

## Executive Summary

FastMCP 3.0 represents a major architectural evolution with **100+ new features** spanning authentication, user interaction, deployment, and integration capabilities. Most importantly for our project, **User Elicitation** provides the exact "form and prompting" functionality requested for MCP Apps, but works entirely in Python without requiring a TypeScript rewrite.

### Key Findings

✅ **User Elicitation solves the MCP Apps requirement** - Request structured input from users during tool execution  
✅ **70% of MCP servers** use some version of FastMCP - battle-tested and production-ready  
✅ **No breaking changes** to core decorator patterns (@tool, @resource, @prompt)  
✅ **Massive new capabilities** - authentication, authorization, middleware, transforms, HTTP deployment  
⚠️ **Migration required** - Not a drop-in replacement, requires code updates  

---

## 1. User Elicitation - The MCP Apps Alternative

### What It Is
User Elicitation allows MCP servers to request structured input from users **during tool execution**, enabling interactive, multi-turn workflows without leaving Python.

### Capabilities

```python
from fastmcp import FastMCP, Context
from dataclasses import dataclass
from typing import Literal

@dataclass
class TaskDetails:
    title: str
    priority: Literal["low", "medium", "high"]
    description: str | None = None
    tags: list[str] | None = None

mcp = FastMCP("Task Manager")

@mcp.tool
async def create_task_interactive(ctx: Context) -> str:
    """Create a task with interactive prompting for missing details"""
    
    # Ask for structured input
    result = await ctx.elicit(
        "Please provide task details",
        response_type=TaskDetails
    )
    
    # Handle user response
    if result.action == "accept":
        task = result.data
        # Create task in database
        return f"✅ Created: {task.title} (Priority: {task.priority})"
    elif result.action == "decline":
        return "❌ Task creation declined"
    else:  # cancel
        return "🚫 Task creation cancelled"
```

### Supported Response Types

| Type | Example | Use Case |
|------|---------|----------|
| **Scalars** | `str`, `int`, `bool` | Simple inputs |
| **Constrained** | `Literal["low", "medium", "high"]` | Dropdown selections |
| **Multi-select** | `[["tag1", "tag2", "tag3"]]` | Checkbox selections |
| **Dataclasses** | `TaskDetails` | Structured forms |
| **Pydantic** | `TaskModel` | Validated forms |
| **Enums** | `Priority(Enum)` | Type-safe selections |
| **Titled Options** | `{"low": {"title": "Low Priority"}}` | Better UX |

### New in FastMCP 2.14.0+

- **Default values**: `Field(default="medium")` for pre-filled forms
- **Multi-select**: Choose multiple options from a list
- **Titled options**: Human-readable labels for better UI

### Limitations (MCP Spec)

- Only **shallow objects** (no nested structures)
- Scalar properties only: `string`, `number`, `integer`, `boolean`, `enum`
- No arrays of objects (can have arrays of scalars)

### Implementation Strategy

1. **Smart defaults**: Pre-fill common values (priority="medium", today's date)
2. **Progressive disclosure**: Ask only for required fields first, then optional
3. **Validation**: Use Pydantic models for type safety
4. **Error handling**: Graceful fallbacks if elicitation fails

---

## 2. FastMCP 3.0 Architecture Overview

FastMCP 3.0 introduces three core abstractions:

### Components (What You Expose)
- **Tools**: Functions AI agents can call
- **Resources**: Data sources agents can read
- **Prompts**: Reusable prompt templates

### Providers (Where They Come From)
- **Functions**: Python functions (current approach)
- **Filesystem**: Expose files/directories as resources
- **Local Servers**: Mount local MCP servers
- **Remote Servers**: Proxy to remote MCP endpoints
- **Skills**: Reusable skill packages

### Transforms (How They Appear to Clients)
- **Namespacing**: Organize tools by prefix
- **Prompts-as-Tools**: Convert prompts to callable tools
- **Resources-as-Tools**: Make resources executable
- **Versioning**: API versioning support
- **Visibility**: Filter what clients see (auth-based)

---

## 3. Major New Features

### 3.1 Authentication & Authorization

**Built-in OAuth 2.1 Support:**
- WorkOS/AuthKit
- GitHub, Google, Azure, AWS Cognito, Auth0
- Discord, Descope, Scalekit, Supabase, OCI
- Custom OIDC providers

**Token Verification:**
- JWT validation
- Bearer tokens
- RFC 7662 token introspection
- Remote auth providers

**Use Cases:**
- Multi-user task servers
- Team collaboration features
- Secure API integrations

**Our Project:** Not immediately needed (single-user), but enables future team features.

---

### 3.2 User Elicitation (Detailed)

**Core Features:**
- Multi-turn progressive disclosure
- Form validation with Pydantic
- User actions: accept/decline/cancel
- Default values and smart forms

**Integration Points:**
1. Task creation with interactive prompts
2. Task updates with confirmation dialogs
3. Bulk operations with user approval
4. Configuration wizards

**Example Use Case:**
```python
@mcp.tool
async def update_task(ctx: Context, task_id: int) -> str:
    # Fetch current task
    task = service.get_task(task_id)
    
    # Ask what to update
    updates = await ctx.elicit(
        f"Update task: {task.title}",
        response_type=TaskUpdate  # Pydantic model with current values as defaults
    )
    
    if updates.action == "accept":
        updated = service.update_task(task_id, updates.data)
        return f"✅ Updated: {updated.title}"
    return "❌ Update cancelled"
```

---

### 3.3 Background Tasks (SEP-1686)

**Purpose:** Long-running operations that report progress without blocking clients.

**Features:**
- Progress reporting (0-100%)
- Status updates
- Cancellation support
- Client notifications

**Use Cases:**
- Batch task imports
- Report generation
- Database migrations
- Data exports

**Example:**
```python
@mcp.tool
async def bulk_import_tasks(ctx: Context, file_path: str) -> str:
    total = count_tasks_in_file(file_path)
    
    for i, task_data in enumerate(parse_file(file_path)):
        service.create_task(**task_data)
        await ctx.report_progress(
            progress=i / total,
            message=f"Imported {i}/{total} tasks"
        )
    
    return f"✅ Imported {total} tasks"
```

---

### 3.4 Middleware

**Purpose:** Intercept and modify requests/responses at protocol level.

**Built-in Middleware:**
- Logging middleware (structured logging)
- Caching middleware (TTL-based)
- Rate limiting
- Error handling
- Authentication enforcement

**Use Cases:**
- Request/response logging
- Performance monitoring
- Access control
- Error tracking

**Example:**
```python
from fastmcp.middleware import LoggingMiddleware, CachingMiddleware

mcp = FastMCP("Task Manager")
mcp.add_middleware(LoggingMiddleware())
mcp.add_middleware(CachingMiddleware(ttl=60))  # 1-minute cache
```

---

### 3.5 Sampling (LLM Text Generation)

**Purpose:** Server can request LLM completions from clients.

**Features:**
- Anthropic and OpenAI handlers
- Fallback to server-side LLM if client doesn't support sampling
- Tool calling in prompts
- Model preferences

**Use Cases:**
- AI-assisted task descriptions
- Smart task categorization
- Natural language parsing
- Suggestion generation

**Example:**
```python
@mcp.tool
async def suggest_task_improvements(ctx: Context, task_id: int) -> str:
    task = service.get_task(task_id)
    
    result = await ctx.sample(
        messages=[{
            "role": "user",
            "content": f"Suggest improvements for this task: {task.title}\n{task.description}"
        }],
        model_preferences={"anthropic": ["claude-3-5-sonnet"]}
    )
    
    return result.content
```

---

### 3.6 HTTP Deployment

**Current:** stdio transport only  
**New:** HTTP + Server-Sent Events (SSE)

**Features:**
- Streamable HTTP transport
- SSE for real-time updates
- Stateless or stateful sessions
- CORS support
- Custom middleware

**Use Cases:**
- Web dashboard for tasks
- Remote API access
- Multi-client support
- Cloud deployment

**Deployment Options:**
- Local: `fastmcp run server.py --transport http`
- Cloud: Render, Railway, Fly.io, AWS Lambda
- Docker: Containerized deployment

---

### 3.7 Declarative Configuration (fastmcp.json)

**Purpose:** Portable, shareable server configuration.

**Features:**
- Dependencies management
- Transport settings
- Environment variables
- Server metadata
- Entrypoint specification

**Example:**
```json
{
  "name": "task-manager",
  "version": "0.1.0",
  "description": "Task management MCP server",
  "transport": {
    "type": "stdio"
  },
  "environment": {
    "python": {
      "entrypoint": "mcp_server.server:main",
      "dependencies": [
        "sqlmodel>=0.0.14",
        "fastmcp>=3.0.0b1"
      ]
    }
  }
}
```

---

### 3.8 Transforms

**Namespace Transform:**
```python
from fastmcp.transforms import NamespaceTransform

# Prefix all tools with "tasks_"
mcp.add_transform(NamespaceTransform(prefix="tasks"))
# get_task → tasks_get_task
```

**Prompts-as-Tools:**
```python
from fastmcp.transforms import PromptsAsTools

# Make prompts callable as tools
mcp.add_transform(PromptsAsTools())
```

**Visibility Transform:**
```python
from fastmcp.transforms import VisibilityTransform

# Hide internal tools from clients
mcp.add_transform(VisibilityTransform(
    filter=lambda component: not component.name.startswith("_")
))
```

---

### 3.9 Providers

**Filesystem Provider:**
```python
from fastmcp.providers import FilesystemProvider

# Expose documentation as resources
mcp.add_provider(FilesystemProvider(
    path="./docs",
    extensions=[".md", ".txt"]
))
```

**Proxy Provider:**
```python
from fastmcp.providers import ProxyProvider

# Mount remote MCP server
mcp.add_provider(ProxyProvider(
    url="https://api.example.com/mcp",
    prefix="external"
))
```

**Skills Provider:**
```python
from fastmcp.providers import SkillsProvider

# Load reusable skill packages
mcp.add_provider(SkillsProvider(
    skills=["calendar", "notifications", "reminders"]
))
```

---

## 4. Migration Path

### Phase 1: Upgrade to FastMCP 3.0 (Minimal Changes)

**Changes Required:**
1. Update `pyproject.toml`: `fastmcp>=3.0.0b1`
2. Update imports: `from fastmcp import FastMCP, Context`
3. Update MCP dependency: `mcp>=1.23` (required by FastMCP 3.0)
4. Test existing tools/resources/prompts

**Expected Impact:** Low - core decorators remain compatible

**Effort:** 1-2 hours

---

### Phase 2: Implement User Elicitation (High Priority)

**Changes Required:**
1. Add `async` to tool functions that need elicitation
2. Add `ctx: Context` parameter
3. Create Pydantic models for forms
4. Implement elicitation calls
5. Handle user responses (accept/decline/cancel)

**Example Tools to Update:**
- `create_task` → Interactive form for all fields
- `update_task` → Confirmation dialog with current values
- `delete_task` → Confirmation prompt
- `bulk_import` → File selection and preview

**Expected Impact:** High - major UX improvement

**Effort:** 4-8 hours

---

### Phase 3: Add Background Tasks & Progress (Medium Priority)

**Changes Required:**
1. Identify long-running operations
2. Add progress reporting
3. Implement cancellation handling

**Example Tools:**
- Bulk imports
- Batch updates
- Report generation
- Data exports

**Expected Impact:** Medium - better feedback for slow operations

**Effort:** 2-4 hours

---

### Phase 4: Middleware & Logging (Low Priority)

**Changes Required:**
1. Add logging middleware
2. Configure structured logging
3. Add caching for expensive queries

**Expected Impact:** Low - operational improvements

**Effort:** 1-2 hours

---

### Phase 5: HTTP Deployment (Future)

**Changes Required:**
1. Update transport configuration
2. Configure CORS
3. Add authentication (if needed)
4. Deploy to cloud

**Expected Impact:** High - enables web access

**Effort:** 4-8 hours

---

## 5. Comparison Table

| Feature | Current (MCP 0.9.0) | FastMCP 3.0 Beta |
|---------|-------------------|------------------|
| **Core Decorators** | ✅ @tool, @resource | ✅ @tool, @resource, @prompt |
| **User Interaction** | ❌ No forms | ✅ **User Elicitation** |
| **Background Tasks** | ❌ Blocking only | ✅ Progress reporting |
| **Authentication** | ❌ None | ✅ OAuth 2.1, JWT, Bearer |
| **Middleware** | ❌ None | ✅ Logging, caching, rate limiting |
| **Sampling** | ❌ None | ✅ Client + server-side LLM |
| **Transport** | ✅ stdio | ✅ stdio, HTTP, SSE |
| **Configuration** | ❌ Code only | ✅ Declarative JSON |
| **Transforms** | ❌ Manual prefixing | ✅ Namespace, visibility, versioning |
| **Providers** | ❌ Manual mounting | ✅ Filesystem, proxy, skills |
| **Production Ready** | ⚠️ Basic | ✅ Battle-tested (70% of MCP servers) |

---

## 6. Recommendations

### ✅ **RECOMMENDED: Upgrade to FastMCP 3.0**

**Rationale:**
1. **User Elicitation** solves the MCP Apps requirement without TypeScript
2. **No breaking changes** to core patterns we're already using
3. **Future-proof** - FastMCP is the de facto standard (70% market share)
4. **Production-ready** - 2+ years of development, 22.4k stars
5. **Active development** - Regular releases, strong community

### 📋 **Implementation Plan**

**Week 1: Foundation**
- [ ] Upgrade to FastMCP 3.0.0b1
- [ ] Update MCP SDK to >=1.23
- [ ] Run test suite to verify compatibility
- [ ] Update documentation

**Week 2: User Elicitation**
- [ ] Create Pydantic models for task forms
- [ ] Implement interactive `create_task`
- [ ] Implement interactive `update_task`
- [ ] Add confirmation for `delete_task`
- [ ] Add bulk operation confirmations

**Week 3: Background Tasks** (Optional)
- [ ] Identify long-running operations
- [ ] Add progress reporting
- [ ] Test with large datasets

**Week 4: Polish** (Optional)
- [ ] Add middleware (logging, caching)
- [ ] Improve error handling
- [ ] Performance optimization

---

## 7. Questions for Decision

### Priority Questions

1. **User Elicitation Priority?**
   - Should we implement this immediately?
   - Which tools should get interactive forms first?
   - Do we want progressive disclosure (step-by-step) or full forms?

2. **Background Tasks?**
   - Do we have operations that take >5 seconds?
   - Should bulk imports show progress?
   - Is cancellation support needed?

3. **HTTP Deployment?**
   - Do we want web-based task management?
   - Should we support remote access?
   - Is multi-user support needed?

### Technical Questions

4. **Authentication?**
   - Is this still a single-user app?
   - Future plans for team collaboration?
   - Need for API keys/tokens?

5. **Middleware?**
   - Want structured logging?
   - Need request caching?
   - Rate limiting required?

6. **Sampling?**
   - Want AI-assisted features?
   - Task description suggestions?
   - Smart categorization?

### Migration Questions

7. **Upgrade Timing?**
   - Upgrade now (before Phase 4)?
   - After Phase 4 completion?
   - Incremental migration?

8. **Beta vs. Stable?**
   - Use 3.0.0b1 now?
   - Wait for 3.0.0 stable release?
   - What's our risk tolerance?

---

## 8. Risks & Mitigation

### Risk 1: Beta Stability
**Risk:** 3.0 is still in beta  
**Mitigation:** 
- 70% of MCP servers already use FastMCP
- Active development with frequent releases
- Strong community support
- Can rollback if issues arise

### Risk 2: Migration Complexity
**Risk:** Breaking changes during migration  
**Mitigation:**
- Phased approach (test after each step)
- Comprehensive test suite (69 tests)
- Version control (can revert)
- Core decorators remain compatible

### Risk 3: Documentation Gap
**Risk:** Beta documentation may be incomplete  
**Mitigation:**
- Extensive official docs (500+ pages)
- Active GitHub community
- Example repositories
- Can reference 2.x docs for stable features

---

## 9. Code Examples

### Example 1: Interactive Task Creation

```python
from fastmcp import FastMCP, Context
from pydantic import BaseModel, Field
from typing import Literal
from datetime import date

class TaskCreationForm(BaseModel):
    title: str = Field(description="Task title (required)")
    description: str | None = Field(default=None, description="Detailed description")
    priority: Literal["low", "medium", "high"] = Field(
        default="medium",
        description="Task priority"
    )
    due_date: date | None = Field(default=None, description="Due date")
    tags: list[str] = Field(default_factory=list, description="Tags for organization")

mcp = FastMCP("Task Manager")

@mcp.tool
async def create_task_interactive(ctx: Context) -> str:
    """Create a new task with interactive form"""
    
    # Request structured input from user
    result = await ctx.elicit(
        message="Please provide task details",
        response_type=TaskCreationForm
    )
    
    # Handle response
    if result.action == "accept":
        task_data = result.data
        
        # Create task in database
        task = service.create_task(
            title=task_data.title,
            description=task_data.description,
            priority=task_data.priority,
            due_date=task_data.due_date,
            tags=task_data.tags,
        )
        
        return f"✅ Created task #{task.id}: {task.title}"
        
    elif result.action == "decline":
        return "❌ Task creation declined - no changes made"
        
    else:  # cancel
        return "🚫 Task creation cancelled"
```

---

### Example 2: Bulk Import with Progress

```python
import asyncio

@mcp.tool
async def bulk_import_tasks(
    ctx: Context,
    file_path: str
) -> str:
    """Import multiple tasks from a file with progress reporting"""
    
    # Parse file
    tasks = parse_task_file(file_path)
    total = len(tasks)
    
    # Confirm before starting
    confirm = await ctx.elicit(
        f"Import {total} tasks from {file_path}?",
        response_type=bool
    )
    
    if confirm.action != "accept" or not confirm.data:
        return "❌ Import cancelled"
    
    # Import with progress
    imported = 0
    for i, task_data in enumerate(tasks):
        try:
            service.create_task(**task_data)
            imported += 1
            
            # Report progress every 10 tasks or at 100%
            if i % 10 == 0 or i == total - 1:
                await ctx.report_progress(
                    progress=i / total,
                    message=f"Imported {i + 1}/{total} tasks"
                )
                
        except Exception as e:
            await ctx.log_error(f"Failed to import task: {e}")
    
    return f"✅ Successfully imported {imported}/{total} tasks"
```

---

### Example 3: Task Update with Confirmation

```python
class TaskUpdateForm(BaseModel):
    title: str | None = None
    description: str | None = None
    priority: Literal["low", "medium", "high"] | None = None
    status: Literal["todo", "in_progress", "done"] | None = None

@mcp.tool
async def update_task_interactive(
    ctx: Context,
    task_id: int
) -> str:
    """Update a task with interactive form showing current values"""
    
    # Fetch current task
    task = service.get_task(task_id)
    if not task:
        return f"❌ Task #{task_id} not found"
    
    # Create form with current values as defaults
    current_values = TaskUpdateForm(
        title=task.title,
        description=task.description,
        priority=task.priority,
        status=task.status,
    )
    
    # Request updates
    result = await ctx.elicit(
        message=f"Update task #{task_id}: {task.title}",
        response_type=TaskUpdateForm,
        default=current_values
    )
    
    if result.action == "accept":
        updates = {k: v for k, v in result.data.dict().items() if v is not None}
        
        if not updates:
            return "ℹ️ No changes made"
        
        updated_task = service.update_task(task_id, **updates)
        return f"✅ Updated task #{task_id}: {', '.join(updates.keys())}"
    
    return "❌ Update cancelled"
```

---

## 10. Next Steps

### Immediate Actions (if approved)

1. **Create feature branch**: `git checkout -b feature/fastmcp-3.0`
2. **Update dependencies**:
   ```bash
   # In pyproject.toml
   dependencies = [
       "fastmcp>=3.0.0b1",
       "mcp>=1.23",
       # ... other deps
   ]
   ```
3. **Install and test**:
   ```bash
   pip install -e .
   pytest
   ```
4. **Update imports** in `mcp_server/server.py`
5. **Run integration tests** with Claude Desktop
6. **Document changes** in MCP-QUICKSTART.md

### Documentation Updates

- [ ] Update MCP-QUICKSTART.md with FastMCP 3.0 features
- [ ] Add User Elicitation examples
- [ ] Document new tool signatures
- [ ] Update troubleshooting section
- [ ] Add deployment options (HTTP)

### Testing Strategy

- [ ] Unit tests for new tools
- [ ] Integration tests with elicitation mocks
- [ ] Manual testing with Claude Desktop
- [ ] Performance benchmarks
- [ ] Edge case validation

---

## 11. Resources

### Official Documentation
- **FastMCP Homepage**: https://gofastmcp.com/
- **GitHub Repository**: https://github.com/jlowin/fastmcp (22.4k stars)
- **Installation**: `pip install fastmcp==3.0.0b1`
- **Full Documentation**: 500+ pages at https://gofastmcp.com/llms.txt

### Key Documentation Pages
- **User Elicitation**: https://gofastmcp.com/servers/elicitation.md
- **Background Tasks**: https://gofastmcp.com/servers/tasks.md
- **Authentication**: https://gofastmcp.com/servers/auth/
- **Middleware**: https://gofastmcp.com/servers/middleware.md
- **Sampling**: https://gofastmcp.com/servers/sampling.md
- **Transforms**: https://gofastmcp.com/servers/transforms/

### Community
- **Discord**: Active community support
- **GitHub Issues**: Responsive maintainers
- **Example Servers**: 50+ examples in repository

---

## 12. Conclusion

FastMCP 3.0 represents a **major leap forward** in MCP server development. The addition of **User Elicitation** provides exactly the form-based interaction you requested, while maintaining full Python compatibility.

**Key Benefits:**
- ✅ Solves MCP Apps requirement without TypeScript
- ✅ Production-ready (70% market share)
- ✅ No breaking changes to core patterns
- ✅ 100+ new features for future growth
- ✅ Active development and community

**Recommended Action:** **Proceed with upgrade**

The migration path is clear, the risks are manageable, and the benefits are substantial. User Elicitation alone justifies the upgrade, and the additional features (background tasks, middleware, HTTP deployment) provide a solid foundation for future enhancements.

**Next Decision Point:** Should we upgrade before or after Phase 4?

---

## Appendix A: Full Feature List

### Core Features (Already Using)
- ✅ Tools (@tool decorator)
- ✅ Resources (@resource decorator)
- ✅ Prompts (@prompt decorator)
- ✅ Context injection
- ✅ Stdio transport

### New in 3.0 (Not Using Yet)
- **User Interaction**: Elicitation, progress, logging
- **Authentication**: OAuth 2.1, JWT, Bearer tokens
- **Authorization**: Eunomia, Permit.io integration
- **Middleware**: Logging, caching, rate limiting
- **Background Tasks**: Progress reporting, cancellation
- **Sampling**: LLM completions (client/server)
- **Transforms**: Namespace, visibility, versioning
- **Providers**: Filesystem, proxy, skills
- **HTTP Transport**: Streamable, stateful/stateless
- **Configuration**: Declarative JSON
- **Deployment**: Cloud-ready, containerizable

---

**End of Report**

*This report provides a comprehensive analysis of FastMCP 3.0 beta. The decision to proceed should consider project priorities, timeline, and risk tolerance. All technical information is accurate as of January 2025 based on official FastMCP documentation.*
