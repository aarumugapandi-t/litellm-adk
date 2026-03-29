# LiteLLM ADK (Agent Development Kit) v0.3.0

The LiteLLM ADK is an agent orchestration framework designed for stability, safety, and seamless multi-provider portability. It provides a standardized interface for managing tool execution, session persistence, and multi-agent coordination across various LLM providers (including OpenAI, Anthropic, OCI, and Bedrock).

## Core Capabilities

- **Human-In-The-Loop (HITL)**: Native support for pausing execution for manual approval or parameter modification before tool execution.
- **Multi-Agent Orchestration**: Standardized handoff protocols for transferring context and control between specialized agents.
- **Resilient Memory Architecture**: Pluggable storage backends (In-Memory, File, MongoDB) with dedicated session management.
- **Semantic Memory (RAG)**: Integrated vector store search for automated context retrieval.
- **Provider Portability**: Automatic parameter filtering to ensure cross-provider compatibility and resilience.

## Installation

```bash
pip install litellm-adk
```

## Quick Start

### Basic Agent Initialization

The ADK manages session history and provider routing automatically.

```python
from litellm_adk import LiteLLMAgent

agent = LiteLLMAgent(
    model="gpt-4o",
    system_prompt="You are a helpful assistant."
)

# Synchronous invocation
response = agent.invoke("Hello! My name is Alice.")
print(response.content)

# Session persistence is maintained internally
print(agent.invoke("What is my name?").content) # "Your name is Alice."
```

### Tool Registration

Python functions can be converted into LLM-compatible tools using the `@tool` decorator.

```python
from litellm_adk import LiteLLMAgent, tool

@tool
def process_refund(user_id: str, amount: float):
    """Processes a refund for a specific user."""
    return f"Successfully refunded ${amount} to user {user_id}."

agent = LiteLLMAgent(tools=[process_refund])
agent.invoke("Refund $50 to user 123")
```

## Safety and Control: Human-In-The-Loop

For sensitive operations, tools can be configured to require explicit human approval. The agent will yield a `requires_approval` event and wait for a decision before proceeding.

```python
@tool(requires_approval=True)
def delete_database(db_name: str):
    """Irreversible database operation."""
    return f"Database {db_name} deleted."

# In a streaming context:
for event in agent.stream("Delete the 'prod' DB"):
    if event["type"] == "requires_approval":
        # Handle the approval request in your application logic
        print(f"Approval Required for: {event['pending_approvals']}")
```

## Long-Term Memory: Semantic Search (RAG)

Connect a Vector Store to enable automated context retrieval.

```python
from litellm_adk.memory.backends.postgres import PostgresVectorStore

vector_store = PostgresVectorStore(connection_string="...")
agent = LiteLLMAgent(vector_store=vector_store)

# The agent retrieves relevant documents automatically before generating a response
agent.invoke("What are the core specifications of Project Chimera?")
```

## Distributed Logic: Agent Handoffs

Transfer execution logic between specialist agents while maintaining context.

```python
billing_specialist = LiteLLMAgent(name="billing", tools=[process_refund])
triage_agent = LiteLLMAgent(name="triage", sub_agents=[billing_specialist])

# The triage agent will programmatically transfer to the billing specialist
triage_agent.invoke("I need to process a refund.")
```

## Configuration

The framework uses `pydantic-settings` for environment-based configuration.

- `ADK_MODEL`: Default LLM model identifier.
- `ADK_API_KEY`: Default provider API key.
- `ADK_BASE_URL`: Global API base URL.
- `ADK_LOG_LEVEL`: System logging level (DEBUG, INFO, ERROR).

## Documentation and Examples
Reference implementations can be found in the [examples directory](./examples/):
- [Multi-agent implementation](./examples/multiagent_demo.py)
- [HITL streaming logic](./examples/streaming_hitl_demo.py)
- [Vector store integration](./examples/vector_memory_demo.py)

## License
MIT
