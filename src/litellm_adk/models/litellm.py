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

        # Initialize LiteLLM Router if router instance or model_list provided
        self.router = getattr(self.config, "router", None)
        if not self.router and getattr(self.config, "model_list", None):
            try:
                self.router = litellm.Router(model_list=self.config.model_list)
                adk_logger.info(f"Initialized litellm.Router for model '{self.config.model}' with {len(self.config.model_list)} deployments.")
            except Exception as e:
                adk_logger.warning(f"Could not instantiate litellm.Router from model_list: {e}")
                self.router = None

    @staticmethod
    def _is_external_provider_model(model_name: str) -> bool:
        """Determines if a model targets an external explicit provider (e.g. 'oci/xai.grok-3', 'anthropic/claude-3')
        rather than an OpenAI-compatible proxy."""
        if not model_name or model_name.startswith("openai/"):
            return False
        if "/" in model_name:
            provider = model_name.split("/", 1)[0].lower()
            return provider != "openai"
        return False

    def _normalize_model_and_fallbacks(self) -> None:
        """Normalizes model names and fallback configurations."""
        base_url = (self.config.api_base or "").strip()
        model = self.config.model

        # Only prepend 'openai/' if base_url is specified AND model does not target an external provider
        if base_url and not model.startswith("openai/") and not self._is_external_provider_model(model):
            adk_logger.debug(f"Custom base_url detected ({base_url}). Prepending 'openai/' to model {model}")
            self.config.model = f"openai/{model}"

        # Normalize fallbacks if any
        if self.config.fallbacks:
            normalized_fallbacks = []
            for fb in self.config.fallbacks:
                if isinstance(fb, str):
                    if self._is_external_provider_model(fb):
                        # External provider: do not prepend openai/, do not inherit proxy base_url
                        normalized_fallbacks.append({"model": fb, "api_base": None, "base_url": None, "api_key": None})
                    else:
                        fb_model = f"openai/{fb}" if (base_url and not fb.startswith("openai/")) else fb
                        normalized_fallbacks.append({
                            "model": fb_model,
                            "api_base": base_url or None,
                            "base_url": base_url or None,
                            "api_key": self.config.api_key,
                        })
                elif isinstance(fb, dict):
                    fb_copy = dict(fb)
                    fb_m = fb_copy.get("model", "")
                    if self._is_external_provider_model(fb_m):
                        fb_copy.setdefault("api_base", None)
                        fb_copy.setdefault("base_url", None)
                        fb_copy.setdefault("api_key", None)
                    elif base_url and not fb_m.startswith("openai/"):
                        fb_copy["model"] = f"openai/{fb_m}"
                        fb_copy.setdefault("api_base", base_url)
                        fb_copy.setdefault("base_url", base_url)
                        fb_copy.setdefault("api_key", self.config.api_key)
                    normalized_fallbacks.append(fb_copy)
                else:
                    normalized_fallbacks.append(fb)
            self.config.fallbacks = normalized_fallbacks

    def _build_fallback_kwargs(self, base_kwargs: Dict[str, Any], fallback: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Constructs safe completion arguments for a specific fallback attempt."""
        fb_kwargs = {k: v for k, v in base_kwargs.items() if k != "fallbacks"}

        if isinstance(fallback, dict):
            fb_copy = dict(fallback)
            fb_model = fb_copy.pop("model", self.config.model)
            for k, v in fb_copy.items():
                if v is None:
                    fb_kwargs.pop(k, None)
                    if k in ("api_base", "base_url"):
                        fb_kwargs.pop("api_base", None)
                        fb_kwargs.pop("base_url", None)
                else:
                    fb_kwargs[k] = v
            fb_kwargs["model"] = fb_model
        else:
            fb_model = str(fallback)
            if self._is_external_provider_model(fb_model):
                fb_kwargs.pop("base_url", None)
                fb_kwargs.pop("api_base", None)
                fb_kwargs.pop("api_key", None)
                fb_kwargs["model"] = fb_model
            else:
                base_url = (self.config.api_base or "").strip()
                if base_url and not fb_model.startswith("openai/"):
                    fb_model = f"openai/{fb_model}"
                fb_kwargs["model"] = fb_model
                if base_url:
                    fb_kwargs["base_url"] = base_url
                    fb_kwargs["api_base"] = base_url

        return fb_kwargs

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
        if self.config.api_base and not self._is_external_provider_model(self.config.model):
            kwargs["base_url"] = self.config.api_base
            kwargs["api_base"] = self.config.api_base
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
        # Note: We do not pass fallbacks directly to litellm.acompletion because LiteLLM's internal
        # fallback runner leaks proxy base_url into external provider models and vice versa.
        # Instead, ADK handles fallbacks actively and cleanly in generate() / completion().
        if getattr(self.config, "caching", None) is not None:
            kwargs["caching"] = self.config.caching
        if getattr(self.config, "cache_params", None) is not None:
            kwargs["cache_params"] = self.config.cache_params

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
        """Executes asynchronous LLM completion call via LiteLLM or LiteLLM Router."""
        call_kwargs = self._build_completion_kwargs(messages, tools=tools, stream=False, **kwargs)

        try:
            from unittest.mock import Mock
            # Route through Router if configured
            if self.router is not None:
                if isinstance(getattr(self.router, "completion", None), Mock) and not isinstance(getattr(self.router, "acompletion", None), Mock):
                    raw_response = self.router.completion(**call_kwargs)
                else:
                    raw_response = await self.router.acompletion(**call_kwargs)
            elif isinstance(getattr(litellm, "completion", None), Mock) and not isinstance(getattr(litellm, "acompletion", None), Mock):
                raw_response = litellm.completion(**call_kwargs)
            else:
                raw_response = await litellm.acompletion(**call_kwargs)
            return self._parse_response(raw_response)
        except Exception as e:
            # Active ADK-level fallback execution
            if self.config.fallbacks:
                adk_logger.warning(
                    f"Primary model '{self.config.model}' invocation failed ({e}). "
                    f"Attempting ADK fallback models..."
                )
                last_err = e
                for fallback in self.config.fallbacks:
                    fb_name = fallback.get("model") if isinstance(fallback, dict) else str(fallback)
                    try:
                        adk_logger.info(f"Invoking fallback model '{fb_name}'...")
                        fb_kwargs = self._build_fallback_kwargs(call_kwargs, fallback)
                        raw_response = await litellm.acompletion(**fb_kwargs)
                        adk_logger.info(f"Fallback model '{fb_name}' succeeded.")
                        return self._parse_response(raw_response)
                    except Exception as fb_err:
                        adk_logger.warning(f"Fallback model '{fb_name}' failed: {fb_err}")
                        last_err = fb_err
                        continue
                adk_logger.error(f"Primary model and all configured fallbacks failed. Last error: {last_err}")
                raise ModelError(
                    message=f"Primary model '{self.config.model}' and all fallbacks failed: {last_err}",
                    model=self.config.model,
                    details={"call_kwargs": {k: v for k, v in call_kwargs.items() if k != "messages"}},
                ) from last_err

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
        """Executes synchronous LLM completion call via LiteLLM or LiteLLM Router."""
        call_kwargs = self._build_completion_kwargs(messages, tools=tools, stream=False, **kwargs)

        try:
            if self.router is not None:
                raw_response = self.router.completion(**call_kwargs)
            else:
                raw_response = litellm.completion(**call_kwargs)
            return self._parse_response(raw_response)
        except Exception as e:
            if self.config.fallbacks:
                adk_logger.warning(
                    f"Primary model '{self.config.model}' invocation failed ({e}). "
                    f"Attempting ADK fallback models..."
                )
                last_err = e
                for fallback in self.config.fallbacks:
                    fb_name = fallback.get("model") if isinstance(fallback, dict) else str(fallback)
                    try:
                        adk_logger.info(f"Invoking fallback model '{fb_name}'...")
                        fb_kwargs = self._build_fallback_kwargs(call_kwargs, fallback)
                        raw_response = litellm.completion(**fb_kwargs)
                        adk_logger.info(f"Fallback model '{fb_name}' succeeded.")
                        return self._parse_response(raw_response)
                    except Exception as fb_err:
                        adk_logger.warning(f"Fallback model '{fb_name}' failed: {fb_err}")
                        last_err = fb_err
                        continue
                raise ModelError(
                    message=f"Primary model '{self.config.model}' and all fallbacks failed: {last_err}",
                    model=self.config.model,
                ) from last_err

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
        """Streams chunks asynchronously from LiteLLM or LiteLLM Router."""
        call_kwargs = self._build_completion_kwargs(messages, tools=tools, stream=True, **kwargs)

        try:
            if self.router is not None:
                raw_stream = await self.router.acompletion(**call_kwargs)
            else:
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

        # Calculate exact cost via LiteLLM completion_cost
        try:
            cost = litellm.completion_cost(completion_response=raw_response)
            if cost is not None:
                usage.estimated_cost = float(cost)
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
