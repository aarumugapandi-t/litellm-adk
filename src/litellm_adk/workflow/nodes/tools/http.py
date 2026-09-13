"""HTTP Request Tool Node for Agent attachment and API calling."""

import json
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional
from ..base import NodeContext, NodeDefinition, NodeResult
from ...expressions import evaluate_template
from ...state import ExecutionStatus
from ....tools.base import Tool
from ....tools.permissions import ToolPermission


def perform_http_request(url: str, method: str = "GET", headers: Optional[Dict[str, str]] = None, body: Optional[str] = None) -> str:
    """Makes an HTTP request and returns the response body as text."""
    if not url or not url.strip():
        return "Error: Empty URL provided."
    try:
        data = body.encode("utf-8") if body else None
        req = urllib.request.Request(
            url.strip(),
            data=data,
            headers=headers or {"User-Agent": "LiteLLM-ADK/1.0"},
            method=method.upper()
        )
        with urllib.request.urlopen(req, timeout=10.0) as response:
            return response.read().decode("utf-8", errors="ignore")[:4000]
    except Exception as e:
        return f"HTTP Request Failed: {str(e)}"


class HTTPToolNode:
    """Provides REST / HTTP request capability to Agents or executes a request directly."""

    @property
    def definition(self) -> NodeDefinition:
        return NodeDefinition(
            type="http_tool",
            name="HTTP Request",
            description="Equips AI agents with external HTTP / REST API calling capabilities.",
            category="Tools",
            icon="globe",
            inputs=["input"],
            outputs=["tool", "output"],
            config_schema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "API endpoint URL (e.g. https://api.github.com/zen)",
                        "default": ""
                    },
                    "method": {
                        "type": "string",
                        "enum": ["GET", "POST", "PUT", "DELETE"],
                        "default": "GET"
                    }
                }
            }
        )

    async def execute(self, context: NodeContext) -> NodeResult:
        cfg = context.node_config
        target_url = cfg.get("url", "")
        method = cfg.get("method", "GET")

        tool_obj = Tool(
            func=perform_http_request,
            name="http_request",
            description="Sends an HTTP request to an external API or URL and returns the response.",
            permissions={ToolPermission.READ, ToolPermission.EXTERNAL},
            timeout=10.0,
        )

        direct_output = None
        if target_url:
            eval_ctx: Dict[str, Any] = {
                "trigger": context.trigger_data,
                "variables": context.variables,
                "inputs": context.inputs,
                "execution": {"id": context.execution_id},
            }
            eval_ctx.update(context.inputs)
            rendered_url = str(evaluate_template(target_url, eval_ctx)).strip()
            if rendered_url:
                direct_output = perform_http_request(rendered_url, method=method)

        return NodeResult(
            output=tool_obj if direct_output is None else direct_output,
            status=ExecutionStatus.COMPLETED,
            metadata={
                "tool": tool_obj,
                "tool_name": "http_request",
                "direct_output": direct_output
            }
        )
