"""Calculator Tool Node for Agent attachment and direct mathematical computation."""

from typing import Any, Dict
from ..base import NodeContext, NodeDefinition, NodeResult
from ...expressions import evaluate_template
from ...state import ExecutionStatus
from ....tools.builtin.calculator import create_calculator_tool, calculate


class CalculatorToolNode:
    """Provides safe math calculation capabilities to Agents or evaluates expressions in pipeline."""

    @property
    def definition(self) -> NodeDefinition:
        return NodeDefinition(
            type="calculator_tool",
            name="Calculator",
            description="Equips AI agents with safe mathematical evaluation, or computes formulas directly.",
            category="Tools",
            icon="binary",
            inputs=["input"],
            outputs=["tool", "output"],
            config_schema={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Math expression (e.g. 15 * 4 + sqrt(144))",
                        "default": "{{ trigger.expression }}"
                    }
                }
            }
        )

    async def execute(self, context: NodeContext) -> NodeResult:
        cfg = context.node_config
        tool_obj = create_calculator_tool()

        eval_ctx: Dict[str, Any] = {
            "trigger": context.trigger_data,
            "variables": context.variables,
            "inputs": context.inputs,
            "execution": {"id": context.execution_id},
        }
        eval_ctx.update(context.inputs)

        raw_expr = cfg.get("expression", "")
        direct_output = None
        if raw_expr:
            rendered = str(evaluate_template(raw_expr, eval_ctx)).strip()
            if rendered and rendered != "{{ trigger.expression }}":
                try:
                    direct_output = calculate(rendered)
                except Exception:
                    pass

        # If not evaluated from template, try calculating directly from upstream input
        if direct_output is None and context.inputs:
            upstream_in = context.inputs.get("input") or context.inputs.get("expression")
            if upstream_in and isinstance(upstream_in, (str, int, float)):
                try:
                    direct_output = calculate(str(upstream_in).strip())
                except Exception:
                    pass

        return NodeResult(
            output=tool_obj if direct_output is None else direct_output,
            status=ExecutionStatus.COMPLETED,
            metadata={
                "tool": tool_obj,
                "tool_name": "calculator",
                "direct_output": direct_output
            }
        )
