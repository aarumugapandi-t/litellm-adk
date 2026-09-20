# Build a Production-Ready Python Agent Framework on Top of LiteLLM

You are a senior AI infrastructure engineer. Design and implement a modular, extensible, production-oriented **Python Agent Framework** built on top of the `litellm` Python package.

The framework should allow developers to create configurable AI agents without rebuilding the core agent loop, memory, tools, vector search, human-in-the-loop, or model integration for every project.

The framework must be **provider-agnostic**, **model-agnostic**, and **storage-agnostic** wherever practical.

---

# 1. Primary Goal

Build a framework where an agent can be created approximately like:

```python
agent = Agent(
    name="researcher",
    model="openai/gpt-5",
    system_prompt="You are a research assistant.",
    tools=[search_tool, calculator_tool],
    memory=memory,
    vector_store=vector_store,
    human_in_the_loop=human_loop,
)

result = await agent.run(
    "Research quantum computing and summarize the important concepts."
)
```

The framework should handle:

1. LLM interaction through LiteLLM
2. Agent reasoning/execution loop
3. Tool calling
4. Conversation state
5. Short-term memory
6. Long-term memory
7. Vector-store retrieval
8. Human-in-the-loop interactions
9. Context management
10. Structured outputs
11. Streaming
12. Retries and error handling
13. Token/context management
14. Observability
15. Agent configuration
16. Middleware/hooks
17. Extensibility
18. Persistence
19. Multi-agent support
20. Async-first execution

Do not tightly couple the framework to OpenAI.

LiteLLM must be the abstraction responsible for communicating with LLM providers.

---

# 2. Design Philosophy

Follow these principles:

* Python-first
* Async-first
* Type-safe
* Modular
* Provider-agnostic
* Storage-agnostic
* Dependency injection
* Explicit configuration
* Minimal magic
* Easy local development
* Production-ready architecture
* Testable components
* Pluggable implementations
* Clear separation of concerns

Avoid creating a giant `Agent` class containing every feature.

The `Agent` should orchestrate independent components.

---

# 3. Core Architecture

Design the framework around these major abstractions:

```text
Agent
│
├── Model
│   └── LiteLLM
│
├── Prompt / Context
│
├── Memory
│   ├── Working Memory
│   ├── Conversation Memory
│   └── Long-Term Memory
│
├── Vector Store
│   ├── Embedding
│   ├── Index
│   └── Retrieval
│
├── Tools
│   ├── Tool Registry
│   ├── Tool Executor
│   └── Tool Permissions
│
├── Human-in-the-Loop
│   ├── Approval
│   ├── Input Request
│   └── Intervention
│
├── Agent Loop
│   ├── Observe
│   ├── Decide
│   ├── Act
│   ├── Observe
│   └── Finish
│
├── Context Manager
│
├── Output Parser
│
├── Middleware
│
├── Events
│
├── Persistence
│
└── Observability
```

Keep these components independently replaceable.

---

# 4. Agent Configuration

Identify everything that should reasonably be configurable by the framework user.

The user should be able to configure at least:

## Identity

```python
name
description
version
```

## Model

```python
model
provider
api_key
temperature
top_p
max_tokens
reasoning_effort
timeout
max_retries
```

Use LiteLLM for model communication.

Do not implement provider-specific API clients inside the framework unless absolutely necessary.

---

# 5. Prompt Configuration

Support:

```python
system_prompt
developer_prompt
instructions
prompt_templates
dynamic_context
```

Allow prompts to be generated dynamically from runtime state.

Example:

```python
system_prompt=lambda ctx: f"""
You are assisting {ctx.user.name}.
Their current task is {ctx.task}.
"""
```

Support static and dynamic prompts.

---

# 6. Agent Behavior Configuration

The framework should allow users to configure:

```python
max_iterations
max_tool_calls
max_execution_time
stop_conditions
parallel_tool_calls
allow_recursion
```

The agent must never run indefinitely.

Provide safe defaults.

---

# 7. Tool System

Create a first-class tool abstraction.

Example:

```python
@tool
async def search_web(query: str) -> str:
    ...
```

The framework should automatically generate an LLM-compatible tool schema.

Each tool should support metadata such as:

```python
name
description
parameters
permissions
requires_approval
timeout
retry_policy
```

Support:

* synchronous tools
* asynchronous tools
* structured input
* structured output
* tool validation
* tool errors
* retries
* timeouts
* cancellation
* permissions
* human approval

---

# 8. Tool Execution

Separate:

```text
Tool Definition
       ↓
Tool Registry
       ↓
Tool Selection
       ↓
Permission Check
       ↓
Human Approval
       ↓
Tool Execution
       ↓
Tool Result
       ↓
Agent Context
```

Do not let the LLM directly execute arbitrary Python code.

All tools must go through the framework's executor.

---

# 9. Human-in-the-Loop

Create a generic human-in-the-loop interface.

The framework must support situations where the agent needs:

* approval
* clarification
* confirmation
* additional information
* intervention
* rejection
* escalation

Example:

```python
@tool(requires_approval=True)
async def send_email(...):
    ...
```

The framework should pause execution and emit an event such as:

```python
HumanApprovalRequired
```

A human can then respond:

```python
approve()
reject()
modify(...)
```

Support pluggable HITL implementations.

For example:

```python
HumanInTheLoop
ConsoleHumanLoop
CallbackHumanLoop
WebSocketHumanLoop
APIHumanLoop
```

Do not hard-code a UI.

---

# 10. Memory Architecture

Memory must be treated as multiple layers.

Implement:

## Working Memory

Temporary state for the current execution.

Example:

```text
current task
current plan
tool results
temporary variables
current observations
```

## Conversation Memory

Messages from the current and previous conversations.

Support:

```text
user
assistant
system
tool
developer
```

## Long-Term Memory

Information that should survive across sessions.

Examples:

```text
user preferences
facts
past decisions
important events
learned information
```

Define an interface:

```python
class MemoryStore(Protocol):
    async def get(...)
    async def add(...)
    async def update(...)
    async def delete(...)
    async def search(...)
```

Provide at least an in-memory implementation.

Make persistent storage pluggable.

---

# 11. Memory Policies

Do not blindly send all memory to the model.

Create a memory policy system.

Allow the developer to configure:

```python
memory_enabled
max_memory_items
memory_relevance_threshold
automatic_memory_extraction
memory_write_policy
memory_read_policy
```

Support strategies such as:

```text
recent
semantic
importance
hybrid
```

The agent should decide what memory is relevant to the current task.

---

# 12. Vector Store

Create a generic vector store interface.

Example:

```python
class VectorStore(Protocol):
    async def add(...)
    async def search(...)
    async def delete(...)
    async def get(...)
```

Support metadata:

```python
id
text
embedding
metadata
namespace
created_at
```

Create a generic embedding abstraction.

```python
class Embedder(Protocol):
    async def embed(text: str) -> list[float]:
        ...
```

Use LiteLLM where appropriate for embedding calls.

The vector store must be replaceable.

Design adapters for:

```text
InMemoryVectorStore
ChromaVectorStore
FAISSVectorStore
QdrantVectorStore
PGVectorStore
```

Do not make all adapters mandatory dependencies.

Use optional dependencies.

---

# 13. Retrieval-Augmented Generation

Support:

```text
query
↓
embedding
↓
vector search
↓
reranking/filtering
↓
context construction
↓
LLM
```

Allow configuration:

```python
top_k
similarity_threshold
metadata_filter
reranker
max_context_tokens
```

The retrieval system should be usable independently from the Agent.

---

# 14. Context Manager

Create a dedicated context manager.

Its responsibility is to build the model input from:

```text
System instructions
+
Developer instructions
+
Conversation history
+
Working memory
+
Long-term memory
+
Retrieved documents
+
Tool results
+
Current user input
```

The context manager must be aware of token limits.

Implement:

```python
ContextManager
ContextPolicy
ContextWindow
ContextItem
```

Support context strategies:

```text
truncate
summarize
compress
prioritize
retrieve
```

Never exceed the configured model context window.

---

# 15. Agent Execution Loop

Implement a clear execution loop.

Conceptually:

```text
User Input
    ↓
Build Context
    ↓
Call LLM
    ↓
Analyze Response
    ↓
Tool Call?
 ┌──┴──┐
Yes    No
 ↓      ↓
Execute  Final Response
Tool
 ↓
Add Result
 ↓
Build Context
 ↓
Call LLM
```

The loop must support:

* tool calls
* multiple tool calls
* parallel tools
* retries
* human intervention
* cancellation
* max iterations
* max execution time
* structured output
* streaming

Avoid implementing hidden chain-of-thought storage or exposing private reasoning.

Store only necessary execution state, decisions, tool calls, and results.

---

# 16. Planning

Planning should be optional.

Allow:

```python
planning=True
```

The framework may support:

```text
Planner
Task decomposition
Plan execution
Replanning
```

But do not force every agent to use a planner.

Create interfaces such as:

```python
Planner
Plan
PlanStep
```

---

# 17. Structured Output

Support:

```python
response_model=MyPydanticModel
```

Example:

```python
class ResearchResult(BaseModel):
    title: str
    summary: str
    sources: list[str]
```

The framework should validate model output.

If validation fails:

```text
LLM output
↓
Validation
↓
Failure
↓
Repair/retry
↓
Validation
```

Support both:

```text
plain text
structured JSON
Pydantic models
```

---

# 18. Streaming

Support:

```python
async for event in agent.stream(...):
    ...
```

Define events such as:

```python
TextDelta
ToolCallStarted
ToolCallCompleted
ToolCallFailed
HumanApprovalRequired
MemoryRetrieved
MemoryCreated
AgentStarted
AgentFinished
AgentError
```

Use an event-driven architecture.

---

# 19. Event System

Create a generic event bus.

Example:

```python
class Event:
    type: str
    timestamp: datetime
    run_id: str
    agent_id: str
    data: dict
```

Allow users to subscribe:

```python
agent.on("tool.completed", handler)
```

Events should be useful for:

* UI
* WebSocket streaming
* logging
* monitoring
* debugging
* auditing

---

# 20. Middleware

Implement middleware around agent execution.

Example:

```python
class Middleware(Protocol):

    async def before_run(...):
        ...

    async def after_run(...):
        ...

    async def on_error(...):
        ...
```

Potential middleware:

```text
LoggingMiddleware
MetricsMiddleware
TracingMiddleware
RateLimitMiddleware
SecurityMiddleware
CostMiddleware
```

Allow developers to create their own middleware.

---

# 21. Security

Treat tools and external actions as potentially dangerous.

Implement:

```text
tool permissions
approval requirements
timeouts
resource limits
input validation
output validation
secret isolation
```

Do not expose API keys to prompts.

Do not allow arbitrary tool execution.

Support permission policies such as:

```python
ToolPermission.READ
ToolPermission.WRITE
ToolPermission.EXTERNAL
ToolPermission.DANGEROUS
```

---

# 22. Persistence

Separate runtime state from persistence.

Create interfaces for:

```python
SessionStore
RunStore
MemoryStore
```

Example:

```python
await session_store.save(session)
session = await session_store.get(session_id)
```

Provide in-memory implementations first.

Design persistent adapters without forcing a database dependency.

---

# 23. Sessions

An agent should support multiple sessions.

Example:

```python
session = await agent.create_session(user_id="123")

result = await agent.run(
    "Remember that I prefer concise answers.",
    session=session
)
```

Session state should include:

```text
session_id
user_id
agent_id
conversation
metadata
created_at
updated_at
```

---

# 24. Multi-Agent Architecture

Design the framework so an Agent can be used as a tool by another Agent.

Example:

```text
Supervisor Agent
    ├── Research Agent
    ├── Coding Agent
    └── Review Agent
```

Create abstractions such as:

```python
AgentTool
AgentTeam
Supervisor
```

Do not make multi-agent behavior mandatory.

---

# 25. Configuration Model

Use Pydantic configuration models.

Example:

```python
AgentConfig(
    name="researcher",
    model="openai/gpt-5",
    temperature=0.2,
    max_iterations=10,
    memory=MemoryConfig(...),
    retrieval=RetrievalConfig(...),
    execution=ExecutionConfig(...),
)
```

Configuration should be serializable.

Support loading from:

```text
Python
YAML
JSON
environment variables
```

Do not require configuration files for simple use cases.

---

# 26. Model Configuration

Create:

```python
ModelConfig
```

with options including:

```text
model
temperature
top_p
max_tokens
reasoning_effort
timeout
max_retries
api_base
extra_headers
```

Use LiteLLM as the model gateway.

The framework should expose a clean interface:

```python
model.generate(...)
model.stream(...)
```

Internally this should use LiteLLM.

---

# 27. Cost and Token Tracking

Track:

```text
input tokens
output tokens
total tokens
estimated cost
latency
number of model calls
number of tool calls
```

Create:

```python
Usage
RunMetrics
CostTracker
```

Do not make billing/provider-specific logic part of the core architecture.

---

# 28. Error Handling

Create explicit framework exceptions:

```text
AgentError
ModelError
ToolError
ToolTimeoutError
ToolPermissionError
MemoryError
VectorStoreError
HumanInterventionError
ContextLimitError
OutputValidationError
MaxIterationsError
ExecutionTimeoutError
```

Errors should contain useful metadata.

Never silently swallow errors.

---

# 29. Cancellation

Every long-running operation should support cancellation.

Example:

```python
task = asyncio.create_task(
    agent.run(...)
)

task.cancel()
```

Tools should have timeout and cancellation support.

---

# 30. Retry Policies

Implement configurable retry behavior.

Example:

```python
RetryPolicy(
    max_attempts=3,
    exponential_backoff=True,
)
```

Retry only appropriate failures.

Do not retry irreversible operations blindly.

---

# 31. Observability

Design hooks for:

```text
logging
metrics
tracing
OpenTelemetry
```

The framework should not require a specific observability vendor.

Provide a simple default logger.

---

# 32. Package Structure

Use a structure similar to:

```text
agent_framework/
│
├── __init__.py
│
├── agent/
│   ├── agent.py
│   ├── config.py
│   ├── loop.py
│   ├── state.py
│   └── result.py
│
├── models/
│   ├── base.py
│   ├── litellm.py
│   └── config.py
│
├── tools/
│   ├── base.py
│   ├── decorator.py
│   ├── registry.py
│   ├── executor.py
│   └── permissions.py
│
├── memory/
│   ├── base.py
│   ├── working.py
│   ├── conversation.py
│   ├── long_term.py
│   ├── policy.py
│   └── stores/
│
├── vector/
│   ├── base.py
│   ├── embeddings.py
│   ├── retriever.py
│   └── stores/
│
├── context/
│   ├── manager.py
│   ├── policy.py
│   └── tokenizer.py
│
├── human/
│   ├── base.py
│   ├── console.py
│   └── callbacks.py
│
├── planning/
│   ├── base.py
│   └── planner.py
│
├── sessions/
│   ├── base.py
│   └── memory.py
│
├── events/
│   ├── base.py
│   ├── bus.py
│   └── types.py
│
├── middleware/
│   ├── base.py
│   └── logging.py
│
├── persistence/
│   ├── sessions.py
│   └── runs.py
│
├── observability/
│   ├── metrics.py
│   ├── tracing.py
│   └── usage.py
│
├── exceptions.py
│
└── utils/
```

Adjust the structure if you identify a better architecture, but preserve clear separation of responsibilities.

---

# 33. Dependency Management

Use modern Python packaging.

Target:

```text
Python 3.11+
```

Core dependencies should be minimal.

Required core dependency:

```text
litellm
pydantic
```

Optional integrations should use extras:

```text
pip install agent-framework[chroma]
pip install agent-framework[qdrant]
pip install agent-framework[postgres]
pip install agent-framework[observability]
```

Do not force every vector database or integration into the base installation.

---

# 34. Developer Experience

The simplest agent should require very little code.

Example:

```python
from agent_framework import Agent

agent = Agent(
    model="openai/gpt-5",
    system_prompt="You are a helpful assistant."
)

response = await agent.run("Explain recursion.")
print(response.text)
```

Tool example:

```python
from agent_framework import tool

@tool
async def calculate(expression: str) -> str:
    ...
```

Memory example:

```python
agent = Agent(
    model="openai/gpt-5",
    memory=memory_store,
)
```

RAG example:

```python
agent = Agent(
    model="openai/gpt-5",
    vector_store=vector_store,
    retrieval=RetrievalConfig(top_k=5),
)
```

HITL example:

```python
agent = Agent(
    model="openai/gpt-5",
    human_in_the_loop=human_loop,
)
```

---

# 35. Advanced Configuration

Everything reasonable should be configurable without modifying framework source code.

Expose configuration for:

```text
model
prompts
generation parameters
tools
tool permissions
tool retries
tool timeouts
agent iteration limits
execution timeout
memory
memory policy
vector store
embedding model
retrieval
reranking
context management
structured output
human approval
planning
sessions
persistence
middleware
events
logging
metrics
tracing
cost limits
rate limits
security policies
```

However, do not expose internal implementation details unnecessarily.

Follow the principle:

> Configuration should control behavior, not implementation.

---

# 36. Agent Lifecycle

Define a predictable lifecycle:

```text
CREATED
   ↓
READY
   ↓
RUNNING
   ↓
WAITING_FOR_HUMAN
   ↓
RUNNING
   ↓
COMPLETED
```

Possible terminal states:

```text
COMPLETED
FAILED
CANCELLED
TIMEOUT
MAX_ITERATIONS
```

Expose lifecycle events.

---

# 37. Agent Result

Create a structured result:

```python
AgentResult(
    text="...",
    structured=None,
    run_id="...",
    session_id="...",
    usage=...,
    tool_calls=[...],
    metadata={...},
)
```

Do not return only a raw string.

Provide convenience behavior so users can still do:

```python
print(result)
```

---

# 38. Testing

Create comprehensive tests.

Test:

* basic agent execution
* LiteLLM integration
* tool registration
* tool execution
* tool failures
* tool timeout
* tool permissions
* memory
* vector retrieval
* context construction
* context limits
* structured outputs
* retries
* cancellation
* human approval
* event streaming
* middleware
* sessions
* persistence interfaces
* multi-agent execution
* max iterations
* execution timeout

Use mocks/fakes for LLM calls.

Tests must not require paid API calls.

---

# 39. Example Applications

Create examples:

```text
examples/
├── basic_agent.py
├── tools.py
├── streaming.py
├── memory.py
├── rag.py
├── structured_output.py
├── human_in_the_loop.py
├── multi_agent.py
└── custom_vector_store.py
```

Each example should demonstrate one concept clearly.

---

# 40. Documentation

Create documentation explaining:

1. Installation
2. Quick start
3. Agent configuration
4. Models
5. Tools
6. Memory
7. Vector stores
8. RAG
9. Human-in-the-loop
10. Streaming
11. Structured outputs
12. Sessions
13. Middleware
14. Events
15. Persistence
16. Multi-agent systems
17. Custom integrations
18. Production deployment

Include architecture diagrams in the documentation using Mermaid where appropriate.

---

# 41. Important Architectural Rule

Do not make the Agent responsible for everything.

Prefer:

```python
Agent
 ├── AgentLoop
 ├── Model
 ├── ToolRegistry
 ├── Memory
 ├── ContextManager
 ├── Retriever
 ├── HumanLoop
 ├── EventBus
 └── Middleware
```

over:

```python
Agent
 └── 3000 lines of implementation
```

Every major capability must have an interface/protocol.

---

# 42. Extensibility

A developer must be able to implement:

```python
class MyVectorStore(VectorStore):
    ...
```

or:

```python
class MyMemoryStore(MemoryStore):
    ...
```

or:

```python
class MyHumanLoop(HumanInTheLoop):
    ...
```

without modifying framework internals.

Prefer Python `Protocol` or abstract base classes where appropriate.

---

# 43. Framework vs Application Boundary

The framework should provide primitives, not application-specific behavior.

Do not include:

* hardcoded business logic
* hardcoded database schemas
* hardcoded web UI
* hardcoded authentication
* hardcoded SaaS logic
* hardcoded provider-specific behavior

The framework should make these integrations possible.

---

# 44. Safety and Reliability

The framework must protect against:

```text
infinite agent loops
unbounded token usage
unbounded tool execution
tool recursion
irreversible actions without approval
context overflow
failed tool calls
model failures
network failures
duplicate operations
```

Use:

```text
timeouts
budgets
iteration limits
permission checks
idempotency where applicable
approval gates
validation
```

---

# 45. Final Deliverables

Produce a complete working repository containing:

```text
source code
tests
examples
README
documentation
pyproject.toml
configuration examples
architecture documentation
```

The framework must be installable and runnable.

Before finishing:

1. Run the test suite.
2. Fix all failures.
3. Run static/type checks where configured.
4. Verify the basic example works.
5. Verify memory works.
6. Verify tool calling works.
7. Verify streaming works.
8. Verify HITL works.
9. Verify vector retrieval works through an in-memory implementation.
10. Verify the framework can operate without any specific vector database.
11. Verify the framework can operate with different LiteLLM-supported model providers.

---

# 46. Implementation Priority

Implement in this order:

### Phase 1 — Core

```text
Agent
AgentConfig
LiteLLMModel
AgentLoop
AgentResult
Exceptions
```

### Phase 2 — Tools

```text
Tool
ToolRegistry
ToolExecutor
Tool permissions
```

### Phase 3 — Context

```text
ContextManager
ContextPolicy
Token management
```

### Phase 4 — Memory

```text
WorkingMemory
ConversationMemory
MemoryStore
MemoryPolicy
```

### Phase 5 — Retrieval

```text
Embedder
VectorStore
Retriever
RAG
```

### Phase 6 — Human Interaction

```text
HumanInTheLoop
Approval
Intervention
```

### Phase 7 — Events and Streaming

```text
EventBus
Agent events
Streaming
```

### Phase 8 — Production Features

```text
Sessions
Persistence
Middleware
Usage tracking
Cost tracking
Retries
Timeouts
Observability
```

### Phase 9 — Multi-Agent

```text
AgentTool
AgentTeam
Supervisor
```

---

# 47. Expected Mental Model

The final framework should make this possible:

```text
                    ┌──────────────┐
                    │    Agent     │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  Agent Loop  │
                    └──────┬───────┘
                           │
       ┌───────────────────┼───────────────────┐
       │                   │                   │
┌──────▼──────┐     ┌──────▼──────┐     ┌──────▼──────┐
│    Model    │     │   Context   │     │    Tools    │
│  LiteLLM    │     │   Manager   │     │   Registry  │
└─────────────┘     └──────┬──────┘     └──────┬──────┘
                            │                   │
                     ┌──────▼──────┐     ┌──────▼──────┐
                     │   Memory    │     │    Human    │
                     │             │     │     Loop    │
                     └──────┬──────┘     └─────────────┘
                            │
                     ┌──────▼──────┐
                     │ VectorStore │
                     │  Retrieval  │
                     └─────────────┘
```

The core idea is:

> **The Agent orchestrates. Components specialize. Interfaces enable replacement. LiteLLM handles model-provider abstraction.**

Build the framework around this principle and avoid unnecessary complexity until the core abstractions are correct.
