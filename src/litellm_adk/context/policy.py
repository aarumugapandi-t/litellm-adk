"""Context policies, windows, and item definitions."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ContextStrategy(str, Enum):
    """Strategies for pruning or compressing context to fit model windows."""

    TRUNCATE = "truncate"
    SUMMARIZE = "summarize"
    PRIORITIZE = "prioritize"


class ContextItem(BaseModel):
    """An individual piece of content within the assembled context."""

    role: str
    content: str
    priority: int = Field(default=0, description="Higher priority items are retained longer.")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    token_count: Optional[int] = None


class ContextWindow(BaseModel):
    """Tracks token allocation and capacity within the model's context window."""

    max_tokens: int
    reserve_tokens: int = 500
    used_tokens: int = 0

    @property
    def available_tokens(self) -> int:
        return max(0, self.max_tokens - self.reserve_tokens - self.used_tokens)


class ContextPolicy(BaseModel):
    """Configuration governing context window budgets and reduction strategies."""

    max_tokens: Optional[int] = Field(default=None, description="Maximum total token budget for model inputs.")
    reserve_tokens: int = Field(default=500, description="Tokens reserved for model completion output.")
    strategy: ContextStrategy = Field(default=ContextStrategy.TRUNCATE, description="Context reduction strategy.")
