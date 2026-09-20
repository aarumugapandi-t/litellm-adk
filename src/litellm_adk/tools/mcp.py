"""Model Context Protocol (MCP) tool adapter for LiteLLM ADK Agents.

Enables Agents to mount and invoke tools from external Model Context Protocol (MCP) servers
(e.g., Zapier, Jira, Linear, GitHub, DeepWiki, ScrapeGraph AI) using standard OpenAI function calling.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from typing import Any, Callable, Dict, List, Optional, Union

import httpx

from .base import Tool
from .permissions import ToolPermission

logger = logging.getLogger(__name__)


def normalize_mcp_schema(input_schema: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Normalizes an MCP tool input schema to compliant OpenAPI/JSONSchema format for LLMs."""
    if not input_schema or not isinstance(input_schema, dict):
        return {"type": "object", "properties": {}, "additionalProperties": False}

    schema = dict(input_schema)
    if "type" not in schema:
        schema["type"] = "object"
    if "properties" not in schema:
        schema["properties"] = {}
    return schema


class MCPTool(Tool):
    """Tool wrapper representing an operation exposed by an external MCP server."""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        endpoint_url: Optional[str] = None,
        call_handler: Optional[Callable[..., Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 30.0,
    ):
        self.endpoint_url = endpoint_url
        self.custom_handler = call_handler
        self.headers = headers or {}
        self.timeout = timeout

        normalized_params = normalize_mcp_schema(parameters)

        async def _mcp_caller(**kwargs: Any) -> Any:
            if self.custom_handler is not None:
                if inspect.iscoroutinefunction(self.custom_handler):
                    return await self.custom_handler(**kwargs)
                return self.custom_handler(**kwargs)

            if not self.endpoint_url:
                raise ValueError(f"No endpoint URL or call handler configured for MCP tool '{name}'")

            # Execute HTTP/SSE call to MCP server
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                payload = {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": name,
                        "arguments": kwargs,
                    },
                    "id": 1,
                }
                resp = await client.post(self.endpoint_url, json=payload, headers=self.headers)
                resp.raise_for_status()
                data = resp.json()
                if "result" in data:
                    return data["result"]
                elif "error" in data:
                    raise RuntimeError(f"MCP Server Error: {data['error']}")
                return data

        super().__init__(
            func=_mcp_caller,
            name=name,
            description=description,
            parameters=normalized_params,
            permissions={ToolPermission.READ, ToolPermission.EXTERNAL},
            timeout=timeout,
        )


def create_mcp_tool(
    name: str,
    description: str,
    parameters: Optional[Dict[str, Any]] = None,
    call_handler: Optional[Callable[..., Any]] = None,
    endpoint_url: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 30.0,
) -> MCPTool:
    """Factory function creating an MCP Tool instance."""
    return MCPTool(
        name=name,
        description=description,
        parameters=parameters or {},
        endpoint_url=endpoint_url,
        call_handler=call_handler,
        headers=headers,
        timeout=timeout,
    )


async def discover_mcp_tools(
    endpoint_url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 15.0,
) -> List[MCPTool]:
    """Queries an MCP server endpoint for its tool definitions and returns Tool instances."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": {},
            "id": 1,
        }
        resp = await client.post(endpoint_url, json=payload, headers=headers or {})
        resp.raise_for_status()
        data = resp.json()

        tools_list = data.get("result", {}).get("tools", [])
        mcp_tools: List[MCPTool] = []
        for t in tools_list:
            tool_obj = MCPTool(
                name=t.get("name", "unnamed_mcp_tool"),
                description=t.get("description", ""),
                parameters=t.get("inputSchema", {}),
                endpoint_url=endpoint_url,
                headers=headers,
                timeout=timeout,
            )
            mcp_tools.append(tool_obj)
        return mcp_tools


import abc
from typing import Literal
from pydantic import BaseModel, Field


class BaseMCPClient(abc.ABC):
    """Abstract base class for Model Context Protocol (MCP) clients."""

    def __init__(self) -> None:
        self._session: Any = None
        self._exit_stack: Any = None

    @property
    def is_connected(self) -> bool:
        """Returns True if the MCP client is actively connected and initialized."""
        return self._session is not None

    async def __aenter__(self) -> "BaseMCPClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    @abc.abstractmethod
    async def connect(self) -> None:
        """Establishes connection to the MCP server and initializes session."""
        raise NotImplementedError

    async def list_tools(self) -> List[Dict[str, Any]]:
        """Lists raw tool specifications from the connected MCP server."""
        if not self._session:
            raise RuntimeError("MCP Client is not connected. Call 'await connect()' or use 'async with' context.")
        tools_result = await self._session.list_tools()
        return [
            {
                "name": t.name,
                "description": t.description or "",
                "inputSchema": getattr(t, "inputSchema", {}) or {},
            }
            for t in tools_result.tools
        ]

    async def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        """Executes a tool on the MCP server and parses returned content."""
        if not self._session:
            raise RuntimeError("MCP Client is not connected. Call 'await connect()' or use 'async with' context.")

        result = await self._session.call_tool(name, arguments or {})

        if getattr(result, "isError", False):
            err_texts = [getattr(c, "text", str(c)) for c in getattr(result, "content", [])]
            return f"Error executing tool '{name}': {' '.join(err_texts)}"

        content = getattr(result, "content", [])
        if not content:
            return ""
        if len(content) == 1 and hasattr(content[0], "text"):
            return content[0].text

        extracted = []
        for item in content:
            if hasattr(item, "text"):
                extracted.append(item.text)
            elif hasattr(item, "data"):
                extracted.append(f"[{getattr(item, 'type', 'media')} data]")
            else:
                extracted.append(str(item))
        return "\n".join(extracted)

    async def get_tools(self) -> List[MCPTool]:
        """Discovers all tools exposed by the MCP server and wraps them into LiteLLM ADK MCPTools."""
        tools_info = await self.list_tools()
        mcp_tools: List[MCPTool] = []
        for t in tools_info:
            tool_name = t["name"]
            tool_desc = t["description"]
            tool_params = t["inputSchema"]

            def _bind_caller(name: str):
                async def _caller(**kwargs: Any) -> Any:
                    return await self.call_tool(name, kwargs)
                return _caller

            mcp_tool = MCPTool(
                name=tool_name,
                description=tool_desc,
                parameters=tool_params,
                call_handler=_bind_caller(tool_name),
            )
            mcp_tools.append(mcp_tool)
        return mcp_tools

    async def close(self) -> None:
        """Gracefully terminates connection and releases underlying resources."""
        if self._exit_stack:
            try:
                await self._exit_stack.aclose()
            except BaseException as err:
                err_msg = str(err)
                if "cancel scope" in err_msg or "TaskGroup" in err_msg:
                    logger.debug("MCP client transport terminated cleanly: %s", err_msg)
                else:
                    logger.warning("Notice during MCP client close: %s", err_msg)
            finally:
                self._exit_stack = None
                self._session = None



class StdioMCPClient(BaseMCPClient):
    """Manages an active connection to an external MCP server over standard I/O (stdio)."""

    def __init__(
        self,
        command: str,
        args: Optional[List[str]] = None,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ):
        super().__init__()
        self.command = command
        self.args = args or []
        self.cwd = cwd
        self.env = env

    async def connect(self) -> None:
        """Establishes stdio communication with the external MCP server subprocess."""
        from contextlib import AsyncExitStack

        self._exit_stack = AsyncExitStack()
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client

            server_params = StdioServerParameters(
                command=self.command,
                args=self.args,
                cwd=self.cwd,
                env=self.env,
            )
            read_stream, write_stream = await self._exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            session = await self._exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await session.initialize()
            self._session = session
            logger.info("Connected to Stdio MCP server (%s %s)", self.command, " ".join(self.args))
        except Exception as e:
            if self._exit_stack:
                await self._exit_stack.aclose()
            raise RuntimeError(f"Failed to connect to MCP stdio server '{self.command}': {e}") from e


class SSEMCPClient(BaseMCPClient):
    """Manages an active connection to an external MCP server over Server-Sent Events (SSE)."""

    def __init__(
        self,
        url: str,
        headers: Optional[Dict[str, Any]] = None,
        timeout: float = 15.0,
        sse_read_timeout: float = 300.0,
        auth: Optional[Any] = None,
    ):
        super().__init__()
        self.url = url
        self.headers = headers or {}
        self.timeout = timeout
        self.sse_read_timeout = sse_read_timeout
        self.auth = auth

    async def connect(self) -> None:
        """Establishes an SSE event stream and JSON-RPC session with the remote MCP server."""
        from contextlib import AsyncExitStack

        self._exit_stack = AsyncExitStack()
        try:
            from mcp import ClientSession
            from mcp.client.sse import sse_client

            read_stream, write_stream = await self._exit_stack.enter_async_context(
                sse_client(
                    url=self.url,
                    headers=self.headers,
                    timeout=self.timeout,
                    sse_read_timeout=self.sse_read_timeout,
                    auth=self.auth,
                )
            )
            session = await self._exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await session.initialize()
            self._session = session
            logger.info("Connected to SSE MCP server at %s", self.url)
        except Exception as e:
            if self._exit_stack:
                await self._exit_stack.aclose()
            raise RuntimeError(f"Failed to connect to MCP SSE server '{self.url}': {e}") from e


class MCPServerConfig(BaseModel):
    """Declarative configuration model for an external Model Context Protocol (MCP) server."""

    transport: Literal["stdio", "sse", "http"] = Field(
        default="stdio",
        description="Transport protocol for MCP communication: 'stdio', 'sse', or 'http'.",
    )
    name: Optional[str] = Field(default=None, description="Optional logical name for this server.")

    # Stdio transport options
    command: Optional[str] = Field(default=None, description="Executable command for stdio server.")
    args: List[str] = Field(default_factory=list, description="CLI arguments for stdio server command.")
    cwd: Optional[str] = Field(default=None, description="Working directory for stdio subprocess.")
    env: Optional[Dict[str, str]] = Field(default=None, description="Environment variables for subprocess.")

    # SSE / HTTP transport options
    url: Optional[str] = Field(default=None, description="Endpoint URL for SSE or HTTP MCP server.")
    headers: Optional[Dict[str, str]] = Field(default=None, description="HTTP request headers.")
    timeout: float = Field(default=30.0, description="Network timeout in seconds.")
    sse_read_timeout: float = Field(default=300.0, description="Read timeout for SSE event stream in seconds.")

    # Authentication options
    api_key: Optional[str] = Field(default=None, description="API key or token for authenticating with the MCP server.")
    token: Optional[str] = Field(default=None, description="Bearer token alias for authenticating with the MCP server.")
    auth_type: Literal["bearer", "api_key", "basic", "custom"] = Field(
        default="bearer",
        description="Authentication mechanism: 'bearer', 'api_key', 'basic', or 'custom'.",
    )
    auth_header_name: Optional[str] = Field(
        default=None,
        description="Custom header name for 'api_key' auth (defaults to 'X-API-Key').",
    )
    username: Optional[str] = Field(default=None, description="Username for HTTP Basic authentication.")
    password: Optional[str] = Field(default=None, description="Password for HTTP Basic authentication.")
    auth: Optional[Any] = Field(default=None, description="Custom httpx.Auth handler instance for SSE client.")


def create_mcp_client(server_config: Union[str, Dict[str, Any], MCPServerConfig]) -> BaseMCPClient:
    """Factory function instantiating the appropriate MCP client transport from configuration."""
    import os

    if isinstance(server_config, str):
        if server_config.startswith("http://") or server_config.startswith("https://"):
            return SSEMCPClient(url=server_config)
        parts = server_config.split()
        return StdioMCPClient(command=parts[0], args=parts[1:] if len(parts) > 1 else [])

    if isinstance(server_config, MCPServerConfig):
        cfg = server_config.model_dump(exclude_none=True)
    elif isinstance(server_config, dict):
        cfg = dict(server_config)
    else:
        raise TypeError(f"Unsupported MCP server configuration type: {type(server_config)}")

    transport = cfg.get("transport")
    url = cfg.get("url") or cfg.get("sse_url") or cfg.get("http_url")
    command = cfg.get("command")

    # Auto-detect transport if not explicitly set
    if not transport:
        if url and ("/sse" in url or not command):
            transport = "sse"
        elif command:
            transport = "stdio"
        else:
            transport = "stdio"

    token = cfg.get("token") or cfg.get("api_key")
    auth_type = cfg.get("auth_type", "bearer")
    auth_obj = cfg.get("auth")

    if transport == "sse":
        if not url:
            raise ValueError("URL must be specified for SSE MCP transport.")

        headers = dict(cfg.get("headers") or {})
        headers_lower = {k.lower(): k for k in headers}

        # Auto-inject Bearer token or API key if not manually provided in headers
        if token and "authorization" not in headers_lower:
            if auth_type == "bearer":
                headers["Authorization"] = f"Bearer {token}"
            elif auth_type == "api_key":
                h_name = cfg.get("auth_header_name") or "X-API-Key"
                headers[h_name] = token

        # Auto-inject Basic Auth if username/password specified
        if auth_type == "basic" and (cfg.get("username") or cfg.get("password")) and "authorization" not in headers_lower:
            import base64
            user = cfg.get("username", "")
            pwd = cfg.get("password", "")
            creds = base64.b64encode(f"{user}:{pwd}".encode("utf-8")).decode("utf-8")
            headers["Authorization"] = f"Basic {creds}"

        return SSEMCPClient(
            url=url,
            headers=headers,
            timeout=float(cfg.get("timeout", 15.0)),
            sse_read_timeout=float(cfg.get("sse_read_timeout", 300.0)),
            auth=auth_obj,
        )

    # Default to Stdio transport
    if not command:
        raise ValueError("Executable 'command' must be specified for Stdio MCP transport.")

    merged_env = dict(os.environ)
    if cfg.get("env"):
        merged_env.update(cfg["env"])
    if token:
        merged_env.setdefault("MCP_API_KEY", token)
        merged_env.setdefault("API_KEY", token)

    return StdioMCPClient(
        command=command,
        args=cfg.get("args") or [],
        cwd=cfg.get("cwd"),
        env=merged_env,
    )



async def discover_stdio_mcp_tools(
    command: str,
    args: Optional[List[str]] = None,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
) -> tuple[List[MCPTool], StdioMCPClient]:
    """Helper to start an MCP server process, establish stdio session, and discover tools."""
    client = StdioMCPClient(command=command, args=args, cwd=cwd, env=env)
    await client.connect()
    tools = await client.get_tools()
    return tools, client


async def discover_sse_mcp_tools(
    url: str,
    headers: Optional[Dict[str, Any]] = None,
    timeout: float = 15.0,
    sse_read_timeout: float = 300.0,
) -> tuple[List[MCPTool], SSEMCPClient]:
    """Helper to connect to a remote SSE MCP server and discover its tools."""
    client = SSEMCPClient(
        url=url,
        headers=headers,
        timeout=timeout,
        sse_read_timeout=sse_read_timeout,
    )
    await client.connect()
    tools = await client.get_tools()
    return tools, client


