from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    """
    Application settings, loaded from environment variables or .env file.
    """
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        extra="ignore",
        env_prefix="ADK_"  # Support ADK_ prefixed env vars
    )

    # Core LLM Settings
    model: str = Field(default="gpt-4o", description="The model to use.")
    api_key: Optional[str] = Field(default=None, description="Global API key.")
    base_url: Optional[str] = Field(default=None, description="Global base URL.")
    
    # Provider-specific keys (fallback)
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    cohere_api_key: Optional[str] = None
    
    # Logging & Observability
    log_level: str = Field(default="INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
    log_format: str = Field(default="text", description="Log format (text or json)")
    enable_telemetry: bool = Field(default=False, description="Enable OpenTelemetry tracing")
    otel_exporter_endpoint: Optional[str] = Field(default=None, description="OTLP exporter endpoint")

    # Tool Execution
    sequential_execution: bool = Field(default=True, description="Default sequential tool execution mode.")
    tool_timeout: float = Field(default=30.0, description="Maximum execution time (seconds) for a single tool call.")
    tool_error_policy: str = Field(default="raise", description="Policy for tool failures: 'raise' or 'return_to_llm'.")
    max_tokens: int = Field(default=4096, description="Default max tokens for LLM responses.")

settings = Settings()
