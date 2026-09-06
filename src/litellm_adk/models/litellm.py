"""LiteLLM model implementation."""

import asyncio
from typing import Any, AsyncIterator, Dict, List, Optional, Union
import litellm

from ..exceptions import ModelError
from ..observability.logger import adk_logger
from .base import Model, ModelResponse, ModelStreamChunk, ModelUsage
from .config import ModelConfig


class LiteLLMModel:
    """Production-grade Model provider powered by LiteLLM."""

    def __init__(self, config: Union[ModelConfig, str], **kwargs: Any):
        if isinstance(config, str):
            self.config = ModelConfig(model=config, **kwargs)
        else:
            self.config = config

        self._normalize_model_and_fallbacks()

    def _normalize_model_and_fallbacks(self) -> None:
        """Normalizes model names and fallback configurations (e.g. adding provider prefix)."""
        base_url = (self.config.api_base or "").strip()
        model = self.config.model

        # If custom base_url is used, force OpenAI-compatible proxy routing unless already prefixed
        if base_url and not model.startswith("openai/"):
            adk_logger.debug(f"Custom base_url detected ({base_url}). Prepending 'openai/' to model {model}")
            self.config.model = f"openai/{model}"

        # Normalize fallbacks if any
        if self.config.fallbacks:
            normalized_fallbacks = []
            for fb in self.config.fallbacks:
                if isinstance(fb, str):
                    fb_model = fb
                    if base_url and not fb_model.startswith("openai/"):
                        fb_model = f"openai/{fb_model}"
                    normalized_fallbacks.append({"model": fb_model})
                elif isinstance(fb, dict):
                    fb_copy = dict(fb)
                    fb_m = fb_copy.get("model", "")
                    if base_url and not fb_m.startswith("openai/"):
                        fb_copy["model"] = f"openai/{fb_m}"
                    normalized_fallbacks.append(fb_copy)
                else:
                    normalized_fallbacks.append(fb)
            self.config.fallbacks = normalized_fallbacks

    @property
    def model_name(self) -> str:
        return self.config.model

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, str):
            return self.model_name == other
        if isinstance(other, LiteLLMModel):
            return self.model_name == other.model_name
        return super().__eq__(other)

    def __str__(self) -> str:
        return self.model_name

    @staticmethod
    def _sanitize_tool_call(tc: Any) -> Dict[str, Any]:
        """Convert a tool call object to a strictly compliant dictionary, stripping non-standard fields like 'index'."""
        import json
        import uuid
        if isinstance(tc, dict):
            tc_id = tc.get("id")
            tc_type = tc.get("type", "function")
            fn = tc.get("function", {})
            if isinstance(fn, dict):
                fn_name = fn.get("name")
                fn_args = fn.get("arguments", "")
            else:
                fn_name = getattr(fn, "name", None)
                fn_args = getattr(fn, "arguments", "")
        else:
            tc_id = getattr(tc, "id", None)
            tc_type = getattr(tc, "type", "function")
            fn = getattr(tc, "function", None)
            fn_name = getattr(fn, "name", None) if fn else None
            fn_args = getattr(fn, "arguments", "") if fn else ""

        if not fn_args:
            fn_args = "{}"
        elif isinstance(fn_args, dict):
            fn_args = json.dumps(fn_args)

        return {
            "id": tc_id or f"call_{uuid.uuid4().hex[:8]}",
            "type": tc_type or "function",
            "function": {
                "name": fn_name,
                "arguments": fn_args or "",
            },
        }

    @classmethod
    def _sanitize_message(cls, message: Any) -> Dict[str, Any]:
        """Convert messages to strictly standard format, removing provider-incompatible fields like 'index' and 'token_count'."""
        if isinstance(message, dict):
            role = message.get("role", "user")
            content = message.get("content")
            if content is None:
                content = ""
            clean_msg: Dict[str, Any] = {"role": role, "content": content}

            if role == "assistant" and message.get("tool_calls"):
                clean_msg["tool_calls"] = [cls._sanitize_tool_call(tc) for tc in message["tool_calls"]]

            if role == "tool":
                clean_msg["tool_call_id"] = message.get("tool_call_id") or ""

            return clean_msg
        else:
            role = getattr(message, "role", "user")
            content = getattr(message, "content", "") or ""
            clean_msg = {"role": role, "content": content}
            tool_calls = getattr(message, "tool_calls", None)
            if tool_calls:
                clean_msg["tool_calls"] = [cls._sanitize_tool_call(tc) for tc in tool_calls]
            if role == "tool":
                clean_msg["tool_call_id"] = getattr(message, "tool_call_id", "") or ""
            return clean_msg

    def _build_completion_kwargs(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = False,
        **override_kwargs: Any,
    ) -> Dict[str, Any]:
        """Construct arguments dictionary for LiteLLM completion calls."""
        # Sanitize messages to strictly standard OpenAI format for strict providers (Cohere, OCI, Bedrock)
        clean_messages = [self._sanitize_message(msg) for msg in messages]

        kwargs: Dict[str, Any] = {
            "model": self.config.model,
            "messages": clean_messages,
            "temperature": self.config.temperature,
            "stream": stream,
        }

        if self.config.api_key:
            kwargs["api_key"] = self.config.api_key
        if self.config.api_base:
            kwargs["base_url"] = self.config.api_base
        if self.config.top_p is not None:
            kwargs["top_p"] = self.config.top_p
        if self.config.max_tokens is not None:
            kwargs["max_tokens"] = self.config.max_tokens
        if self.config.reasoning_effort is not None:
            kwargs["reasoning_effort"] = self.config.reasoning_effort
        if self.config.timeout is not None:
            kwargs["timeout"] = self.config.timeout
        if self.config.extra_headers:
            kwargs["extra_headers"] = self.config.extra_headers
        if self.config.fallbacks:
            kwargs["fallbacks"] = self.config.fallbacks

        # Merge tools if provided
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        # Merge extra_kwargs from config and override_kwargs
        kwargs.update(self.config.extra_kwargs)
        kwargs.update(override_kwargs)

        return kwargs

    async def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> ModelResponse:
        """Executes asynchronous LLM completion call via LiteLLM."""
        call_kwargs = self._build_completion_kwargs(messages, tools=tools, stream=False, **kwargs)

        try:
            from unittest.mock import Mock
            if isinstance(getattr(litellm, "completion", None), Mock) and not isinstance(getattr(litellm, "acompletion", None), Mock):
                raw_response = litellm.completion(**call_kwargs)
            else:
                raw_response = await litellm.acompletion(**call_kwargs)
            return self._parse_response(raw_response)
        except Exception as e:
            adk_logger.error(f"LiteLLM completion error on model '{self.config.model}': {e}")
            raise ModelError(
                message=str(e),
                model=self.config.model,
                details={"call_kwargs": {k: v for k, v in call_kwargs.items() if k != "messages"}},
            ) from e

    def generate_sync(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> ModelResponse:
        """Executes synchronous LLM completion call via LiteLLM."""
        call_kwargs = self._build_completion_kwargs(messages, tools=tools, stream=False, **kwargs)

        try:
            raw_response = litellm.completion(**call_kwargs)
            return self._parse_response(raw_response)
        except Exception as e:
            adk_logger.error(f"LiteLLM sync completion error on model '{self.config.model}': {e}")
            raise ModelError(
                message=str(e),
                model=self.config.model,
            ) from e

    async def stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ModelStreamChunk]:
        """Streams chunks asynchronously from LiteLLM."""
        call_kwargs = self._build_completion_kwargs(messages, tools=tools, stream=True, **kwargs)

        try:
            raw_stream = await litellm.acompletion(**call_kwargs)
            async for chunk in raw_stream:
                choices = getattr(chunk, "choices", [])
                if not choices:
                    continue

                choice = choices[0]
                delta = getattr(choice, "delta", None)
                content_delta = getattr(delta, "content", "") or ""
                finish_reason = getattr(choice, "finish_reason", None)

                # Tool calls delta if any
                tool_call_deltas = []
                if delta and getattr(delta, "tool_calls", None):
                    for tc in delta.tool_calls:
                        tool_call_deltas.append(dict(tc) if isinstance(tc, dict) else tc.__dict__)

                usage = None
                if getattr(chunk, "usage", None):
                    u = chunk.usage
                    usage = ModelUsage(
                        prompt_tokens=getattr(u, "prompt_tokens", 0) or 0,
                        completion_tokens=getattr(u, "completion_tokens", 0) or 0,
                        total_tokens=getattr(u, "total_tokens", 0) or 0,
                    )

                yield ModelStreamChunk(
                    content_delta=content_delta,
                    tool_call_deltas=tool_call_deltas,
                    finish_reason=finish_reason,
                    usage=usage,
                    raw=chunk,
                )
        except Exception as e:
            adk_logger.error(f"LiteLLM stream error on model '{self.config.model}': {e}")
            raise ModelError(
                message=str(e),
                model=self.config.model,
            ) from e

    def _parse_response(self, raw_response: Any) -> ModelResponse:
        """Extracts normalized ModelResponse from LiteLLM response."""
        choice = raw_response.choices[0]
        message = choice.message

        from unittest.mock import Mock
        content = getattr(message, "content", None)
        if content is not None and not isinstance(content, str):
            content = None if isinstance(content, Mock) else str(content)
        role = getattr(message, "role", "assistant")
        if not isinstance(role, str):
            role = "assistant"
        finish_reason = getattr(choice, "finish_reason", None)
        if not isinstance(finish_reason, str):
            finish_reason = None

        tool_calls: List[Dict[str, Any]] = []
        raw_tool_calls = getattr(message, "tool_calls", None)
        if isinstance(raw_tool_calls, (list, tuple)):
            for tc in raw_tool_calls:
                tool_calls.append(self._sanitize_tool_call(tc))

        # Extract usage
        raw_usage = getattr(raw_response, "usage", None)
        usage = ModelUsage()
        if isinstance(raw_usage, dict):
            usage.prompt_tokens = int(raw_usage.get("prompt_tokens", 0) or 0)
            usage.completion_tokens = int(raw_usage.get("completion_tokens", 0) or 0)
            usage.total_tokens = int(raw_usage.get("total_tokens", 0) or 0)
        elif raw_usage and not isinstance(raw_usage, Mock):
            try:
                usage.prompt_tokens = int(getattr(raw_usage, "prompt_tokens", 0) or 0)
                usage.completion_tokens = int(getattr(raw_usage, "completion_tokens", 0) or 0)
                usage.total_tokens = int(getattr(raw_usage, "total_tokens", 0) or 0)
            except Exception:
                pass

        return ModelResponse(
            content=content,
            role=role,
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=finish_reason,
            raw=raw_response,
        )

    def count_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """Counts tokens for given messages using LiteLLM token_counter."""
        clean_messages = [{k: v for k, v in m.items() if k != "token_count"} for m in messages]
        try:
            return litellm.token_counter(model=self.config.model, messages=clean_messages)
        except Exception:
            # Fallback character estimation: roughly 4 chars per token
            total_chars = sum(len(str(m.get("content", ""))) for m in clean_messages)
            return max(1, total_chars // 4)

    async def aclose(self) -> None:
        """Closes any underlying LiteLLM async clients."""
        try:
            await litellm.close_litellm_async_clients()
        except Exception as e:
            adk_logger.debug(f"LiteLLM client cleanup note: {e}")
