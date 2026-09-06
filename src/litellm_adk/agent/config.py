"""Agent configuration models."""

import os
from typing import Any, Callable, Dict, List, Optional, Type, Union
from pydantic import BaseModel, ConfigDict, Field
import yaml

from ..models.config import ModelConfig


class ExecutionConfig(BaseModel):
    """Configuration governing execution loop constraints and behaviors."""

    max_iterations: int = Field(default=25, ge=1, description="Maximum loop iterations before terminating.")
    max_tool_calls: int = Field(default=50, ge=1, description="Maximum total tool calls allowed per run.")
    max_execution_time: Optional[float] = Field(default=None, description="Max execution time in seconds.")
    parallel_tool_calls: bool = Field(default=True, description="Execute parallel tool calls concurrently.")
    allow_recursion: bool = Field(default=False, description="Allow an agent to invoke itself recursively.")
    stop_conditions: List[str] = Field(default_factory=list, description="Custom stop phrases or conditions.")


class AgentConfig(BaseModel):
    """Declarative configuration model for an Agent."""

    # Identity
    name: str = Field(default="Assistant", description="Name of the agent.")
    description: str = Field(default="A helpful AI assistant.", description="Description of the agent's role.")
    version: str = Field(default="1.0.0", description="Version of the agent configuration.")

    # Model configuration
    model: Optional[Union[str, ModelConfig]] = Field(default=None, description="Model string or ModelConfig instance.")
    api_key: Optional[str] = Field(default=None, description="API key for the model.")
    base_url: Optional[str] = Field(default=None, description="Custom base URL / proxy endpoint.")
    temperature: float = Field(default=0.7, description="Model sampling temperature.")
    max_tokens: Optional[int] = Field(default=None, description="Maximum output tokens.")
    fallbacks: Optional[List[Union[str, Dict[str, Any]]]] = Field(default=None, description="Fallback model options.")

    # Prompts
    system_prompt: Union[str, Callable[[Any], str]] = Field(
        default="You are a helpful assistant.",
        description="System prompt string or callable generating prompt from context."
    )
    developer_prompt: Optional[str] = Field(default=None, description="Developer instruction prompt.")
    instructions: Optional[str] = Field(default=None, description="Specific run instructions.")

    # Execution controls
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    max_context_tokens: Optional[int] = Field(default=None, description="Context window limit.")
    planning: bool = Field(default=False, description="Enable automated task planning decomposition.")

    # Tools and multi-agent
    tools: Optional[List[Union[str, Dict[str, Any], Any]]] = Field(
        default=None,
        description="List of tool names, definitions, functions, or Tool instances."
    )
    sub_agents: Optional[List[Any]] = Field(
        default=None,
        description="Sub-agent instances, configs, or specs."
    )
    use_global_tools: bool = Field(default=False, description="Include tools from global ToolRegistry.")

    # Safety and middleware flags
    scrub_pii: bool = Field(default=False, description="Scrub PII from outgoing LLM payloads.")
    handoff_context: str = Field(default="clean", description="Context handoff strategy ('clean', 'user_only', 'full').")
    handoff_memory: str = Field(default="ephemeral", description="Memory handoff mode ('ephemeral', 'persist').")

    # Dynamic extra kwargs
    extra_kwargs: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary extra kwargs for LiteLLM.")

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    @classmethod
    def from_yaml(cls, yaml_content_or_path: str) -> "AgentConfig":
        """Loads configuration from a YAML string or file path."""
        if os.path.exists(yaml_content_or_path):
            with open(yaml_content_or_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        else:
            data = yaml.safe_load(yaml_content_or_path)
        return cls(**(data or {}))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentConfig":
        """Loads configuration from a Python dictionary."""
        return cls(**data)
