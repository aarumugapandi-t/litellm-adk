"""Model configuration definitions."""

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, ConfigDict


class ModelConfig(BaseModel):
    """Configuration for LLM providers via LiteLLM."""

    model: str = Field(..., description="LiteLLM-compatible model identifier (e.g., 'gpt-4o', 'groq/llama-3.3-70b').")
    provider: Optional[str] = Field(default=None, description="Explicit provider override if needed.")
    api_key: Optional[str] = Field(default=None, description="API key for the model provider.")
    api_base: Optional[str] = Field(default=None, description="Custom base URL / proxy endpoint.")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature.")
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Nucleus sampling probability.")
    max_tokens: Optional[int] = Field(default=None, description="Maximum tokens to generate.")
    reasoning_effort: Optional[str] = Field(default=None, description="Reasoning effort for reasoning models ('low', 'medium', 'high').")
    timeout: Optional[float] = Field(default=60.0, description="Timeout in seconds for model requests.")
    max_retries: int = Field(default=3, ge=0, description="Maximum retry attempts on transient failures.")
    extra_headers: Optional[Dict[str, str]] = Field(default=None, description="Custom HTTP headers to send.")
    fallbacks: Optional[List[Union[str, Dict[str, Any]]]] = Field(
        default=None,
        description="Fallback model strings or configs if primary model fails."
    )
    extra_kwargs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional arguments forwarded directly to litellm.completion."
    )

    model_config = ConfigDict(extra="allow")
