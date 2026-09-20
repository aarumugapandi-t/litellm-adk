import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import pytest

from litellm_adk.models.litellm import LiteLLMModel
from litellm_adk.models.config import ModelConfig
from litellm_adk.exceptions import ModelError


def test_is_external_provider_model():
    # External providers
    assert LiteLLMModel._is_external_provider_model("oci/xai.grok-3") is True
    assert LiteLLMModel._is_external_provider_model("anthropic/claude-3-haiku") is True
    assert LiteLLMModel._is_external_provider_model("groq/llama-3-8b") is True
    assert LiteLLMModel._is_external_provider_model("gemini/gemini-1.5-flash") is True

    # OpenAI or bare proxy models
    assert LiteLLMModel._is_external_provider_model("command-a-03-2025") is False
    assert LiteLLMModel._is_external_provider_model("openai/command-a-03-2025") is False
    assert LiteLLMModel._is_external_provider_model("gpt-4o") is False
    assert LiteLLMModel._is_external_provider_model("openai/gpt-4o") is False


def test_normalization_does_not_prepend_openai_to_external_providers():
    model = LiteLLMModel(
        ModelConfig(
            model="oci/xai.grok-3",
            api_base="http://localhost:9000/v1",
            fallbacks=["command-a-03-2025", "anthropic/claude-3-haiku"],
        )
    )
    # Primary model should NOT be mangled to openai/oci/xai.grok-3
    assert model.config.model == "oci/xai.grok-3"

    # Fallbacks: proxy model should get openai/ and base_url, external should not
    fallbacks = model.config.fallbacks
    assert len(fallbacks) == 2
    assert fallbacks[0]["model"] == "openai/command-a-03-2025"
    assert fallbacks[0]["base_url"] == "http://localhost:9000/v1"

    assert fallbacks[1]["model"] == "anthropic/claude-3-haiku"
    assert fallbacks[1]["base_url"] is None


@pytest.mark.asyncio
async def test_active_adk_fallback_execution_when_primary_fails():
    model = LiteLLMModel(
        ModelConfig(
            model="oci/xai.grok-3",
            api_base="http://localhost:9000/v1",
            fallbacks=["command-a-03-2025"],
        )
    )

    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="Fallback answer", role="assistant", tool_calls=None))]
    mock_resp.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)

    # First call (primary) raises BadRequestError, second call (fallback) succeeds
    with patch("litellm.acompletion", side_effect=[Exception("No healthy deployments for oci/xai.grok-3"), mock_resp]) as mock_call:
        res = await model.generate(messages=[{"role": "user", "content": "hi"}])
        assert res.content == "Fallback answer"
        assert mock_call.call_count == 2
        # Verify fallback call kwargs had the fallback model
        fallback_kwargs = mock_call.call_args_list[1].kwargs
        assert fallback_kwargs["model"] == "openai/command-a-03-2025"
        assert fallback_kwargs["base_url"] == "http://localhost:9000/v1"
