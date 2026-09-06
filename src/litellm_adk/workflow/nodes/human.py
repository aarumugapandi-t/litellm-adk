"""Human-in-the-Loop Node pausing workflow for interactive user review."""

from typing import Any, Dict, List
from .base import Node, NodeContext, NodeDefinition, NodeResult
from ..expressions import evaluate_template
from ..state import ExecutionStatus


class HumanNode:
    """Pauses workflow execution and requests human review, approval, or input."""

    @property
    def definition(self) -> NodeDefinition:
        return NodeDefinition(
            type="human",
            name="Human Review & Approval",
            description="Pauses execution until a human reviews details and provides approval or input.",
            category="Human in the Loop",
            icon="user-check",
            inputs=["input"],
            outputs=["approved", "rejected"],
            config_schema={
                "type": "object",
                "required": ["message"],
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Notification prompt explaining what requires human approval",
                        "default": "Please review and approve the requested action."
                    },
                    "approval_type": {
                        "type": "string",
                        "enum": ["boolean_approval", "text_input", "selection"],
                        "default": "boolean_approval"
                    },
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Options when approval_type is selection",
                        "default": ["Approve", "Reject"]
                    }
                }
            }
        )

    async def execute(self, context: NodeContext) -> NodeResult:
        cfg = context.node_config
        raw_msg = cfg.get("message", "Please review and approve the requested action.")
        appr_type = cfg.get("approval_type", "boolean_approval")
        options = cfg.get("options", ["Approve", "Reject"])

        eval_ctx: Dict[str, Any] = {
            "trigger": context.trigger_data,
            "variables": context.variables,
            "inputs": context.inputs,
            "execution": {"id": context.execution_id},
        }
        eval_ctx.update(context.inputs)

        rendered_msg = str(evaluate_template(raw_msg, eval_ctx))

        # Check if human response has already been supplied in resume payload
        decision_data = context.inputs.get("__human_decision__")
        if decision_data is not None:
            approved = bool(decision_data.get("approved", True))
            selected_handle = "approved" if approved else "rejected"
            return NodeResult(
                output=decision_data,
                selected_handle=selected_handle,
                status=ExecutionStatus.COMPLETED
            )

        # Pause execution and request human review
        return NodeResult(
            output=None,
            status=ExecutionStatus.WAITING_FOR_HUMAN,
            waiting_for_approval=True,
            approval_payload={
                "node_id": context.node_id,
                "message": rendered_msg,
                "approval_type": appr_type,
                "options": options,
            },
        )
