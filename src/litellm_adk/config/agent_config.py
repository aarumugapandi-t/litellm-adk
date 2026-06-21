from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any, Union

class AgentConfig(BaseModel):
    """
    Declarative configuration model for LiteLLMAgent.
    """
    name: str = Field(default="Assistant", description="Name of the agent.")
    description: str = Field(default="A helpful AI assistant.", description="Description of the agent's role.")
    model: Optional[str] = Field(default=None, description="The LLM model string to use.")
    api_key: Optional[str] = Field(default=None, description="API key for the model.")
    base_url: Optional[str] = Field(default=None, description="Base URL for the provider.")
    system_prompt: str = Field(default="You are a helpful assistant.", description="The system prompt.")
    
    # Advanced features
    tools: Optional[List[Union[str, Dict[str, Any], Any]]] = Field(
        default=None, 
        description="List of tool names, dictionaries, or callables."
    )
    sub_agents: Optional[List[Any]] = Field(
        default=None, 
        description="List of sub-agent objects or AgentConfigs."
    )
    max_context_tokens: Optional[int] = Field(default=None, description="Token limit before truncation.")
    fallbacks: Optional[List[Union[str, Dict[str, Any]]]] = Field(default=None, description="Failover configurations.")
    
    # Flags
    handoff_context: str = Field(default="clean", description="'clean', 'user_only', or 'full'")
    handoff_memory: str = Field(default="ephemeral", description="'ephemeral' or 'persist'")
    use_global_tools: bool = Field(default=False, description="Whether to include all global tools.")
    parallel_tool_calls: bool = Field(default=True, description="Whether to allow parallel tool execution.")
    scrub_pii: bool = Field(default=False, description="Whether to scrub PII from messages before sending to LLM.")

    # Arbitrary kwargs for litellm
    extra_kwargs: Dict[str, Any] = Field(default_factory=dict, description="Extra litellm completion kwargs.")
    
    model_config = ConfigDict(extra="allow")
