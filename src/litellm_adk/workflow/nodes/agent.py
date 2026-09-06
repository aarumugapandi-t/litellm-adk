"""Agent Node executing an orchestrated LiteLLM ADK Agent."""

from typing import Any, Dict, List
from .base import Node, NodeContext, NodeDefinition, NodeResult
from ..expressions import evaluate_template
from ..state import ExecutionStatus
from ...agent.agent import Agent
from ...tools.registry import tool_registry


class AgentNode:
    """Agent node orchestrating an autonomous ADK Agent with tool execution and memory."""

    @property
    def definition(self) -> NodeDefinition:
        return NodeDefinition(
            type="agent",
            name="AI Agent",
            description="Executes a multi-turn AI Agent with tool reasoning, memory, and safety guardrails.",
            category="AI & Agents",
            icon="bot",
            inputs=["input"],
            outputs=["output"],
            config_schema={
                "type": "object",
                "required": ["model", "api_key", "base_url", "prompt"],
                "properties": {
                    "model": {
                        "type": "string",
                        "description": "Model identifier (e.g. openrouter/mistralai/ministral-3b-2512, openai/gpt-4o)",
                        "default": "openrouter/mistralai/ministral-3b-2512"
                    },
                    "api_key": {
                        "type": "string",
                        "format": "password",
                        "description": "API key for model provider (e.g. sk-1234 or {{ variables.api_key }})",
                        "default": ""
                    },
                    "base_url": {
                        "type": "string",
                        "format": "uri",
                        "description": "Custom API endpoint base URL (e.g. http://localhost:9000/v1 or https://openrouter.ai/api/v1)",
                        "default": ""
                    },
                    "prompt": {
                        "type": "string",
                        "description": "Task or query for the agent (supports expressions)",
                        "default": "{{ trigger.input }}"
                    },
                    "system_prompt": {
                        "type": "string",
                        "description": "Agent operational persona and instructions",
                        "default": "You are an intelligent AI workflow agent."
                    },
                    "tools": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tools available to this agent from the tool registry",
                        "default": []
                    },
                    "max_iterations": {
                        "type": "integer",
                        "description": "Maximum reasoning turns before stopping",
                        "default": 10
                    },
                    "temperature": {
                        "type": "number",
                        "description": "Sampling temperature for model reasoning",
                        "default": 0.7
                    }
                }
            }
        )

    async def execute(self, context: NodeContext) -> NodeResult:
        cfg = context.node_config
        model_name = cfg.get("model", "openrouter/mistralai/ministral-3b-2512")
        raw_api_key = cfg.get("api_key", "")
        raw_base_url = cfg.get("base_url", "")
        raw_prompt = cfg.get("prompt", "")
        raw_system = cfg.get("system_prompt", "You are an intelligent AI workflow agent.")
        tool_names = cfg.get("tools", [])
        max_iters = int(cfg.get("max_iterations", 10))

        eval_ctx: Dict[str, Any] = {
            "trigger": context.trigger_data,
            "variables": context.variables,
            "inputs": context.inputs,
            "execution": {"id": context.execution_id},
        }
        eval_ctx.update(context.inputs)

        prompt_rendered = str(evaluate_template(raw_prompt, eval_ctx))
        system_rendered = str(evaluate_template(raw_system, eval_ctx))
        api_key_rendered = str(evaluate_template(raw_api_key, eval_ctx)) if raw_api_key else None
        base_url_rendered = str(evaluate_template(raw_base_url, eval_ctx)) if raw_base_url else None

        # Fallback to variables if not explicitly provided
        if not api_key_rendered and "api_key" in context.variables:
            api_key_rendered = context.variables["api_key"]
        if not base_url_rendered and "base_url" in context.variables:
            base_url_rendered = context.variables["base_url"]

        # Support comma-separated strings or lists for tool_names
        if isinstance(tool_names, str):
            tool_names = [t.strip() for t in tool_names.split(",") if t.strip()]

        # Resolve tools from registry or pass identifier for agent resolution
        resolved_tools = []
        for t_name in tool_names:
            tool_obj = tool_registry.get_tool(t_name)
            if tool_obj:
                resolved_tools.append(tool_obj)
            else:
                resolved_tools.append(t_name)

        try:
            from ...agent.agent import ExecutionConfig

            agent = Agent(
                name=f"WorkflowAgent_{context.node_id}",
                model=model_name,
                api_key=api_key_rendered or None,
                base_url=base_url_rendered or None,
                system_prompt=system_rendered,
                tools=resolved_tools,
                event_bus=context.event_bus,
                approval_manager=context.approval_manager,
                execution_config=ExecutionConfig(max_iterations=max_iters) if max_iters else None,
            )

            res = await agent.ainvoke(
                prompt=prompt_rendered,
                session_id=context.execution_id,
            )

            if getattr(res, "status", None) == "requires_approval":
                return NodeResult(
                    output=None,
                    status=ExecutionStatus.WAITING_FOR_HUMAN,
                    waiting_for_approval=True,
                    approval_payload={"pending_approvals": getattr(res, "pending_approvals", [])},
                    metadata={"agent_status": "requires_approval"}
                )

            tool_calls_data = [
                {"name": tc.name, "arguments": tc.arguments, "result": tc.result, "duration": tc.duration}
                for tc in res.tool_calls
            ]

            return NodeResult(
                output=res.text,
                status=ExecutionStatus.COMPLETED,
                metadata={
                    "tool_calls": tool_calls_data,
                    "tokens": res.usage.total_tokens if hasattr(res, "usage") and res.usage else 0,
                    "duration": res.duration,
                }
            )
        except Exception as e:
            return NodeResult(
                output=None,
                status=ExecutionStatus.FAILED,
                error=str(e),
            )
