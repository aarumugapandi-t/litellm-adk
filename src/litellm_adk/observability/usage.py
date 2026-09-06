"""Token usage, runtime metrics, and cost calculation abstractions."""

import time
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class Usage(BaseModel):
    """Token consumption data."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0


class RunMetrics(BaseModel):
    """Runtime execution metrics for an agent invocation."""

    latency: float = 0.0
    start_time: float = Field(default_factory=time.time)
    end_time: Optional[float] = None
    model_calls: int = 0
    tool_calls: int = 0

    def finish(self) -> None:
        self.end_time = time.time()
        self.latency = max(0.0, self.end_time - self.start_time)


class CostTracker:
    """Estimates LLM invocation cost based on model and token counts."""

    # Default rough rates per 1,000 tokens (USD)
    ESTIMATED_RATES_PER_1K: Dict[str, Dict[str, float]] = {
        "gpt-4o": {"prompt": 0.0025, "completion": 0.01},
        "gpt-4o-mini": {"prompt": 0.00015, "completion": 0.0006},
        "claude-3-5-sonnet": {"prompt": 0.003, "completion": 0.015},
    }

    @classmethod
    def calculate_cost(cls, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculates estimated USD cost for model generation."""
        # Find closest match in rate table
        for key, rate in cls.ESTIMATED_RATES_PER_1K.items():
            if key in model.lower():
                return (prompt_tokens / 1000.0) * rate["prompt"] + (completion_tokens / 1000.0) * rate["completion"]

        # Default fallback estimate ($0.001 per 1k tokens)
        return (prompt_tokens + completion_tokens) / 1000.0 * 0.001
