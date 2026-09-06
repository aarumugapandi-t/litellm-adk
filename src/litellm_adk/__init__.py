"""LiteLLM ADK - Production-Ready Multi-Agent Framework on top of LiteLLM."""

# Core orchestrator and configurations
from .agent import (
    Agent,
    AgentConfig,
    AgentLifecycleState,
    AgentLoop,
    AgentResult,
    AgentState,
    ExecutionConfig,
    LiteLLMAgent,
    OutputParser,
    ToolCallRecord,
)

# Models
from .models import (
    LiteLLMModel,
    Model,
    ModelConfig,
    ModelResponse,
    ModelStreamChunk,
    ModelUsage,
)

# Tools
from .tools import (
    Tool,
    ToolExecutor,
    ToolPermission,
    ToolRegistry,
    generate_tool_schema,
    tool,
    tool_registry,
)

# Multi-layer Memory
from .memory import (
    BaseMemory,
    ConversationMemory,
    FileMemory,
    InMemoryMemory,
    InMemoryStore,
    LongTermMemory,
    MemoryPolicy,
    MemoryStore,
    MemoryStrategy,
    MongoDBMemory,
    SQLAlchemyMemory,
    WorkingMemory,
)

# Vector Store & RAG
from .vector import (
    Embedder,
    InMemoryVectorStore,
    LiteLLMEmbedder,
    RetrievalConfig,
    Retriever,
    SimpleEmbedder,
    VectorItem,
    VectorSearchResult,
    VectorStore,
)

# Context Management
from .context import (
    ContextItem,
    ContextManager,
    ContextPolicy,
    ContextStrategy,
    ContextWindow,
)

# Human in the Loop
from .human import (
    ApprovalDecision,
    ApprovalManager,
    BaseApprovalManager,
    CallbackHumanLoop,
    ConsoleHumanLoop,
    HumanInTheLoop,
    InMemoryApprovalManager,
    SQLiteApprovalManager,
)

# Events & Streaming
from .events import (
    AgentErrorEvent,
    AgentFinished,
    AgentStarted,
    Event,
    EventBus,
    HumanApprovalRequired,
    MemoryCreated,
    MemoryRetrieved,
    TextDelta,
    ToolCallCompleted,
    ToolCallFailed,
    ToolCallStarted,
)

# Middleware
from .middleware import (
    LoggingMiddleware,
    Middleware,
    MiddlewarePipeline,
    PIIScrubbingMiddleware,
)

# Multi-Agent
from .multiagent import (
    AgentTeam,
    AgentTool,
    Supervisor,
    agent_as_tool,
)

# Sessions & Persistence
from .persistence import (
    InMemoryRunStore,
    InMemorySessionStore,
    RunStore,
    SessionStore,
)
from .session import Session

# Observability
from .config.settings import settings
from .observability import (
    CostTracker,
    RunMetrics,
    Usage,
    adk_logger,
    get_tracer,
    setup_litellm_telemetry,
    trace_span,
)

# Security & Caching
from .caching import CacheManager
from .security import PIIScrubber

# Visual Workflow Platform & Server
from .workflow import (
    WorkflowDefinition,
    WorkflowNode,
    WorkflowEdge,
    WorkflowSettings,
    WorkflowStatus,
    ExecutionState,
    ExecutionStatus,
    WorkflowGraph,
    WorkflowEngine,
    node_registry,
)
from .server import serve

# Exceptions
from .exceptions import (
    AgentError,
    ContextLimitError,
    ExecutionTimeoutError,
    HumanInterventionError,
    MaxIterationsError,
    MemoryError,
    ModelError,
    OutputValidationError,
    ToolError,
    ToolPermissionError,
    ToolTimeoutError,
    VectorStoreError,
)

# Initialize opentelemetry automatically
setup_litellm_telemetry()

__all__ = [
    # Core Agent
    "Agent",
    "LiteLLMAgent",
    "AgentConfig",
    "ExecutionConfig",
    "AgentLoop",
    "AgentResult",
    "ToolCallRecord",
    "AgentState",
    "AgentLifecycleState",
    "OutputParser",
    # Models
    "Model",
    "ModelConfig",
    "LiteLLMModel",
    "ModelResponse",
    "ModelStreamChunk",
    "ModelUsage",
    # Tools
    "tool",
    "tool_registry",
    "Tool",
    "ToolRegistry",
    "ToolExecutor",
    "ToolPermission",
    "generate_tool_schema",
    # Context
    "ContextManager",
    "ContextPolicy",
    "ContextStrategy",
    "ContextItem",
    "ContextWindow",
    # Memory
    "BaseMemory",
    "MemoryStore",
    "WorkingMemory",
    "ConversationMemory",
    "LongTermMemory",
    "InMemoryStore",
    "MemoryPolicy",
    "MemoryStrategy",
    "InMemoryMemory",
    "FileMemory",
    "MongoDBMemory",
    "SQLAlchemyMemory",
    # Vector & RAG
    "VectorStore",
    "VectorItem",
    "VectorSearchResult",
    "Embedder",
    "LiteLLMEmbedder",
    "SimpleEmbedder",
    "Retriever",
    "RetrievalConfig",
    "InMemoryVectorStore",
    # HITL
    "HumanInTheLoop",
    "ApprovalDecision",
    "ConsoleHumanLoop",
    "CallbackHumanLoop",
    "ApprovalManager",
    "BaseApprovalManager",
    "InMemoryApprovalManager",
    "SQLiteApprovalManager",
    # Events
    "EventBus",
    "Event",
    "AgentStarted",
    "AgentFinished",
    "AgentErrorEvent",
    "TextDelta",
    "ToolCallStarted",
    "ToolCallCompleted",
    "ToolCallFailed",
    "HumanApprovalRequired",
    "MemoryRetrieved",
    "MemoryCreated",
    # Middleware
    "Middleware",
    "MiddlewarePipeline",
    "LoggingMiddleware",
    "PIIScrubbingMiddleware",
    # Multi-Agent
    "AgentTool",
    "agent_as_tool",
    "AgentTeam",
    "Supervisor",
    # Sessions & Persistence
    "Session",
    "SessionStore",
    "RunStore",
    "InMemorySessionStore",
    "InMemoryRunStore",
    # Observability
    "settings",
    "adk_logger",
    "get_tracer",
    "setup_litellm_telemetry",
    "trace_span",
    "Usage",
    "RunMetrics",
    "CostTracker",
    # Security & Caching
    "CacheManager",
    "PIIScrubber",
    # Exceptions
    "AgentError",
    "ModelError",
    "ToolError",
    "ToolTimeoutError",
    "ToolPermissionError",
    "MemoryError",
    "VectorStoreError",
    "HumanInterventionError",
    "ContextLimitError",
    "OutputValidationError",
    "MaxIterationsError",
    "ExecutionTimeoutError",
    # Visual Workflow Platform & Server
    "WorkflowDefinition",
    "WorkflowNode",
    "WorkflowEdge",
    "WorkflowSettings",
    "WorkflowStatus",
    "ExecutionState",
    "ExecutionStatus",
    "WorkflowGraph",
    "WorkflowEngine",
    "node_registry",
    "serve",
]
