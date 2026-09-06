"""Memory policy configurations and strategy definitions."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class MemoryStrategy(str, Enum):
    """Strategies for selecting memory items to inject into agent context."""

    RECENT = "recent"
    SEMANTIC = "semantic"
    IMPORTANCE = "importance"
    HYBRID = "hybrid"


class MemoryPolicy(BaseModel):
    """Configuration governing memory ingestion, indexing, and retrieval thresholds."""

    memory_enabled: bool = Field(default=True, description="Whether memory is active.")
    strategy: MemoryStrategy = Field(default=MemoryStrategy.RECENT, description="Retrieval strategy.")
    max_memory_items: int = Field(default=10, description="Max memory items to include in context.")
    memory_relevance_threshold: float = Field(default=0.6, ge=0.0, le=1.0, description="Minimum relevance score.")
    automatic_memory_extraction: bool = Field(default=False, description="Extract facts automatically from turns.")
    memory_write_policy: str = Field(default="always", description="When to persist memory ('always', 'explicit').")
    memory_read_policy: str = Field(default="relevant", description="How to read memory ('all', 'relevant').")
