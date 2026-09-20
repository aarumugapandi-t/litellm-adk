"""GitHub Model Context Protocol (MCP) Integration Example.

Demonstrates connecting a LiteLLM ADK Agent directly to the official GitHub MCP server
(`@modelcontextprotocol/server-github`) using declarative agent configuration.

The agent gains access to GitHub operations, including:
- Searching repositories (`search_repositories`)
- Inspecting source code and file contents (`get_file_contents`)
- Listing and creating issues (`list_issues`, `create_issue`)
- Managing pull requests and commits (`create_pull_request`, `list_commits`)

Prerequisites:
1. Node.js (with `npx` available on PATH)
2. A GitHub Personal Access Token (classic with `repo` scope, or fine-grained token)
   Set via environment variable:
     $env:GITHUB_PERSONAL_ACCESS_TOKEN="ghp_your_token_here"  (PowerShell)
     export GITHUB_PERSONAL_ACCESS_TOKEN="ghp_your_token_here" (Bash)

Run:
    python examples/github_mcp_agent.py
"""

import asyncio
import os
import sys
from typing import Optional

from litellm_adk import Agent


async def run_github_mcp_agent(
    repo_query: str = "Search for popular Python repositories related to 'litellm' and summarize the top 3 with their stars and descriptions.",
    token: Optional[str] = None,
) -> None:
    """Instantiates and executes a GitHub MCP-enabled research and automation agent."""
    github_pat = token or os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN") or os.getenv("GITHUB_TOKEN") or "kshdfkhk"

    print("=" * 75)
    print("LiteLLM ADK - GitHub Model Context Protocol (MCP) Agent")
    print("=" * 75)

    if not github_pat:
        print("[WARNING] No GITHUB_PERSONAL_ACCESS_TOKEN found in environment!")
        print("\nTo run with real GitHub API access:")
        print("  1. Create a GitHub Personal Access Token at: https://github.com/settings/tokens")
        print("     (Scopes needed: 'repo' for private repos, or read-only for public exploration)")
        print("  2. Set the environment variable:")
        print("     $env:GITHUB_PERSONAL_ACCESS_TOKEN=\"ghp_your_token_here\"  # Windows PowerShell")
        print("     export GITHUB_PERSONAL_ACCESS_TOKEN=\"ghp_your_token_here\" # Linux/macOS")
        print("-" * 75)
        print("Exiting demo setup. Please set your token and re-run.")
        return

    # 1. Configure the Agent with the official GitHub MCP server
    # The ADK automatically runs 'npx -y @modelcontextprotocol/server-github',
    # performs the JSON-RPC handshake, discovers all tools, and maps their schemas.
    agent = Agent(
        name="github_agent",
        model="command-a-03-2025",  # or "claude-3-5-sonnet", "ollama/llama3", etc.
        base_url="http://localhost:9000/v1",  # Replace with your actual base URL
        api_key="sk-1234",  # Replace with your actual
        system_prompt=(
            "You are an expert GitHub DevOps and software engineering assistant. "
            "You have direct access to GitHub tools via the Model Context Protocol (MCP). "
            "Use the provided tools to search repositories, inspect file contents, "
            "and query issues or pull requests. Always ground your answers with accurate data."
        ),
        mcp_servers=[
            # Stdio transport spawning the official GitHub MCP server via npx
            {
                "transport": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-github"],
                # "env": {
                #     "GITHUB_PERSONAL_ACCESS_TOKEN": github_pat,
                # },
            },
            # If using a remote hosted SSE GitHub MCP server, simply use:
            # {
            #     "transport": "sse",
            #     "url": "https://mcp-github.internal.net/sse",
            #     "token": github_pat,
            # },
        ],
    )

    print("Starting GitHub MCP Agent and discovering tools...")

    # 2. Use async context manager for clean process and connection lifecycle
    try:
        async with agent:
            print(f"\nDiscovered {len(agent.tools)} GitHub MCP tool(s):")
            for t in agent.tools:
                fn = t.get("function", {})
                name = fn.get("name", "")
                desc = fn.get("description", "").split("\n")[0][:70]
                print(f"  • {name:<28} : {desc}...")
            print("-" * 75)

            # 3. Invoke the agent with a user prompt
            print(f"User Query:\n  {repo_query}\n")
            print("Running agent reasoning loop with GitHub grounding...")

            result = await agent.ainvoke(repo_query)

            print("\nAgent Response:")
            print("=" * 75)
            print(result.text)
            print("=" * 75)

            # 4. Inspect executed tool calls
            if result.tool_calls:
                print(f"\nExecuted Tool Calls ({len(result.tool_calls)}):")
                for call in result.tool_calls:
                    print(f"  - Tool: {call.tool_name}")
                    print(f"    Arguments: {call.arguments}")
                    preview = str(call.result).replace("\n", " ")[:160]
                    print(f"    Output Preview: {preview}...")

            print(f"\nExecution stats: {result.duration:.2f}s, {result.usage.total_tokens} tokens")

    except Exception as exc:
        print(f"\nExecution encountered an error: {exc}")
    finally:
        await agent.aclose()


if __name__ == "__main__":
    asyncio.run(run_github_mcp_agent())
