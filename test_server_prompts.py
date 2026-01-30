#!/usr/bin/env python3
"""Test script to verify MCP server prompts are registered."""

import sys
import asyncio
sys.path.insert(0, '.')

from mcp_server.server import mcp


async def main():
    """Test prompts registration."""
    print("=" * 60)
    print("MCP Server Prompts Test")
    print("=" * 60)
    
    # List all prompts
    print("\n1. Listing prompts...")
    try:
        prompts = await mcp.list_prompts()
        print(f"   Found {len(prompts)} prompts:")
        for prompt in prompts:
            print(f"   - {prompt.name}: {prompt.description}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test getting a specific prompt
    print("\n2. Testing newTask prompt...")
    try:
        prompt_result = await mcp.render_prompt("newTask")
        print(f"   Success! Prompt returned {len(prompt_result.messages)} message(s)")
        if prompt_result.messages:
            msg = prompt_result.messages[0]
            print(f"   Role: {msg.role}")
            print(f"   Content preview: {msg.content.text[:100]}...")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test with arguments
    print("\n3. Testing newTask with task_type='bug'...")
    try:
        prompt_result = await mcp.render_prompt("newTask", {"task_type": "bug"})
        if prompt_result.messages:
            msg = prompt_result.messages[0]
            print(f"   Content includes 'bug': {'bug' in msg.content.text.lower()}")
            # Show a bit more to verify bug-specific content
            lines = msg.content.text.split('\n')
            print(f"   First line: {lines[0]}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
