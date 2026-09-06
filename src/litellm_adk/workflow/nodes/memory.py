"""Memory Node for persisting and retrieving state and conversational facts."""

from typing import Any, Dict
from .base import Node, NodeContext, NodeDefinition, NodeResult
from ..expressions import evaluate_template
from ..state import ExecutionStatus
from ...memory.in_memory import InMemoryMemory

# Shared in-memory workflow memory store
_GLOBAL_MEMORY = InMemoryMemory()


class MemoryNode:
    """Operations against workflow long-term and cross-session memory."""

    @property
    def definition(self) -> NodeDefinition:
        return NodeDefinition(
            type="memory",
            name="Memory Storage",
            description="Reads, writes, searches, or clears workflow memory and cross-session facts.",
            category="Memory & Vector",
            icon="database",
            inputs=["input"],
            outputs=["output"],
            config_schema={
                "type": "object",
                "required": ["operation"],
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["read", "write", "search", "delete"],
                        "default": "read"
                    },
                    "key": {
                        "type": "string",
                        "description": "Storage key or session identifier",
                        "default": "{{ session.id }}"
                    },
                    "value": {
                        "type": "string",
                        "description": "Payload to store when operation is write",
                        "default": "{{ trigger.input }}"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max items to retrieve",
                        "default": 10
                    }
                }
            }
        )

    async def execute(self, context: NodeContext) -> NodeResult:
        cfg = context.node_config
        op = cfg.get("operation", "read")
        raw_key = cfg.get("key", "default")
        raw_val = cfg.get("value", "")
        limit = int(cfg.get("limit", 10))

        eval_ctx: Dict[str, Any] = {
            "trigger": context.trigger_data,
            "variables": context.variables,
            "inputs": context.inputs,
            "execution": {"id": context.execution_id},
        }
        eval_ctx.update(context.inputs)

        key = str(evaluate_template(raw_key, eval_ctx))
        value = evaluate_template(raw_val, eval_ctx)

        try:
            if op == "write":
                await _GLOBAL_MEMORY.add(session_id=key, message={"role": "system", "content": str(value)})
                return NodeResult(output={"status": "stored", "key": key}, status=ExecutionStatus.COMPLETED)
            elif op == "read":
                messages = await _GLOBAL_MEMORY.get_messages(session_id=key, limit=limit)
                return NodeResult(output=messages, status=ExecutionStatus.COMPLETED)
            elif op == "delete":
                await _GLOBAL_MEMORY.clear(session_id=key)
                return NodeResult(output={"status": "cleared", "key": key}, status=ExecutionStatus.COMPLETED)
            else:
                messages = await _GLOBAL_MEMORY.get_messages(session_id=key, limit=limit)
                return NodeResult(output=messages, status=ExecutionStatus.COMPLETED)
        except Exception as e:
            return NodeResult(output=None, status=ExecutionStatus.FAILED, error=str(e))
