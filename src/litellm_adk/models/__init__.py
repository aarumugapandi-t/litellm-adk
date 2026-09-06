"""Model abstraction package with backward compatibility."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

# Core model abstractions
from .base import Model, ModelResponse, ModelStreamChunk, ModelUsage
from .config import ModelConfig
from .litellm import LiteLLMModel


# Backward compatibility with litellm_adk.models
class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"
    EXPIRED = "expired"


class ApprovalRequest(BaseModel):
    id: str = Field(..., description="Unique tool call ID")
    session_id: str
    tool_name: str
    original_args: Dict[str, Any]
    modified_args: Optional[Dict[str, Any]] = None
    status: ApprovalStatus = ApprovalStatus.PENDING
    requester: str = "agent"
    reviewer: Optional[str] = None
    reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None


class ApprovalAuditEntry(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: str
    session_id: str
    action: str
    actor: str
    reason: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UsageInfo(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0


class AgentResponse(BaseModel):
    content: str = Field(..., description="The final text response from the agent.")
    accumulated_content: str = Field(..., description="The full concatenated text including intermediate thoughts.")
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list, description="Tools executed during this turn.")
    session_id: str
    usage: UsageInfo = Field(default_factory=UsageInfo)

    def __str__(self) -> str:
        return self.accumulated_content


__all__ = [
    "Model",
    "ModelResponse",
    "ModelStreamChunk",
    "ModelUsage",
    "ModelConfig",
    "LiteLLMModel",
    "ApprovalStatus",
    "ApprovalRequest",
    "ApprovalAuditEntry",
    "UsageInfo",
    "AgentResponse",
]
