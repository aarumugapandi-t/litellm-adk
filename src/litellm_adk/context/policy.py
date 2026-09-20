"""Context policies, windows, and item definitions."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ContextPlacement(str, Enum):
    """Placement targets for ephemeral RAG reference context."""

    USER_TURN = "user_turn"
    SYSTEM_PROMPT = "system_prompt"


class ContextStrategy(str, Enum):
    """Strategies for pruning or compressing context to fit model windows."""

    SLIDING_WINDOW = "sliding_window"
    SUMMARIZATION = "summarization"
    SEMANTIC_TRUNCATION = "semantic_truncation"

    # Backward compatibility aliases
    TRUNCATE = "sliding_window"
    SUMMARIZE = "summarization"
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
    """Configuration governing context window budgets, compaction strategies, and placement."""

    max_tokens: Optional[int] = Field(default=None, description="Maximum total token budget for model inputs.")
    reserve_tokens: int = Field(default=500, description="Tokens reserved for model completion output.")
    strategy: ContextStrategy = Field(default=ContextStrategy.SLIDING_WINDOW, description="Context reduction strategy.")
    preserve_system_prompt: bool = Field(default=True, description="Never evict system instructions.")
    preserve_last_n_messages: int = Field(default=4, description="Number of recent messages to always preserve.")
    summarize_model: Optional[str] = Field(default=None, description="Model to use for summarization compaction.")
    context_placement: str = Field(default="user_turn", description="Where to inject ephemeral RAG context: 'user_turn' or 'system_prompt'.")
