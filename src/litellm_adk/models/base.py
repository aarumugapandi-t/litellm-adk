"""Base protocols and data structures for Model providers."""

from typing import Any, AsyncIterator, Dict, List, Optional, Protocol, runtime_checkable
from pydantic import BaseModel, Field


class ModelUsage(BaseModel):
    """Token usage reporting for a model call."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0


class ModelResponse(BaseModel):
    """Normalized response from a model generation call."""

    content: Optional[str] = None
    role: str = "assistant"
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    usage: ModelUsage = Field(default_factory=ModelUsage)
    finish_reason: Optional[str] = None
    raw: Optional[Any] = None


class ModelStreamChunk(BaseModel):
    """Normalized chunk from a streaming model call."""

    content_delta: str = ""
    tool_call_deltas: List[Dict[str, Any]] = Field(default_factory=list)
    finish_reason: Optional[str] = None
    usage: Optional[ModelUsage] = None
    raw: Optional[Any] = None


@runtime_checkable
class Model(Protocol):
    """Protocol for model gateway implementations."""

    @property
    def model_name(self) -> str:
        """Return the configured model name."""
        ...

    async def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> ModelResponse:
        """Execute a generation call against the model."""
        ...

    async def stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ModelStreamChunk]:
        """Stream chunks from the model."""
        ...

    def count_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """Calculate token count for given messages under this model."""
        ...

    async def aclose(self) -> None:
        """Release any open HTTP clients or connection pools."""
        ...
