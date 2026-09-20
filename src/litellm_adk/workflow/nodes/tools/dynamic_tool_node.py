"""Dynamic Tool Node for LLM-generated skills and safe sandboxed execution."""

from typing import Any, Dict
from ..base import NodeContext, NodeDefinition, NodeResult
from ...state import ExecutionStatus
from ....tools.dynamic_tool import DynamicToolSpec, SafeCodeSandbox, create_dynamic_tool_instance


class DynamicToolNode:
    """Executes or provides custom LLM-generated dynamic tools to AI Agents."""

    @property
    def definition(self) -> NodeDefinition:
        return NodeDefinition(
            type="dynamic_tool",
            name="Dynamic Tool",
            description="Executes a dynamically synthesized Python tool or equips it to AI Agents.",
            category="Tools",
            icon="zap",
            inputs=["input"],
            outputs=["tool", "output"],
            config_schema={
                "type": "object",
                "properties": {
                    "tool_name": {
                        "type": "string",
                        "description": "Unique identifier for the dynamic tool",
                        "default": "custom_processor",
                    },
                    "description": {
                        "type": "string",
                        "description": "Functional description telling the LLM when to call this tool",
                        "default": "Performs custom data transformation or API querying.",
                    },
                    "code": {
                        "type": "string",
                        "description": "Python source code implementing run(**kwargs)",
                        "default": "def run(**kwargs):\n    return {'status': 'success', 'data': kwargs}",
                    },
                    "parameters": {
                        "type": "object",
                        "description": "JSON schema for tool input arguments",
                        "default": {},
                    },
                    "timeout_seconds": {
                        "type": "number",
                        "description": "Execution timeout in seconds",
                        "default": 10.0,
                    },
                    "approval_required": {
                        "type": "boolean",
                        "description": "Whether tool invocation requires human sign-off",
                        "default": False,
                    },
                },
                "required": ["tool_name", "code"],
            },
        )

    async def execute(self, context: NodeContext) -> NodeResult:
        cfg = context.node_config
        tool_name = cfg.get("tool_name") or cfg.get("name") or "dynamic_tool"
        code = cfg.get("code") or "def run(**kwargs):\n    return kwargs"
        description = cfg.get("description") or "Dynamic synthesized tool"
        params = cfg.get("parameters") or {}
        timeout = float(cfg.get("timeout_seconds") or 10.0)
        approval_required = bool(cfg.get("approval_required", False))

        spec = DynamicToolSpec(
            name=tool_name,
            description=description,
            code=code,
            parameters=params,
            timeout_seconds=timeout,
            approval_required=approval_required,
        )

        tool_obj = create_dynamic_tool_instance(spec)

        # If invoked in a linear data pipeline (input connected), execute directly
        direct_output = None
        if context.inputs:
            test_args = context.inputs.get("input")
            if isinstance(test_args, dict):
                sandbox_res = await SafeCodeSandbox.execute(
                    code=code,
                    arguments=test_args,
                    timeout_seconds=timeout,
                )
                if sandbox_res.success:
                    direct_output = sandbox_res.output

        return NodeResult(
            output=tool_obj if direct_output is None else direct_output,
            status=ExecutionStatus.COMPLETED,
            metadata={
                "tool": tool_obj,
                "tool_spec": spec.model_dump(),
                "tool_name": tool_name,
                "dynamic": True,
                "direct_output": direct_output,
            },
        )
