"""LLM Node executing direct LiteLLM model completions."""

from typing import Any, Dict
import litellm
from .base import Node, NodeContext, NodeDefinition, NodeResult
from ..expressions import evaluate_template
from ..state import ExecutionStatus


class LLMNode:
    """Direct LLM invocation node with template prompt evaluation."""

    @property
    def definition(self) -> NodeDefinition:
        return NodeDefinition(
            type="llm",
            name="LLM Completion",
            description="Generates a completion directly from any supported model via LiteLLM.",
            category="AI & Agents",
            icon="sparkles",
            inputs=["input"],
            outputs=["output"],
            config_schema={
                "type": "object",
                "required": ["prompt"],
                "properties": {
                    "model": {
                        "type": "string",
                        "description": "Model identifier (e.g., openai/gpt-4o, openrouter/mistralai/ministral-3b-2512)",
                        "default": "openai/gpt-4o-mini"
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
                        "description": "User prompt (supports expressions like {{ trigger.input }})",
                        "default": "{{ trigger.input }}"
                    },
                    "system_prompt": {
                        "type": "string",
                        "description": "Optional system prompt",
                        "default": "You are a helpful assistant."
                    },
                    "temperature": {
                        "type": "number",
                        "description": "Sampling temperature",
                        "default": 0.7,
                        "minimum": 0.0,
                        "maximum": 2.0
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Maximum tokens to generate",
                        "default": 1000
                    },
                    "response_format": {
                        "type": "string",
                        "description": "Response format: text or json_object",
                        "enum": ["text", "json_object"],
                        "default": "text"
                    }
                }
            }
        )

    async def execute(self, context: NodeContext) -> NodeResult:
        cfg = context.node_config
        model_name = cfg.get("model", "openai/gpt-4o-mini")
        raw_api_key = cfg.get("api_key", "")
        raw_base_url = cfg.get("base_url", "")
        raw_prompt = cfg.get("prompt", "")
        raw_system = cfg.get("system_prompt", "You are a helpful assistant.")
        temp = float(cfg.get("temperature", 0.7))
        max_tokens = cfg.get("max_tokens")

        # Build evaluation context for expressions
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

        if not api_key_rendered and "api_key" in context.variables:
            api_key_rendered = context.variables["api_key"]
        if not base_url_rendered and "base_url" in context.variables:
            base_url_rendered = context.variables["base_url"]

        messages = []
        if system_rendered:
            messages.append({"role": "system", "content": system_rendered})
        messages.append({"role": "user", "content": prompt_rendered})

        call_kwargs: Dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": temp,
        }
        if api_key_rendered:
            call_kwargs["api_key"] = api_key_rendered
        if base_url_rendered:
            call_kwargs["api_base"] = base_url_rendered
            call_kwargs["base_url"] = base_url_rendered
        if max_tokens:
            call_kwargs["max_tokens"] = int(max_tokens)
        if cfg.get("response_format") == "json_object":
            call_kwargs["response_format"] = {"type": "json_object"}

        try:
            resp = await litellm.acompletion(**call_kwargs)
            choice = resp.choices[0]
            content = choice.message.content if hasattr(choice, "message") else ""
            usage = resp.usage.dict() if hasattr(resp, "usage") and resp.usage else {}
            return NodeResult(
                output=content,
                status=ExecutionStatus.COMPLETED,
                metadata={"usage": usage, "model": model_name}
            )
        except Exception as e:
            return NodeResult(
                output=None,
                status=ExecutionStatus.FAILED,
                error=str(e),
                metadata={"model": model_name}
            )
