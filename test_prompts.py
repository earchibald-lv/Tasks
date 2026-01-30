#!/usr/bin/env python3
"""Test FastMCP prompt capabilities"""

from fastmcp import FastMCP

mcp = FastMCP("test")

# Check if prompt decorator exists
if hasattr(mcp, 'prompt'):
    print("✓ FastMCP has prompt decorator")
    
    # Try to create a simple prompt
    @mcp.prompt()
    def create_task_prompt(task_type: str = "feature") -> str:
        """Template for creating a new task
        
        Args:
            task_type: Type of task (feature, bug, docs)
        """
        return f"""Please help me create a new {task_type} task.

I need to:
1. Define a clear, actionable title
2. Write a detailed description
3. Set appropriate priority based on urgency
4. Optionally link to JIRA issues

Let's create this task together!"""
    
    print("✓ Created test prompt")
    print(f"  Prompt name: create_task_prompt")
    print(f"  Arguments: task_type (default: 'feature')")
    
else:
    print("✗ FastMCP does not have prompt decorator")
    print("  Available methods:")
    for attr in sorted(dir(mcp)):
        if not attr.startswith('_') and callable(getattr(mcp, attr)):
            print(f"    - {attr}")
