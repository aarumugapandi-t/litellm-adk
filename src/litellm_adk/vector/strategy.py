"""Strategy enums and configuration models for retrieval architectures."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RetrievalMode(str, Enum):
    """Execution modality for retrieval integration in agents."""

    TOOL = "tool"          # Autonomous tool calling: LLM chooses when/what to search
    PIPELINE = "pipeline"  # Pre-execution retrieval: runs before reasoning loop, injects into prompt
    BOTH = "both"          # Pipeline pre-retrieval + tool available in agent loop


class RetrievalStrategy(str, Enum):
    """Algorithmic strategy for retrieving relevant context."""

    DIRECT = "direct"                           # Query -> embedding -> search
    CONDITIONAL_TRANSFORM = "conditional_transform"  # Query -> LLM eval/rewrite -> conditional search
    MULTI_QUERY = "multi_query"                 # Query -> LLM sub-queries -> parallel search -> RRF
    ADAPTIVE_ROUTER = "adaptive_router"         # Query -> router -> appropriate strategy


class QueryTransformationResult(BaseModel):
    """Structured decision output from query transformation."""

    needs_search: bool = Field(
        default=True,
        description="Whether external retrieval is required to answer the query."
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Brief rationale for search decision."
    )
    search_query: Optional[str] = Field(
        default=None,
        description="Standalone rewritten query if search is required."
    )
    sub_queries: List[str] = Field(
        default_factory=list,
        description="Sub-queries if query decomposition is triggered."
    )


class QueryTransformationConfig(BaseModel):
    """Configuration for conditional query transformation and reformulation."""

    model: Optional[str] = Field(default=None, description="Model used for query transformation.")
    include_history_turns: int = Field(default=4, description="Number of past conversation turns to inspect.")
    use_hyde: bool = Field(default=False, description="Whether to generate hypothetical document embeddings.")
    custom_chitchat_phrases: Optional[List[str]] = Field(
        default=None,
        description="Optional list of phrases to recognize dynamically as chitchat.",
    )
    intent_evaluator: Optional[Any] = Field(
        default=None,
        description="Optional callable (query -> bool) returning whether search is required.",
    )


class MultiQueryConfig(BaseModel):
    """Configuration for multi-query decomposition and Reciprocal Rank Fusion."""

    model: Optional[str] = Field(default=None, description="Model used for query decomposition.")
    max_sub_queries: int = Field(default=3, ge=2, le=6, description="Maximum number of sub-queries to generate.")
    rrf_k: int = Field(default=60, ge=1, description="Smoothing constant k for Reciprocal Rank Fusion.")


class RetrievalRouterConfig(BaseModel):
    """Configuration for adaptive retrieval routing."""

    router_type: str = Field(default="dynamic", description="'dynamic', 'llm', or 'heuristic'")
    classifier_model: Optional[str] = Field(default=None, description="Model used for LLM classification.")
    enable_heuristics: bool = Field(default=True, description="Enable fuzzy matching fallback when model is absent.")
    fuzzy_cutoff: float = Field(default=0.72, ge=0.0, le=1.0, description="Fuzzy string similarity threshold for typo tolerance.")
    comparative_keywords: Optional[List[str]] = Field(
        default=None,
        description="Custom list of comparative terms for routing.",
    )
    contextual_pronouns: Optional[List[str]] = Field(
        default=None,
        description="Custom list of contextual references and pronouns for routing.",
    )
