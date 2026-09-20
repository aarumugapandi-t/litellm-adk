"""Unit tests for Model Context Protocol (MCP) Transports and Declarative Agent Mounting."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from litellm_adk import (
    Agent,
    AgentConfig,
    BaseMCPClient,
    MCPServerConfig,
    MCPTool,
    SSEMCPClient,
    StdioMCPClient,
    create_mcp_client,
)


def test_mcp_server_config_validation():
    """Validates declarative MCPServerConfig models for Stdio and SSE transports."""
    stdio_cfg = MCPServerConfig(
        transport="stdio",
        command="node",
        args=["dist/index.js"],
        cwd="/path/to/server",
    )
    assert stdio_cfg.transport == "stdio"
    assert stdio_cfg.command == "node"
    assert stdio_cfg.args == ["dist/index.js"]
    assert stdio_cfg.cwd == "/path/to/server"

    sse_cfg = MCPServerConfig(
        transport="sse",
        url="http://localhost:8000/sse",
        headers={"Authorization": "Bearer secret"},
        timeout=20.0,
    )
    assert sse_cfg.transport == "sse"
    assert sse_cfg.url == "http://localhost:8000/sse"
    assert sse_cfg.headers == {"Authorization": "Bearer secret"}
    assert sse_cfg.timeout == 20.0


def test_create_mcp_client_factory():
    """Verifies create_mcp_client correctly instantiates Stdio and SSE clients."""
    # 1. Stdio from dict
    client1 = create_mcp_client({
        "command": "node",
        "args": ["index.js"],
        "cwd": "/app",
    })
    assert isinstance(client1, StdioMCPClient)
    assert client1.command == "node"
    assert client1.args == ["index.js"]

    # 2. SSE from dict
    client2 = create_mcp_client({
        "transport": "sse",
        "url": "http://localhost:8000/sse",
    })
    assert isinstance(client2, SSEMCPClient)
    assert client2.url == "http://localhost:8000/sse"

    # 3. SSE from URL string
    client3 = create_mcp_client("https://example.com/api/sse")
    assert isinstance(client3, SSEMCPClient)
    assert client3.url == "https://example.com/api/sse"

    # 4. Stdio from command string
    client4 = create_mcp_client("python -m my_mcp_server")
    assert isinstance(client4, StdioMCPClient)
    assert client4.command == "python"
    assert client4.args == ["-m", "my_mcp_server"]

    # 5. From typed MCPServerConfig
    client5 = create_mcp_client(MCPServerConfig(
        transport="sse",
        url="http://127.0.0.1:3000/sse",
    ))
    assert isinstance(client5, SSEMCPClient)
    assert client5.url == "http://127.0.0.1:3000/sse"


@pytest.mark.asyncio
async def test_base_mcp_client_tool_lifecycle():
    """Tests tool listing, invocation, and wrapping on BaseMCPClient."""
    client = StdioMCPClient(command="dummy")

    # Mock internal session
    mock_session = AsyncMock()
    tool_mock = MagicMock()
    tool_mock.name = "web_search"
    tool_mock.description = "Perform internet search"
    tool_mock.inputSchema = {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    }
    mock_session.list_tools.return_value = MagicMock(tools=[tool_mock])

    # Mock tool call result
    content_mock = MagicMock()
    content_mock.text = "Search results: 1. Python 3.13 released."
    call_result_mock = MagicMock(isError=False, content=[content_mock])
    mock_session.call_tool.return_value = call_result_mock

    client._session = mock_session

    assert client.is_connected is True

    # 1. List tools
    tools_list = await client.list_tools()
    assert len(tools_list) == 1
    assert tools_list[0]["name"] == "web_search"

    # 2. Get wrapped tools
    wrapped_tools = await client.get_tools()
    assert len(wrapped_tools) == 1
    assert isinstance(wrapped_tools[0], MCPTool)
    assert wrapped_tools[0].name == "web_search"

    # 3. Call tool through handler
    output = await wrapped_tools[0].func(query="Python 3.13")
    assert "Search results: 1. Python 3.13 released." in output
    mock_session.call_tool.assert_awaited_with("web_search", {"query": "Python 3.13"})


@pytest.mark.asyncio
async def test_agent_declarative_mcp_servers():
    """Tests declarative mcp_servers configuration and automatic mounting in Agent."""
    mock_mcp_tool = MCPTool(
        name="weather_mcp",
        description="Fetch current weather",
        parameters={"type": "object", "properties": {"city": {"type": "string"}}},
        call_handler=AsyncMock(return_value="Sunny, 25C"),
    )

    mock_client = AsyncMock(spec=BaseMCPClient)
    mock_client.connect = AsyncMock()
    mock_client.get_tools = AsyncMock(return_value=[mock_mcp_tool])
    mock_client.close = AsyncMock()

    with patch("litellm_adk.agent.agent.create_mcp_client", return_value=mock_client):
        agent = Agent(
            name="researcher",
            model="gpt-4o",
            mcp_servers=[
                {
                    "command": "node",
                    "args": ["dist/index.js"],
                    "cwd": "/mock/path",
                }
            ],
        )

        assert agent.mcp_servers is not None
        assert len(agent.mcp_servers) == 1
        assert agent._mcp_initialized is False

        # Initialize MCP servers
        await agent.initialize_mcp_servers()
        assert agent._mcp_initialized is True
        mock_client.connect.assert_awaited_once()
        mock_client.get_tools.assert_awaited_once()

        # Verify tool is registered in agent registry and exposed in tools property
        tool_defs = agent.tools
        assert any(t["function"]["name"] == "weather_mcp" for t in tool_defs)

        # Verify close
        await agent.close_mcp_servers()
        assert agent._mcp_initialized is False
        mock_client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_agent_context_manager_mcp_lifecycle():
    """Tests async with Agent(...) automatically initializes and closes MCP servers."""
    mock_client = AsyncMock(spec=BaseMCPClient)
    mock_client.connect = AsyncMock()
    mock_client.get_tools = AsyncMock(return_value=[])
    mock_client.close = AsyncMock()

    with patch("litellm_adk.agent.agent.create_mcp_client", return_value=mock_client):
        agent = Agent(
            model="gpt-4o",
            mcp_servers=[{"transport": "sse", "url": "http://localhost:8000/sse"}],
        )

        async with agent as active_agent:
            assert active_agent._mcp_initialized is True
            mock_client.connect.assert_awaited_once()

        # After exiting context, close should be called
        mock_client.close.assert_awaited_once()
        assert agent._mcp_initialized is False


@pytest.mark.asyncio
async def test_agent_lazy_mcp_init_on_run():
    """Tests that Agent.run automatically initializes MCP servers if not already initialized."""
    mock_client = AsyncMock(spec=BaseMCPClient)
    mock_client.connect = AsyncMock()
    mock_client.get_tools = AsyncMock(return_value=[])
    mock_client.close = AsyncMock()

    with patch("litellm_adk.agent.agent.create_mcp_client", return_value=mock_client):
        agent = Agent(
            model="gpt-4o",
            mcp_servers=[{"command": "node", "args": ["server.js"]}],
        )

        assert agent._mcp_initialized is False

        # Mock the execution loop to avoid live LLM calls
        agent.loop.run = AsyncMock(return_value=MagicMock(text="Loop done", cost_usd=0.0, total_tokens=10))

        result = await agent.ainvoke("Test prompt")
        assert agent._mcp_initialized is True
        mock_client.connect.assert_awaited_once()
        mock_client.get_tools.assert_awaited_once()
        assert result.text == "Loop done"

        await agent.aclose()
        mock_client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_multiple_mcp_servers():
    """Tests Agent mounting multiple MCP servers simultaneously (e.g., Stdio and SSE)."""
    tool1 = MCPTool(name="stdio_tool", description="T1", parameters={}, call_handler=AsyncMock())
    tool2 = MCPTool(name="sse_tool", description="T2", parameters={}, call_handler=AsyncMock())

    client1 = AsyncMock(spec=BaseMCPClient)
    client1.connect = AsyncMock()
    client1.get_tools = AsyncMock(return_value=[tool1])
    client1.close = AsyncMock()

    client2 = AsyncMock(spec=BaseMCPClient)
    client2.connect = AsyncMock()
    client2.get_tools = AsyncMock(return_value=[tool2])
    client2.close = AsyncMock()

    def mock_factory(cfg):
        if isinstance(cfg, dict) and cfg.get("transport") == "sse":
            return client2
        return client1

    with patch("litellm_adk.agent.agent.create_mcp_client", side_effect=mock_factory):
        agent = Agent(
            model="gpt-4o",
            mcp_servers=[
                {"command": "node", "args": ["dist/index.js"]},
                {"transport": "sse", "url": "http://localhost:8000/sse"},
            ],
        )

        await agent.initialize_mcp_servers()
        assert len(agent._mcp_clients) == 2
        tool_names = [t["function"]["name"] for t in agent.tools]
        assert "stdio_tool" in tool_names
        assert "sse_tool" in tool_names

        await agent.aclose()
        client1.close.assert_awaited_once()
        client2.close.assert_awaited_once()


def test_mcp_authentication_modes():
    """Tests that create_mcp_client auto-injects Bearer, API Key, Basic Auth, and Stdio env vars."""
    import base64

    # 1. Bearer token auth for SSE
    c1 = create_mcp_client({
        "transport": "sse",
        "url": "https://api.example.com/sse",
        "token": "ghp_secret_token",
    })
    assert isinstance(c1, SSEMCPClient)
    assert c1.headers.get("Authorization") == "Bearer ghp_secret_token"

    # 2. API Key header auth for SSE
    c2 = create_mcp_client({
        "transport": "sse",
        "url": "https://api.example.com/sse",
        "auth_type": "api_key",
        "api_key": "sec_12345",
        "auth_header_name": "X-Custom-Key",
    })
    assert isinstance(c2, SSEMCPClient)
    assert c2.headers.get("X-Custom-Key") == "sec_12345"

    # 3. Basic Auth for SSE
    c3 = create_mcp_client({
        "transport": "sse",
        "url": "https://api.example.com/sse",
        "auth_type": "basic",
        "username": "admin",
        "password": "secretpassword",
    })
    assert isinstance(c3, SSEMCPClient)
    expected_basic = base64.b64encode(b"admin:secretpassword").decode("utf-8")
    assert c3.headers.get("Authorization") == f"Basic {expected_basic}"

    # 4. Stdio API key injection into subprocess environment
    c4 = create_mcp_client({
        "command": "node",
        "args": ["dist/index.js"],
        "api_key": "brave_search_key_999",
    })
    assert isinstance(c4, StdioMCPClient)
    assert c4.env.get("API_KEY") == "brave_search_key_999"
    assert c4.env.get("MCP_API_KEY") == "brave_search_key_999"
    assert "PATH" in c4.env  # Verified system environment is safely merged


