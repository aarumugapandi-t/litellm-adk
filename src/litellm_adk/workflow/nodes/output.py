"""Output Node terminating workflow and structuring the final response."""

from typing import Any, Dict
from .base import Node, NodeContext, NodeDefinition, NodeResult
from ..expressions import evaluate_template
from ..state import ExecutionStatus


class OutputNode:
    """Terminal node aggregating and returning the final workflow result."""

    @property
    def definition(self) -> NodeDefinition:
        return NodeDefinition(
            type="output",
            name="Workflow Output",
            description="Terminates the workflow and formats the final returned result.",
            category="Input & Output",
            icon="check-circle",
            inputs=["input"],
            outputs=[],
            config_schema={
                "type": "object",
                "properties": {
                    "response": {
                        "type": "string",
                        "description": "Payload or expression returned as final workflow output",
                        "default": "{{ input }}"
                    },
                    "format": {
                        "type": "string",
                        "enum": ["json", "text"],
                        "default": "json"
                    }
                }
            }
        )

    async def execute(self, context: NodeContext) -> NodeResult:
        cfg = context.node_config
        raw_resp = cfg.get("response", "{{ input }}")

        eval_ctx = context.get_eval_context()

        # Fallback to direct input if response is empty
        if not raw_resp:
            return NodeResult(output=context.inputs, status=ExecutionStatus.COMPLETED)

        rendered = evaluate_template(raw_resp, eval_ctx)
        return NodeResult(output=rendered, status=ExecutionStatus.COMPLETED)
