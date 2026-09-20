"""Model Context Protocol (MCP) Integration Example.

Demonstrates connecting a LiteLLM ADK Agent to an external Model Context Protocol (MCP)
server communicating over standard I/O (stdio) transport, dynamically discovering its tools
(e.g., web search, content extraction, and browser automation), and invoking them in an agent loop.

Supported transports:
- Stdio Transport (e.g., `node dist/index.js`, `npm run start`, or CLI executables)
- HTTP/SSE Transport (e.g., remote microservices and endpoints)

Run:
    python examples/mcp_agent.py
"""

import asyncio
import os
from typing import Optional

from litellm_adk import Agent, StdioMCPClient, discover_stdio_mcp_tools


async def run_mcp_search_agent(
    server_cwd: Optional[str] = None,
    server_script: Optional[str] = None,
    user_query: str = "https://pypi.org/project/litellm-adk/ Who are the maintainers of this project.",
) -> None:
    """Connects to a stdio MCP server, discovers its tools, and runs an Agent with those tools.

    Args:
        server_cwd: Directory containing the MCP server (e.g., D:/KiBO/mcp/web-search-mcp).
        server_script: Path to the server entrypoint (e.g., dist/index.js).
        user_query: The user prompt to execute with the agent.
    """

        # 4. Instantiate the Agent equipped with MCP tools
        # Using LiteLLM configured model or local proxy
    agent = Agent(
        name="web_search_agent",
        model="command-a-03-2025",  # or "claude-3-5-sonnet", "ollama/llama3", etc.
        base_url="http://localhost:9000/v1",  # Replace with your actual base URL
        api_key="sk-1234",  # Replace with your actual
        system_prompt=(
            "You are an expert research agent with access to web search and content extraction "
            "tools exposed via the Model Context Protocol (MCP). When the user asks a question "
            "requiring fresh or external information, select and call the appropriate search tool "
            "to ground your answer with accurate and up-to-date facts."
        ),
        mcp_servers=[
            # 1. Local Stdio MCP Server (web-search-mcp)
            {
                "transport": "stdio",
                "command": "node",
                "args": [r"dist\index.js"],
                "cwd": r"D:\KiBO\mcp\web-search-mcp",
            },
            # 2. Remote SSE MCP Server (if applicable)
            # {
            #     "transport": "sse",
            #     "url": "https://mcp.company.internal/sse",
            #     "headers": {"Authorization": "Bearer your_token"},
            # },
        ],
    )

    print(f"\nUser Query: {user_query}\n")
    print("Running agent reasoning loop with MCP tool grounding...")

    # 2. Execute the Agent within an async context manager for automatic lifecycle cleanup
    try:
        async with agent:
            result = await agent.ainvoke(user_query)

            print("\nAgent Response:")
            print(result.text)

            # 3. Inspect executed MCP tool calls
            if result.tool_calls:
                print("\nExecuted MCP Tool Calls:")
                for call in result.tool_calls:
                    print(f"  - Tool: {call.tool_name}")
                    print(f"    Arguments: {call.arguments}")
                    result_preview = str(call.result)[:200]
                    print(f"    Result Preview: {result_preview}...")

            print(f"\nExecution stats: {result.duration:.2f}s, {result.usage.total_tokens} tokens")

    except Exception as exc:
        print(f"\nAgent execution encountered an error: {exc}")
        print("\nNote: Make sure your LLM API key (e.g., OPENAI_API_KEY or LITELLM_API_KEY) is configured.")
    finally:
        await agent.aclose()



if __name__ == "__main__":
    asyncio.run(run_mcp_search_agent())
