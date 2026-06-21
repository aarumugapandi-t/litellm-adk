# LiteLLM ADK (Agent Development Kit)

> A robust orchestration framework for building, scaling, and observing provider-agnostic autonomous LLM applications.

## Overview

Building autonomous AI agents that are resilient, observable, and secure is notoriously difficult. The **LiteLLM Agent Development Kit (ADK)** abstracts away the underlying complexity of managing session states, cross-provider compatibility, and tool execution lifecycles. 

By acting as an orchestration layer on top of the industry-standard `litellm` router, the ADK enables engineering teams to write business logic once and seamlessly deploy it across OpenAI, Anthropic, Groq, AWS Bedrock, and custom proxies. Out of the box, it provides enterprise-grade observability, persistent memory architectures, and strict data sanitization protocols.

## Key Value Propositions

- **Provider Agnosticism**: Standardize inputs and outputs across 100+ language models without tightly coupling to vendor-specific SDKs.
- **Resilient State Management**: Pluggable persistent memory interfaces (In-Memory, SQL, MongoDB) to maintain conversational context across distributed system architectures.
- **Execution Guardrails**: Native authorization interceptors for Human-in-the-Loop (HITL) workflows and automatic Personally Identifiable Information (PII) masking.
- **Declarative Topologies**: Define and orchestrate complex, multi-agent communication networks entirely through YAML configuration files.
- **Enterprise Observability**: Zero-configuration OpenTelemetry (OTel) bindings for distributed tracing, latency monitoring, and token economics.

---

## Installation

The ADK is available via standard Python package managers:

```bash
pip install litellm-adk
```

You will need to provide the authentication credentials for your target LLM provider (e.g., `OPENAI_API_KEY`, `GROQ_API_KEY`) via environment variables.

---

## Quick Start

The ADK handles session initialization, history management, and API routing implicitly.

```python
import asyncio
from litellm_adk import LiteLLMAgent

async def main():
    # Initialize the agent with a target model and system instruction
    agent = LiteLLMAgent(
        model="groq/qwen/qwen3-32b",
        system_prompt="You are a specialized financial assistant."
    )

    # Context is automatically tracked and maintained internally
    response_one = await agent.ainvoke("My name is Alice and my account ID is 402A.")
    print(response_one.content)

    response_two = await agent.ainvoke("What is my account ID?")
    print(response_two.content) # Output: "Your account ID is 402A."

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Core Concepts & Usage

### 1. Data Privacy & Sanitization
In enterprise deployments, sensitive user data should not be forwarded to third-party APIs. The ADK includes an interceptor layer that scrubs sensitive patterns before transmission.

```python
agent = LiteLLMAgent(
    model="openai/gpt-4o",
    scrub_pii=True # Activates the pre-flight sanitization pipeline
)

# The payload transmitted to the LLM will be masked: "My SSN is [SSN_REDACTED]"
response = await agent.ainvoke("My SSN is 123-45-6789.")
```

### 2. Safe Tool Execution (Human-in-the-Loop)
Agents often require access to mutable infrastructure (e.g., executing SQL, refunding transactions). The ADK allows functions to be flagged with authorization requirements, seamlessly yielding execution control back to the client application for human validation.

```python
from litellm_adk import tool_registry, LiteLLMAgent

@tool_registry.register(requires_approval=True)
def execute_transaction(account_id: str, amount: float):
    """Executes a financial transaction."""
    pass

async def transaction_workflow():
    agent = LiteLLMAgent(model="groq/qwen/qwen3-32b", tools=["execute_transaction"])
    
    # Asynchronous generators automatically pause execution and yield authorization requests
    async for event in agent.astream("Transfer $50 to account 99X"):
        if event["type"] == "requires_approval":
            print(f"Authorization requested for tool: {event['pending_approvals']}")
            # Await client/UI authorization before resuming the generator...
```

### 3. Multi-Agent Topologies
Defining multi-agent hierarchies natively in Python can result in fragile, tightly coupled codebases. The ADK allows architects to define agent swarms declaratively.

```yaml
# support_network.yaml
name: TriageAgent
model: groq/qwen/qwen3-32b
system_prompt: "Route hardware issues to the HardwareAgent."

sub_agents:
  - name: HardwareAgent
    model: groq/qwen/qwen3-32b
    system_prompt: "You resolve server hardware anomalies."
    tools: ["reboot_server"]
```

```python
# Instantiates the entire hierarchy and resolves dependency injections
agent = LiteLLMAgent.from_yaml("support_network.yaml")
```

### 4. Performance Optimization (Semantic Caching)
To drastically reduce token costs and inference latency, the ADK integrates directly with Redis and Dragonfly for semantic vector caching.

```python
from litellm_adk.caching import CacheManager

# Intercepts semantically identical queries and serves them in <1ms
CacheManager.enable_redis_cache(host="127.0.0.1", port=6379, semantic=True)
```

### 5. Observability & Tracing
The framework provides drop-in telemetry hooks that bind directly to OpenTelemetry standards, allowing you to trace execution paths, measure latency, and track token consumption across platforms like Langfuse or Datadog.

```python
from litellm_adk import setup_litellm_telemetry

# Injects OpenTelemetry wrappers into the execution pipeline
setup_litellm_telemetry()
```

---

## Global Configuration

The ADK uses `pydantic-settings` to manage global defaults securely. You can inject these via a `.env` file using the `ADK_` prefix, allowing you to instantiate agents without hardcoding infrastructure details.

```env
# .env
ADK_MODEL=groq/qwen/qwen3-32b
ADK_BASE_URL=http://localhost:9000/v1
ADK_API_KEY=sk-xxxx
ADK_LOG_LEVEL=INFO
```

With the `.env` file present, initialization becomes completely decoupled from your business logic:

```python
# The agent will automatically inherit the model, base_url, and api_key from the environment
agent = LiteLLMAgent(system_prompt="You are a routing specialist.")
```

---

## Reference Architectures

For complete reference implementations of specific architectural patterns, refer to the [`examples/`](./examples/) directory within the repository:

- **State Handoffs**: [`multiagent_demo.py`](./examples/multiagent_demo.py)
- **Declarative Initialization**: [`declarative_demo.py`](./examples/declarative_demo.py)
- **Authorization Pipelines**: [`streaming_hitl_demo.py`](./examples/streaming_hitl_demo.py)
- **Database Interfacing**: [`production_nl2sql.py`](./examples/production_nl2sql.py)

---

## Acknowledgments & Credits

This project is built directly on top of the incredible [LiteLLM](https://github.com/BerriAI/litellm) library. 

LiteLLM provides the foundational API standardization, proxy routing, and cross-provider exception mapping that makes this orchestration framework possible. The ADK is designed to be a complementary Agent-layer extension to their routing infrastructure. Huge thanks to the BerriAI team and all LiteLLM contributors!

---

## License
MIT License. See `LICENSE` for more information.
