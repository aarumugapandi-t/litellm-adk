"""Transform Node providing safe schema shaping and templating."""

from typing import Any, Dict
from .base import Node, NodeContext, NodeDefinition, NodeResult
from ..expressions import evaluate_template
from ..state import ExecutionStatus


class TransformNode:
    """Safely reshapes JSON data, extracts fields, and sets workflow variables."""

    @property
    def definition(self) -> NodeDefinition:
        return NodeDefinition(
            type="transform",
            name="Data Transform",
            description="Transforms and reshapes data structures using template expressions.",
            category="Logic & Control",
            icon="binary",
            inputs=["input"],
            outputs=["output"],
            config_schema={
                "type": "object",
                "properties": {
                    "template": {
                        "type": "object",
                        "description": "Target JSON structure to produce (values support expressions)",
                        "default": {}
                    },
                    "set_variables": {
                        "type": "object",
                        "description": "Workflow variables to set or update for subsequent nodes",
                        "default": {}
                    }
                }
            }
        )

    async def execute(self, context: NodeContext) -> NodeResult:
        cfg = context.node_config
        template = cfg.get("template", {})
        set_vars = cfg.get("set_variables", {})

        eval_ctx: Dict[str, Any] = {
            "trigger": context.trigger_data,
            "variables": context.variables,
            "inputs": context.inputs,
            "execution": {"id": context.execution_id},
        }
        eval_ctx.update(context.inputs)

        transformed = evaluate_template(template, eval_ctx)
        
        # Update workflow variables if specified
        if isinstance(set_vars, dict):
            for k, v in set_vars.items():
                context.variables[k] = evaluate_template(v, eval_ctx)

        return NodeResult(output=transformed, status=ExecutionStatus.COMPLETED)
