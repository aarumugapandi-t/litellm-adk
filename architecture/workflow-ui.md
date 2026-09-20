# Build a Visual Workflow Platform on Top of the Python Agent Framework

Extend the existing Python Agent Framework into a complete **visual AI workflow platform**, inspired by the architecture and developer experience of n8n.

The system must provide:

1. A Python-native server
2. REST API
3. WebSocket/SSE execution streaming
4. Workflow persistence
5. Workflow execution engine
6. Visual workflow editor
7. Node-based architecture
8. Agent nodes
9. Tool nodes
10. Memory nodes
11. Vector retrieval nodes
12. Human-in-the-loop nodes
13. Conditional branching
14. Workflow variables
15. Credentials/configuration
16. Execution history
17. Debugging
18. Import/export of workflows

The existing Agent Framework remains the core execution/runtime layer.

---

# 1. Core Concept

The platform should have three distinct layers:

```text
┌──────────────────────────┐
│       Visual UI          │
│   Workflow Builder       │
└────────────┬─────────────┘
             │ Workflow JSON
             ▼
┌──────────────────────────┐
│      Workflow API        │
│       FastAPI            │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│    Workflow Engine       │
│ Graph / Scheduler / State│
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│    Agent Framework       │
│ LiteLLM / Tools / Memory │
│ Vector / HITL / Agents   │
└──────────────────────────┘
```

The UI must never contain the actual agent execution logic.

The server is the source of truth.

---

# 2. Native Server

Add a native server capability directly to the Python package.

The developer should be able to run:

```bash
agent-framework serve
```

or:

```bash
python -m agent_framework serve
```

The framework should start an HTTP server.

Provide programmatic usage:

```python
from agent_framework.server import serve

serve()
```

Allow configuration:

```bash
agent-framework serve \
    --host 0.0.0.0 \
    --port 8000 \
    --reload
```

Support:

```text
host
port
reload
workers
log_level
database_url
cors
```

Use FastAPI and Uvicorn.

---

# 3. Server Responsibilities

The server must provide APIs for:

```text
Workflows
Agents
Tools
Executions
Sessions
Memory
Vector stores
Credentials
Settings
Health
```

Example endpoints:

```text
GET    /api/workflows
POST   /api/workflows
GET    /api/workflows/{id}
PUT    /api/workflows/{id}
DELETE /api/workflows/{id}

POST   /api/workflows/{id}/execute
POST   /api/workflows/{id}/activate
POST   /api/workflows/{id}/deactivate

GET    /api/executions
GET    /api/executions/{id}

GET    /api/executions/{id}/events
WS     /api/executions/{id}/stream

GET    /api/nodes
GET    /api/tools

GET    /api/health
```

Keep API versioning:

```text
/api/v1/...
```

---

# 4. Web UI

Create a separate frontend application.

Recommended stack:

```text
React
TypeScript
React Flow
Tailwind CSS
```

The UI should look and behave like a modern node-based workflow editor.

Main layout:

```text
┌──────────────────────────────────────────────────────────────┐
│ Logo   Workflow Name             Save   Test   Activate      │
├───────────────┬──────────────────────────────────┬───────────┤
│               │                                  │           │
│ Node Library  │          Workflow Canvas         │ Inspector │
│               │                                  │           │
│ Trigger       │       ┌─────────┐                │ Node      │
│ Agent         │       │ Trigger │                │ Settings  │
│ LLM           │──────▶│         │──────┐         │           │
│ Tool          │       └─────────┘      │         │           │
│ Memory        │                        ▼         │           │
│ Vector Search │                 ┌────────────┐   │           │
│ Condition     │                 │ AI Agent   │   │           │
│ Human         │                 └─────┬──────┘   │           │
│ Transform     │                       │          │           │
│ Output        │                       ▼          │           │
│               │                 ┌──────────┐     │           │
│               │                 │ Output   │     │           │
│               │                 └──────────┘     │           │
└───────────────┴──────────────────────────────────┴───────────┘
```

---

# 5. Node Architecture

Every workflow is a directed graph.

A node should have:

```json
{
  "id": "agent_1",
  "type": "agent",
  "name": "Research Agent",
  "position": {
    "x": 500,
    "y": 300
  },
  "config": {},
  "inputs": [],
  "outputs": []
}
```

Edges:

```json
{
  "id": "edge_1",
  "source": "trigger",
  "target": "agent_1",
  "sourceHandle": "output",
  "targetHandle": "input"
}
```

---

# 6. Node Interface

Create a backend abstraction:

```python
class Node(Protocol):

    type: str
    version: str

    async def execute(
        self,
        context: NodeContext
    ) -> NodeResult:
        ...
```

Each node must be independently executable.

Node metadata should describe itself to the frontend:

```python
NodeDefinition(
    type="agent",
    name="AI Agent",
    description="Execute an AI agent",
    category="AI",
    icon="bot",
    inputs=[...],
    outputs=[...],
    config_schema={...},
)
```

The frontend should dynamically obtain available nodes from:

```text
GET /api/v1/nodes
```

Do not hardcode every node configuration in the frontend.

---

# 7. Initial Node Types

Implement these first.

## Trigger

Starts a workflow.

Types:

```text
Manual Trigger
Webhook Trigger
Schedule Trigger
API Trigger
```

---

## LLM Node

Direct LiteLLM invocation.

Configuration:

```text
model
temperature
max_tokens
system_prompt
user_prompt
response_format
```

---

## Agent Node

Execute an Agent Framework agent.

Configuration:

```text
agent
model
system_prompt
tools
memory
vector_store
max_iterations
temperature
response_format
```

The Agent Node should internally use the existing Agent abstraction.

---

## Tool Node

Execute a registered framework tool.

Configuration:

```text
tool
parameters
timeout
requires_approval
```

---

## Memory Node

Operations:

```text
read
write
search
delete
```

Configuration:

```text
memory_store
namespace
key
query
limit
```

---

## Vector Search Node

Configuration:

```text
vector_store
query
top_k
filters
similarity_threshold
```

Output:

```text
documents
scores
metadata
```

---

## Condition Node

Support branching:

```text
IF
SWITCH
```

Example:

```text
Input
  │
  ▼
Condition
 ├── true  → Agent
 └── false → Human
```

---

## Transform Node

Allow safe data transformation.

Examples:

```text
JSON Transform
Template
Set Variable
Map
Filter
Merge
```

Do not allow arbitrary Python execution from workflows by default.

---

## Human Node

Pause execution and request human input.

Configuration:

```text
message
input_type
approval
timeout
options
```

Execution becomes:

```text
RUNNING
   ↓
WAITING_FOR_HUMAN
   ↓
user responds
   ↓
RUNNING
```

---

## Output Node

Terminates a workflow.

Support:

```text
JSON
Text
Webhook Response
Workflow Result
```

---

# 8. Workflow Definition

Create a versioned workflow schema.

Example:

```json
{
  "version": "1",
  "id": "workflow_123",
  "name": "Research Assistant",
  "description": "Research and summarize a topic",
  "active": true,

  "nodes": [
    {
      "id": "trigger",
      "type": "manual",
      "version": "1",
      "position": {
        "x": 100,
        "y": 200
      },
      "config": {}
    },
    {
      "id": "agent",
      "type": "agent",
      "version": "1",
      "position": {
        "x": 400,
        "y": 200
      },
      "config": {
        "model": "openai/gpt-5",
        "system_prompt": "You are a research assistant.",
        "max_iterations": 10
      }
    }
  ],

  "edges": [
    {
      "id": "e1",
      "source": "trigger",
      "target": "agent"
    }
  ],

  "settings": {
    "timeout": 300,
    "max_concurrency": 10
  }
}
```

---

# 9. Workflow Engine

Build a dedicated execution engine.

Responsibilities:

```text
Load workflow
↓
Validate graph
↓
Create execution
↓
Resolve trigger
↓
Execute nodes
↓
Pass outputs
↓
Handle branches
↓
Persist state
↓
Emit events
↓
Finish
```

Do not implement workflow execution inside FastAPI route handlers.

Use:

```python
WorkflowEngine
WorkflowExecutor
ExecutionContext
ExecutionState
NodeExecutor
Scheduler
```

---

# 10. Graph Execution

Support:

```text
linear workflows
branches
merges
parallel execution
loops
conditional execution
sub-workflows
```

Example:

```text
             ┌── Vector Search ──┐
             │                   │
Trigger ──▶ Agent                ├──▶ Final Agent
             │                   │
             └── Web Search ────┘
```

The engine must understand dependency relationships.

Execute independent nodes concurrently where safe.

Use `asyncio`.

---

# 11. Workflow State

Every execution should maintain:

```python
ExecutionState(
    execution_id,
    workflow_id,
    status,
    current_nodes,
    completed_nodes,
    node_outputs,
    variables,
    errors,
    metadata,
)
```

State must be persisted so execution can be inspected and, where possible, resumed.

---

# 12. Expression System

Nodes need to consume previous node outputs.

Provide expressions similar to:

```text
{{ trigger.input }}
{{ agent.output }}
{{ vector_search.documents }}
{{ variables.user_id }}
```

Example:

```text
Prompt:

Research the following topic:

{{ trigger.topic }}
```

Implement a safe expression resolver.

Do not evaluate arbitrary Python.

Support:

```text
node.output
node.output.field
variables.x
execution.id
session.id
```

---

# 13. Workflow Variables

Support:

```text
workflow variables
execution variables
environment variables
node outputs
session variables
```

Example:

```json
{
  "variables": {
    "language": "English",
    "max_results": 5
  }
}
```

Allow nodes to read/write variables according to permissions.

---

# 14. Credentials

Never store raw API keys inside workflow JSON.

Create a credential abstraction:

```python
CredentialStore
Credential
CredentialResolver
```

Workflow configuration should reference:

```json
{
  "credential_id": "openai-prod"
}
```

The backend resolves the secret.

Secrets must never be returned to the frontend.

---

# 15. Workflow Persistence

Initially support SQLite.

Design the persistence layer so PostgreSQL can be added later.

Create repositories:

```text
WorkflowRepository
ExecutionRepository
CredentialRepository
SessionRepository
```

Example:

```python
workflow = await workflow_repository.get(workflow_id)
await workflow_repository.save(workflow)
```

---

# 16. Execution History

The UI must provide an execution page.

Show:

```text
Execution ID
Workflow
Started
Finished
Duration
Status
Tokens
Cost
```

Selecting an execution should display:

```text
Trigger
   ↓
Agent          ✓ 2.3s
   ↓
Vector Search  ✓ 0.4s
   ↓
Condition      ✓
   ↓
Human          ⏸ waiting
```

Users should be able to inspect each node's:

```text
input
output
duration
logs
errors
tool calls
token usage
```

---

# 17. Real-Time Execution

When a workflow runs, stream events to the frontend.

Use WebSocket or SSE.

Events:

```text
workflow.started
node.started
node.progress
node.output
node.completed
node.failed
human.required
workflow.completed
workflow.failed
```

Example:

```json
{
  "type": "node.completed",
  "execution_id": "...",
  "node_id": "agent_1",
  "output": {...}
}
```

The UI should visually update the graph while execution is occurring.

Running nodes should visibly indicate their state.

---

# 18. Debug Mode

Provide:

```text
Test Workflow
Test From Node
Run Selected Node
Inspect Input
Inspect Output
Replay Execution
```

A developer should be able to select a node and execute it with sample input without running the entire workflow.

---

# 19. Workflow Validation

Before activation:

```text
Validate graph
Validate node configuration
Validate connections
Validate required credentials
Validate expressions
Validate cycles
Validate trigger
```

Display validation errors directly in the UI.

Example:

```text
Agent node:
✗ Model is required

Vector Search:
✗ Vector store is not configured
```

---

# 20. Workflow Lifecycle

Support:

```text
DRAFT
ACTIVE
INACTIVE
ARCHIVED
```

Only active workflows should respond to production triggers.

---

# 21. Versioning

Every workflow change should create a version.

Support:

```text
draft version
published version
execution version
```

An execution must reference the exact workflow version used.

This prevents changing a workflow while an old execution is running from changing its behavior.

---

# 22. Sub-Workflows

Allow a workflow to invoke another workflow.

Create:

```text
Workflow Node
```

Example:

```text
Main Workflow
      │
      ▼
Research Subworkflow
      │
      ▼
Summarization Subworkflow
```

Pass inputs and outputs between workflows.

---

# 23. Agent Configuration UI

The Agent node inspector should expose the Agent Framework configuration.

Organize settings into sections:

### Model

```text
Provider
Model
Temperature
Max Tokens
Reasoning
Timeout
```

### Instructions

```text
System Prompt
Developer Prompt
```

### Tools

```text
Available Tools
Tool Permissions
Approval Requirements
```

### Memory

```text
Enable Memory
Memory Store
Memory Policy
```

### Retrieval

```text
Vector Store
Embedding Model
Top K
Similarity Threshold
```

### Execution

```text
Max Iterations
Max Tool Calls
Execution Timeout
```

### Output

```text
Text
JSON
Structured Schema
```

---

# 24. Node Configuration Schemas

Node configuration must be schema-driven.

Backend:

```python
NodeDefinition(
    config_schema=...
)
```

Frontend:

```text
Node Definition
       ↓
Generate Inspector UI
       ↓
User edits configuration
       ↓
JSON
       ↓
API
```

Avoid creating custom UI components for every field unless necessary.

---

# 25. UI Features

Implement:

```text
drag & drop nodes
node search
zoom
pan
minimap
copy/paste
delete
undo/redo
multi-select
connect nodes
auto layout
keyboard shortcuts
node inspector
workflow validation
save
save as
duplicate
activate/deactivate
test
execution viewer
```

---

# 26. Workflow Import / Export

Support:

```text
Export JSON
Import JSON
```

Example:

```bash
agent-framework workflow export my-workflow.json
```

and:

```bash
agent-framework workflow import my-workflow.json
```

The UI should also support import/export.

---

# 27. CLI

Extend the CLI:

```bash
agent-framework serve

agent-framework workflow list

agent-framework workflow create

agent-framework workflow run <workflow-id>

agent-framework workflow export <workflow-id>

agent-framework workflow import <file>

agent-framework workflow validate <file>
```

---

# 28. Project Structure

Use a monorepo structure:

```text
agent-framework/
│
├── packages/
│
│   ├── python/
│   │   └── agent_framework/
│   │       ├── agent/
│   │       ├── models/
│   │       ├── tools/
│   │       ├── memory/
│   │       ├── vector/
│   │       ├── context/
│   │       ├── human/
│   │       │
│   │       ├── workflow/
│   │       │   ├── engine.py
│   │       │   ├── graph.py
│   │       │   ├── state.py
│   │       │   ├── execution.py
│   │       │   ├── expressions.py
│   │       │   └── nodes/
│   │       │
│   │       ├── server/
│   │       │   ├── app.py
│   │       │   ├── routes/
│   │       │   ├── websocket.py
│   │       │   └── dependencies.py
│   │       │
│   │       ├── persistence/
│   │       ├── credentials/
│   │       ├── events/
│   │       └── cli/
│   │
│   └── web/
│       ├── src/
│       │   ├── components/
│       │   ├── canvas/
│       │   ├── nodes/
│       │   ├── inspector/
│       │   ├── execution/
│       │   ├── workflows/
│       │   ├── api/
│       │   └── stores/
│       └── package.json
│
├── examples/
├── tests/
└── docs/
```

---

# 29. Native Server + UI Distribution

The goal is eventually to make this feel like a single application.

A developer should be able to install:

```bash
pip install agent-framework
```

and run:

```bash
agent-framework serve
```

The Python server should serve the compiled frontend assets.

Therefore:

```text
Browser
   │
   ▼
localhost:8000
   │
   ├── /              → Web UI
   ├── /api/v1/...    → REST API
   ├── /ws/...        → WebSocket
   └── /static/...    → Frontend assets
```

During frontend development, allow:

```text
React dev server
       ↓
FastAPI backend
```

using configurable API URLs/CORS.

In production, package the built frontend into the Python distribution.

---

# 30. Architecture Boundary

Maintain strict separation:

```text
                 UI
                  │
             HTTP/WebSocket
                  │
                  ▼
              Server
                  │
                  ▼
          Workflow Engine
                  │
                  ▼
           Agent Framework
                  │
       ┌──────────┼───────────┐
       ▼          ▼           ▼
    LiteLLM     Tools       Memory
                            │
                         Vector
```

The workflow engine must depend on Agent Framework abstractions.

The Agent Framework must NOT depend on the web UI.

The core Agent Framework should remain usable without starting the server.

---

# 31. Important Principle

The framework should have two modes:

## SDK Mode

```python
agent = Agent(...)
result = await agent.run(...)
```

No server required.

## Platform Mode

```bash
agent-framework serve
```

Starts:

```text
API
Workflow Engine
Persistence
Event Streaming
Web UI
```

This means developers can use the framework as a normal Python SDK or as a complete visual AI platform.

---

# 32. Future-Proof Architecture

Design interfaces so the platform can eventually support:

```text
multiple workers
distributed execution
Redis
PostgreSQL
queues
scheduled workflows
webhooks
authentication
RBAC
teams
projects
workflow marketplace
custom nodes
plugins
remote tools
MCP
A2A
```

Do not implement all of these initially.

The architecture must not prevent them.

---

# 33. Initial MVP

Do NOT attempt to build everything at once.

The first working version should implement only:

```text
Python Agent Framework
        +
FastAPI Server
        +
SQLite
        +
Workflow Graph
        +
React Flow UI
        +
Manual Trigger
        +
LLM Node
        +
Agent Node
        +
Tool Node
        +
Condition Node
        +
Memory Node
        +
Vector Search Node
        +
Human Approval Node
        +
Output Node
        +
Execution Streaming
        +
Execution History
```

Everything else should be designed as extensions.

---

# 34. MVP User Experience

The final MVP should allow this workflow:

```text
                    ┌───────────────┐
                    │ Manual Trigger│
                    └───────┬───────┘
                            │
                            ▼
                    ┌───────────────┐
                    │ Vector Search │
                    └───────┬───────┘
                            │
                            ▼
                    ┌───────────────┐
                    │   AI Agent    │
                    │   LiteLLM     │
                    └───────┬───────┘
                            │
                            ▼
                    ┌───────────────┐
                    │     Human     │
                    │    Approval   │
                    └───────┬───────┘
                            │
                            ▼
                    ┌───────────────┐
                    │     Output    │
                    └───────────────┘
```

The user should be able to build this entirely through the visual editor.

Then click:

```text
Test
```

and see the execution happen visually.

---

# 35. Final Quality Requirements

The implementation must:

* use strong typing
* use Pydantic schemas
* use async APIs
* have clean interfaces
* avoid circular dependencies
* have unit tests
* have integration tests
* validate workflow graphs
* persist executions
* stream execution events
* handle failures
* support cancellation
* enforce execution limits
* never expose credentials
* never execute arbitrary Python from workflow configuration
* keep Agent Framework independent of the UI
* keep UI independent of implementation details
* version workflow schemas
* provide clear documentation

Before finishing, run:

```bash
pytest
```

and frontend tests/build.

Verify:

```text
agent-framework serve
```

starts successfully.

Verify that opening:

```text
http://localhost:8000
```

loads the workflow editor.

Verify that a workflow can be:

```text
created
saved
loaded
edited
validated
executed
streamed
inspected
activated
deactivated
exported
imported
```

The final architecture should make the framework feel like:

> **An n8n-style visual workflow runtime specifically designed around AI agents, LiteLLM, memory, RAG, tools, and human-in-the-loop execution.**

Do not copy n8n's implementation. Adopt the useful conceptual model of a visual DAG/workflow engine while designing the runtime specifically for this Agent Framework.
