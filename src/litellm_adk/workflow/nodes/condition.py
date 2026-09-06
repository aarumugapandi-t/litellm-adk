"""Condition Node providing conditional branching and routing."""

from typing import Any, Dict
from .base import Node, NodeContext, NodeDefinition, NodeResult
from ..expressions import evaluate_template
from ..state import ExecutionStatus


class ConditionNode:
    """Evaluates conditional rules and routes execution along true or false branch handles."""

    @property
    def definition(self) -> NodeDefinition:
        return NodeDefinition(
            type="condition",
            name="Conditional Branch",
            description="Evaluates a logical condition and branches flow to true or false handles.",
            category="Logic & Control",
            icon="git-branch",
            inputs=["input"],
            outputs=["true", "false"],
            config_schema={
                "type": "object",
                "required": ["left_value", "operator"],
                "properties": {
                    "left_value": {
                        "type": "string",
                        "description": "Value or expression to test (e.g. {{ agent.output }})",
                        "default": "{{ trigger.input }}"
                    },
                    "operator": {
                        "type": "string",
                        "enum": [
                            "equals",
                            "not_equals",
                            "contains",
                            "not_contains",
                            "greater_than",
                            "less_than",
                            "is_empty",
                            "is_not_empty"
                        ],
                        "default": "equals"
                    },
                    "right_value": {
                        "type": "string",
                        "description": "Value to compare against",
                        "default": ""
                    }
                }
            }
        )

    async def execute(self, context: NodeContext) -> NodeResult:
        cfg = context.node_config
        raw_left = cfg.get("left_value", "")
        op = cfg.get("operator", "equals")
        raw_right = cfg.get("right_value", "")

        eval_ctx: Dict[str, Any] = {
            "trigger": context.trigger_data,
            "variables": context.variables,
            "inputs": context.inputs,
            "execution": {"id": context.execution_id},
        }
        eval_ctx.update(context.inputs)

        left = evaluate_template(raw_left, eval_ctx)
        right = evaluate_template(raw_right, eval_ctx)

        result_bool = False
        try:
            if op == "equals":
                result_bool = str(left).strip() == str(right).strip()
            elif op == "not_equals":
                result_bool = str(left).strip() != str(right).strip()
            elif op == "contains":
                result_bool = str(right) in str(left)
            elif op == "not_contains":
                result_bool = str(right) not in str(left)
            elif op == "greater_than":
                result_bool = float(left) > float(right)
            elif op == "less_than":
                result_bool = float(left) < float(right)
            elif op == "is_empty":
                result_bool = not bool(left)
            elif op == "is_not_empty":
                result_bool = bool(left)
        except Exception:
            result_bool = False

        selected = "true" if result_bool else "false"
        return NodeResult(
            output={"result": result_bool, "branch": selected},
            selected_handle=selected,
            status=ExecutionStatus.COMPLETED
        )
