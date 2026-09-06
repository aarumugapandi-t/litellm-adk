"""Tool Node executing a single registered tool from the registry."""

from typing import Any, Dict
from .base import Node, NodeContext, NodeDefinition, NodeResult
from ..expressions import evaluate_template
from ..state import ExecutionStatus
from ...tools.registry import tool_registry
from ...tools.executor import ToolExecutor


class ToolNode:
    """Executes a discrete framework tool with evaluated arguments."""

    @property
    def definition(self) -> NodeDefinition:
        return NodeDefinition(
            type="tool",
            name="Tool Execution",
            description="Executes a specific tool registered in the framework tool registry.",
            category="Tools",
            icon="wrench",
            inputs=["input"],
            outputs=["output"],
            config_schema={
                "type": "object",
                "required": ["tool"],
                "properties": {
                    "tool": {
                        "type": "string",
                        "description": "Name of the registered tool to execute"
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Arguments passed to the tool (supports {{ expressions }})",
                        "default": {}
                    },
                    "timeout": {
                        "type": "number",
                        "description": "Execution timeout in seconds",
                        "default": 30.0
                    }
                }
            }
        )

    async def execute(self, context: NodeContext) -> NodeResult:
        cfg = context.node_config
        tool_name = cfg.get("tool")
        raw_params = cfg.get("parameters", {})
        timeout = float(cfg.get("timeout", 30.0))

        if not tool_name:
            return NodeResult(output=None, status=ExecutionStatus.FAILED, error="Tool name is required.")

        tool_obj = tool_registry.get_tool(tool_name)
        if not tool_obj:
            return NodeResult(output=None, status=ExecutionStatus.FAILED, error=f"Tool '{tool_name}' not found in registry.")

        eval_ctx: Dict[str, Any] = {
            "trigger": context.trigger_data,
            "variables": context.variables,
            "inputs": context.inputs,
            "execution": {"id": context.execution_id},
        }
        eval_ctx.update(context.inputs)

        resolved_params = evaluate_template(raw_params, eval_ctx)
        if not isinstance(resolved_params, dict):
            resolved_params = {}

        executor = ToolExecutor(registry=tool_registry, default_timeout=timeout)
        try:
            res = await executor.execute(
                name=tool_name,
                arguments=resolved_params,
                timeout=timeout,
            )
            return NodeResult(output=res, status=ExecutionStatus.COMPLETED)
        except Exception as e:
            return NodeResult(output=None, status=ExecutionStatus.FAILED, error=str(e))
