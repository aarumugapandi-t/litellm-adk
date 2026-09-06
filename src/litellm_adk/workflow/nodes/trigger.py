"""Trigger nodes initiating workflow executions."""

from typing import Any, Dict
from .base import Node, NodeContext, NodeDefinition, NodeResult
from ..state import ExecutionStatus


class ManualTriggerNode:
    """Manual trigger node activated from UI or CLI."""

    @property
    def definition(self) -> NodeDefinition:
        return NodeDefinition(
            type="manual_trigger",
            name="Manual Trigger",
            description="Starts the workflow on manual execution with custom payload.",
            category="Triggers",
            icon="play-circle",
            inputs=[],
            outputs=["output"],
            config_schema={
                "type": "object",
                "properties": {
                    "default_payload": {
                        "type": "object",
                        "description": "Default JSON payload when triggered without arguments",
                        "default": {}
                    }
                }
            }
        )

    async def execute(self, context: NodeContext) -> NodeResult:
        payload = context.trigger_data or context.node_config.get("default_payload", {})
        return NodeResult(output=payload, status=ExecutionStatus.COMPLETED)


class WebhookTriggerNode:
    """Webhook trigger activated by incoming HTTP POST request."""

    @property
    def definition(self) -> NodeDefinition:
        return NodeDefinition(
            type="webhook_trigger",
            name="Webhook Trigger",
            description="Starts the workflow when an external webhook request is received.",
            category="Triggers",
            icon="webhook",
            inputs=[],
            outputs=["output"],
            config_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Unique webhook endpoint path slug",
                        "default": "webhook-1"
                    }
                }
            }
        )

    async def execute(self, context: NodeContext) -> NodeResult:
        payload = context.trigger_data or {}
        return NodeResult(output=payload, status=ExecutionStatus.COMPLETED)
