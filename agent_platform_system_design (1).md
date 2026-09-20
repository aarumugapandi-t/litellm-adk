Agent Platform System Design

Visual Agent Manager, Dynamic Tools, Secure Runtime, and API Platform

Consolidated architecture and implementation blueprint

## Executive design principle

The platform is not primarily a workflow editor. It is an Agent Control
Plane where a Manager Agent and a visual UI create, configure, version,
test, publish, deploy, and expose other agents. Workflows are an
optional execution representation. Agent, Tool, Skill, Credential,
Policy, Version, Deployment, and Execution are first-class resources.

## Target user experience

``` text
User
  |
  v
Manager Agent / Visual Agent Manager
  |
  +--> create_agent
  +--> discover_tools
  +--> create_skill
  +--> attach_tool
  +--> bind_credential
  +--> test_agent
  +--> publish_agent
  +--> deploy_agent
  |
  v
Agent Registry
  |
  +--> Support Agent
  +--> Research Agent
  +--> Analytics Agent
  +--> Developer Agent
  |
  v
Universal Agent Runtime
  |
  +--> REST API
  +--> Streaming API
  +--> SDK
  +--> Webhook
  +--> UI / Chat
```

## 1. Product Scope

### 1.1 Product goal

Build a platform in which a user can describe the agents they need in
natural language, while the Manager Agent translates the request into
declarative agent specifications. The same specifications are editable
through a visual UI, validated by the control plane, and executed by a
separate runtime.

### 1.2 Primary capabilities

-   Create and manage multiple agents from one project.

-   Attach reusable tools to agents and bind agent-specific credentials
    and permissions.

-   Create persistent LLM-generated Skills/Tools when an existing
    capability is insufficient.

-   Configure model, instructions, memory, knowledge, policies, limits,
    and output schemas.

-   Create drafts, validate, test, version, publish, deploy, rollback,
    and audit agents.

-   Expose published agents through REST APIs, streaming APIs, SDKs,
    webhooks, and UI chat.

-   Allow agents to call other agents as tools, with recursion/depth
    limits and policy checks.

-   Support human approval for sensitive actions.

-   Keep secrets outside workflow/agent definitions and resolve them
    only at execution time.

-   Provide execution traces, tool-call logs, errors, latency, cost, and
    audit history.

### 1.3 Non-goals for the first release

-   A general-purpose low-code automation platform covering every SaaS
    integration.

-   Unrestricted execution of arbitrary LLM-generated code.

-   A fully autonomous production deployment path without validation and
    policy gates.

-   A requirement that every agent be represented as a visual graph.

## 2. Architecture Principles

## 3. Core Resource Model

``` text
Project
 |
 +-- Agents
 |     |
 |     +-- Tools
 |     +-- Skills
 |     +-- Memory
 |     +-- Knowledge
 |     +-- Policies
 |     +-- AgentToolBindings
 |     +-- Deployments
 |
 +-- Tools
 +-- Skills
 +-- Credentials
 +-- Resources
 +-- Policies
 +-- Executions
```

## 4. System Architecture

``` text
+----------------------+
                         |       Web UI          |
                         | React / TypeScript    |
                         +----------+-----------+
                                    |
                              REST / SSE
                                    |
                         +----------v-----------+
                         |      API Server      |
                         | FastAPI               |
                         +----------+-----------+
                                    |
             +----------------------+----------------------+
             |                      |                      |
     +-------v-------+      +-------v-------+      +-------v-------+
     | Agent Registry|      | Tool Registry |      | Credential    |
     | + Versions    |      | + Skills      |      | Registry      |
     +-------+-------+      +-------+-------+      +-------+-------+
             |                      |                      |
             +----------------------+----------------------+
                                    |
                         +----------v-----------+
                         | Workflow / Agent     |
                         | Compiler + Validator |
                         +----------+-----------+
                                    |
                         +----------v-----------+
                         | Execution Orchestrator|
                         +----------+-----------+
                                    |
                    +---------------+---------------+
                    |               |               |
             +------v------+ +------v------+ +------v------+
             | Agent Worker| | Tool Worker | | Code Sandbox|
             +------+------ +------+------ +------+------+
                    |               |               |
                 LiteLLM        APIs/DB/MCP       Generated code
                                    |
                              +-----v-----+
                              | Secrets   |
                              | Manager   |
                              +-----------+
```

### 4.1 Control plane

The control plane owns desired state. It stores resource definitions,
validates changes, manages versions, resolves dependencies, handles
credential bindings, applies policies, and controls
publication/deployment.

### 4.2 Data plane

The data plane executes published versions. It loads the exact agent
version, builds its runtime context, resolves permitted credentials,
calls LiteLLM, dispatches tools, enforces policies, records events, and
returns the result.

## 5. UI Architecture

### 5.1 Main navigation

``` text
Agent Platform
 |
 +-- Overview
 +-- Agents
 +-- Tools
 +-- Skills
 +-- Credentials
 +-- Knowledge
 +-- Memory
 +-- Policies
 +-- Deployments
 +-- Executions
 +-- API / SDK
 +-- Settings
```

### 5.2 Agent Manager screen

``` text
+-----------------------------------------------------------------------+
| Agent Manager                                             + New Agent |
+----------------+------------------------------------------------------+
| Agents         | Customer Support Agent                              |
|                |                                                      |
| * Support      | Status: Published      Version: 3                    |
| * Research     |                                                      |
| * Analytics    | Instructions                                        |
| * Developer    | [..................................................] |
|                |                                                      |
|                | Tools                                                |
|                | [Postgres] [Docs Search] [Email]                    |
|                |                                                      |
|                | Memory      Knowledge      Policy                    |
|                | [Enabled]   [Customer KB] [Read-only]              |
|                |                                                      |
|                | API: POST /v1/agents/customer-support/run           |
|                |                                                      |
|                | [Test] [Edit] [Versions] [Deploy] [Logs]            |
+----------------+------------------------------------------------------+
```

### 5.3 Manager Agent panel

The Manager Agent is a natural-language control surface over the same
registries and resource APIs used by the UI. It must not directly mutate
infrastructure or bypass validation.

``` text
User:
  "Create a sales analytics agent that can query the warehouse
   and produce charts."

Manager:
  1. Discover existing tools.
  2. Select SQL/query capability.
  3. Select chart-generation capability.
  4. Determine required credential.
  5. Build an AgentSpec draft.
  6. Run validation.
  7. Show missing configuration or risks.
  8. Test.
  9. Ask for publication/deployment approval.
```

### 5.4 Agent detail tabs

-   Overview: description, status, model, owner, current version.

-   Instructions: system/developer instructions and structured output
    settings.

-   Tools: reusable tools and agent-specific bindings.

-   Memory: session memory, long-term memory, vector store
    configuration.

-   Knowledge: retrieval sources and knowledge bases.

-   Policy: permissions, network, rate limits, approvals, timeouts.

-   API: endpoints, authentication, schemas, streaming events.

-   Versions: immutable versions, diffs, rollback.

-   Runs: execution timeline, tool calls, errors, latency, token/cost
    data.

## 6. Optional Visual Agent/Workflow Editor

The visual editor should be an editing surface over the same declarative
resource model, not the runtime itself. React Flow is suitable for the
graph surface because it provides node-based editing primitives such as
dragging, panning, selection, and connections.

``` text
Canvas
 |
 +-- Input
 +-- Agent
 +-- Tool
 +-- Condition
 +-- Loop
 +-- Human Approval
 +-- Memory
 +-- Knowledge Search
 +-- Agent-as-Tool
 +-- Output
```

### 6.1 Graph patch protocol

``` text
Supported operations:
  add_node
  remove_node
  update_node
  connect
  disconnect
  set_config
  bind_credential
  attach_tool
  detach_tool
  publish_version
```

The Manager Agent should emit patches or structured resource mutations,
not raw frontend state. This enables undo/redo, auditability, conflict
handling, validation, and version control.

## 7. Agent Runtime

``` text
Agent Invocation
      |
      v
Load Published Agent Version
      |
      v
Build Execution Context
      |
      +--> Session / Memory
      +--> Tools
      +--> Credentials
      +--> Policies
      +--> Knowledge
      |
      v
LiteLLM Model Call
      |
      +---- final response ----------------------+
      |                                          |
      +---- tool call                            |
              |                                  |
              v                                  |
        Validate arguments                      |
              |                                  |
        Authorization / Policy                  |
              |                                  |
        Resolve credentials                     |
              |                                  |
        Execute tool/sandbox                    |
              |                                  |
        Validate output                         |
              |                                  |
              +------------> model -------------+
      |
      v
Final output + trace
```

### 7.1 Agent abstraction

``` text
class AgentSpec:
    id: str
    name: str
    version: int
    instructions: str
    model: ModelConfig
    tools: list[ToolBinding]
    memory: MemoryConfig | None
    knowledge: KnowledgeConfig | None
    policy_id: str
    output_schema: dict | None

class AgentRuntime:
    async def run(self, agent_id, input, session=None, context=None):
        ...
```

## 8. Tool Architecture

A Tool is a versioned contract, not merely a Python function. The
implementation can be a native Python callable, HTTP adapter, MCP
server, database adapter, external service, or sandboxed generated code.
Current agent SDKs similarly model function tools with explicit schemas
and also support agents-as-tools; this platform should preserve that
abstraction.

### 8.1 Tool manifest

``` text
{
  "name": "customer_database",
  "version": 3,
  "runtime": {"language": "python", "version": "3.12"},
  "entrypoint": "main:run",
  "inputs": {"sql": {"type": "string"}},
  "outputs": {"rows": {"type": "array"}},
  "credentials": [{"name": "database", "type": "postgres"}],
  "permissions": ["database.read"],
  "network": {"allow": ["postgres.internal:5432"]},
  "limits": {"timeout_seconds": 10, "max_rows": 1000}
}
```

## 9. LLM-Generated Tools / Skills

Generated code is treated as a build artifact. It must not be executed
directly inside the API server. The generated capability goes through
specification, static checks, dependency checks, tests, policy checks,
and publication before it can be attached to production agents.

``` text
Generate
  |
  v
Tool/Skill Specification
  |
  v
Static validation
  |
  +--> schema validation
  +--> dependency validation
  +--> forbidden API/import checks
  +--> resource policy checks
  |
  v
Sandbox test
  |
  +--> generated tests
  +--> runtime tests
  +--> credential tests
  |
  v
Approval / policy gate
  |
  v
Publish version
  |
  v
Tool Registry
```

### 9.1 Generated skill lifecycle

## 10. Credentials and Environment Variables

Credentials are first-class resources and must remain separate from
agent definitions, tool source, workflow JSON, prompts, and ordinary
logs. The UI should bind a credential reference to an agent-tool
relationship. At execution time, the runtime resolves the secret and
injects only the required capability.

``` text
AgentToolBinding
  |
  +--> tool_id
  +--> credential_id
  +--> permissions
  +--> configuration
  |
  v
Credential Resolver
  |
  v
Secret Manager
  |
  v
Short-lived runtime context
  |
  v
Tool / Sandbox
```

### 10.1 UI behavior when a credential is missing

-   Agent remains in DRAFT or CONFIGURATION_REQUIRED state.

-   UI identifies the missing credential without exposing any secret
    value.

-   User can create/select a credential from the node or tool inspector.

-   Connection test runs using the secret manager and never sends the
    secret through the LLM.

-   After successful validation, the agent can move to READY.

### 10.2 Environment-variable compatibility

Support \${DB_HOST}, \${API_KEY}, etc. as an import/export convenience,
but internally convert them to SecretRef/CredentialRef objects. The
generated code should prefer a runtime credential context over
hard-coded os.environ lookups.

### 10.3 Dynamic credentials

For higher-security deployments, integrate a secret manager capable of
issuing short-lived database credentials. Vault's database secrets
engine is one example: it can generate credentials dynamically and
revoke them through leasing.

## 11. Policy Engine

``` text
Tool Call
   |
   v
Authentication
   |
   v
Authorization
   |
   v
Input Validation
   |
   v
Resource / Credential Check
   |
   v
Policy Decision
   |
   +--> deny
   +--> approve
   +--> require_human
   +--> allow
   |
   v
Execution
```

``` text
{
  "tool": "customer_database",
  "permissions": ["database.read"],
  "resources": ["postgres/customer"],
  "network": {"allow": ["postgres.internal:5432"]},
  "limits": {"timeout_seconds": 10, "max_rows": 1000},
  "approval": {"required_for": ["database.write"]}
}
```

Policies must be enforced by the runtime, not only described in prompts.
The LLM can request an action; it cannot grant itself permission.

## 12. Universal Agent API

### 12.1 REST resources

``` text
POST   /v1/agents
GET    /v1/agents
GET    /v1/agents/{agent_id}
PATCH  /v1/agents/{agent_id}
POST   /v1/agents/{agent_id}/versions
POST   /v1/agents/{agent_id}/publish
POST   /v1/agents/{agent_id}/deploy
POST   /v1/agents/{agent_id}/run
POST   /v1/agents/{agent_id}/sessions
POST   /v1/agents/{agent_id}/sessions/{session_id}/messages
GET    /v1/executions/{execution_id}
GET    /v1/executions/{execution_id}/events
```

### 12.2 Run request

``` text
POST /v1/agents/customer-support/run

{
  "input": "My order has not arrived.",
  "session_id": "sess_123",
  "metadata": {
    "customer_id": "cust_42"
  }
}
```

### 12.3 Streaming events

``` text
agent.started
agent.message
tool.requested
tool.started
tool.completed
human_approval.required
human_approval.granted
agent.completed
agent.failed
```

The same event model should feed the UI run timeline and external
consumers. Use SSE initially for simple HTTP streaming; add WebSocket
where bidirectional interaction is needed.

## 13. Agent-to-Agent Composition

A published agent should be exposable as a callable capability. This
allows the Manager Agent to delegate work to specialized agents and lets
agents compose without duplicating their tools.

``` text
Manager Agent
 |
 +--> customer_support(input)
 +--> research(input)
 +--> finance(input)
 +--> developer(input)
```

-   Treat Agent-as-Tool as a normal callable interface with input/output
    schemas.

-   Enforce max delegation depth, total child calls, timeout, and
    budget.

-   Prevent circular delegation through runtime call-chain tracking.

-   Propagate only the context explicitly allowed by policy.

-   Do not automatically propagate parent credentials to child agents.

## 14. Manager Agent Design

### 14.1 Manager tools

``` text
create_agent
update_agent
list_agents
get_agent
discover_tools
attach_tool
detach_tool
create_skill
update_skill
bind_credential
validate_agent
test_agent
publish_agent
deploy_agent
rollback_agent
inspect_execution
```

### 14.2 Manager operating model

1.  Interpret the user's goal and extract requirements.

2.  Discover existing agents, tools, skills, credentials, policies, and
    resources.

3.  Reuse existing capabilities before creating new ones.

4.  Create a draft AgentSpec and tool bindings.

5.  Identify missing credentials or configuration.

6.  Run validation and policy checks.

7.  Create or repair generated Skills only when necessary.

8.  Run tests in an isolated environment.

9.  Present the resulting plan and any required user actions.

10. Publish/deploy only when the requested authorization policy allows
    it.

## 15. Persistence Model

``` text
projects
agents
agent_versions
agent_tool_bindings
tools
tool_versions
skills
skill_versions
credentials
credential_bindings
policies
resources
deployments
executions
execution_events
sessions
messages
knowledge_sources
memory_stores
```

### 15.1 Important schema relationships

## 16. Python Framework Package Structure

``` text
agent_platform/
|
+-- core/
|   +-- agent.py
|   +-- context.py
|   +-- state.py
|   +-- events.py
|
+-- models/
|   +-- base.py
|   +-- litellm.py
|
+-- tools/
|   +-- base.py
|   +-- registry.py
|   +-- native.py
|   +-- dynamic.py
|   +-- agent_tool.py
|   +-- schemas.py
|
+-- skills/
|   +-- model.py
|   +-- registry.py
|   +-- compiler.py
|   +-- versions.py
|
+-- credentials/
|   +-- manager.py
|   +-- resolver.py
|   +-- providers/
|
+-- policies/
|   +-- engine.py
|   +-- permissions.py
|   +-- rules.py
|
+-- runtime/
|   +-- runner.py
|   +-- dispatcher.py
|   +-- context.py
|   +-- workers/
|
+-- sandbox/
|   +-- runner.py
|   +-- docker.py
|   +-- limits.py
|
+-- memory/
+-- knowledge/
+-- workflows/
+-- api/
+-- observability/
```

## 17. Frontend Package Structure

``` text
src/
|
+-- app/
+-- pages/
|   +-- agents/
|   +-- tools/
|   +-- skills/
|   +-- credentials/
|   +-- executions/
|
+-- canvas/
|   +-- AgentCanvas
|   +-- NodeRenderer
|   +-- EdgeRenderer
|
+-- nodes/
|   +-- AgentNode
|   +-- ToolNode
|   +-- MemoryNode
|   +-- HumanApprovalNode
|   +-- ConditionNode
|
+-- inspector/
|   +-- SchemaForm
|   +-- CredentialSelector
|   +-- PolicyEditor
|
+-- manager/
|   +-- ManagerChat
|   +-- PlanPreview
|   +-- GraphPatchPreview
|
+-- executions/
|   +-- RunTimeline
|   +-- ToolCallViewer
|   +-- TraceViewer
|
+-- api/
+-- state/
```

## 18. Execution, Queues, and Durability

For the MVP, an async worker pool with persisted execution state is
sufficient. The runtime should still be designed around durable
execution records so it can later be backed by a workflow engine.

``` text
API
 |
 v
Execution record
 |
 v
Task queue
 |
 +--> Agent worker
 +--> Tool worker
 +--> Sandbox worker
 |
 v
Execution events
 |
 v
Client stream / UI timeline
```

For long-running workflows with retries, pauses, human approval, or
multi-day execution, a durable workflow platform such as Temporal can be
introduced. Temporal is designed to resume workflows after crashes,
network failures, and infrastructure outages.

## 19. Security Model

## 20. Observability

``` text
Execution
 |
 +-- agent.started
 +-- llm.requested
 +-- llm.completed
 +-- tool.requested
 +-- policy.checked
 +-- credential.resolved
 +-- tool.started
 +-- tool.completed
 +-- human_approval.required
 +-- human_approval.granted
 +-- agent.completed
 +-- agent.failed
```

-   Trace every execution with a correlation ID.

-   Record model name, latency, token usage, estimated cost, and retry
    count where available.

-   Record tool name, duration, status, and sanitized input/output
    metadata.

-   Never log raw credentials or sensitive payloads unless explicitly
    configured and protected.

-   Provide both technical traces and a user-friendly timeline.

## 21. Versioning and Deployment

``` text
Draft
  |
  v
Validated
  |
  v
Tested
  |
  v
Published v3
  |
  +--> Deployment: staging
  |
  +--> Deployment: production
             |
             v
        Endpoint / API key
```

-   Published versions are immutable.

-   Deployments pin an exact version.

-   Rollback means changing the deployment pointer to a previously
    published version.

-   Editing an agent creates a new draft/version rather than mutating
    production.

-   Tool and Skill versions used by a deployment should be pinned or
    resolved by explicit compatibility rules.

## 22. Implementation Roadmap

## 23. Recommended MVP Cut

Do not start with the full graph editor or arbitrary code generation.
The fastest path to a usable platform is a resource-oriented Agent
Manager.

1.  Agent registry with drafts and published versions.

2.  Agent detail UI with instructions/model/tools/memory configuration.

3.  Reusable Tool registry with HTTP, Python, and database tools.

4.  Credential registry using secret references.

5.  AgentToolBinding with per-agent credential and policy configuration.

6.  LiteLLM-based AgentRuntime.

7.  REST run endpoint plus SSE execution events.

8.  Execution history and tool-call timeline.

9.  Manager Agent that can create/update agents and attach existing
    tools.

10. Only after the above works: visual graph editor and generated
    Skills.

## 24. End-to-End Example

### User request:

"Create a customer support agent. It should query our PostgreSQL
customer database, search our documentation, and send an email when a
human follow-up is required."

``` text
Manager Agent
  |
  +--> discover_tools()
  |
  +--> found:
  |      postgres_query
  |      documentation_search
  |      send_email
  |
  +--> create_agent("customer_support")
  |
  +--> attach_tool(postgres_query)
  |      credential = customer_db_readonly
  |      permission = database.read
  |
  +--> attach_tool(documentation_search)
  |
  +--> attach_tool(send_email)
  |      credential = company_email
  |      approval = required
  |
  +--> validate_agent()
  |
  +--> test_agent()
  |
  +--> publish_agent()
  |
  +--> deploy_agent()
  |
  v
POST /v1/agents/customer-support/run
  |
  v
Agent Runtime
  |
  +--> LLM
  +--> PostgreSQL
  +--> Documentation
  +--> Email (approval gate)
  |
  v
Final response + execution trace
```

## 25. Final Architectural Decisions

## 26. Reference Architecture Evidence

The design aligns with several current agent-platform patterns. OpenAI's
Agents SDK models agents as LLMs configured with instructions and tools,
supports function tools, agent-as-tool composition, sessions,
human-in-the-loop mechanisms, and tracing. This supports treating Agent,
Tool, and Agent-as-Tool as explicit runtime abstractions rather than
embedding everything into a workflow graph.

LiteLLM provides a model abstraction/gateway layer with authentication,
logging, spend tracking, and rate limiting capabilities, making it a
reasonable model-provider boundary for this framework.

React Flow is a suitable implementation primitive for the optional node
editor because it directly supports interactive node-based UIs.

Vault demonstrates the credential pattern recommended here: credentials
can be generated dynamically and leased rather than hard-coded into
applications. Temporal demonstrates the durable-execution model
appropriate for long-running, failure-sensitive agent workflows.

## 27. Selected Sources

-   OpenAI Agents SDK --- Tools:
    https://openai.github.io/openai-agents-python/tools/

-   OpenAI Agents SDK --- Agents:
    https://openai.github.io/openai-agents-python/agents/

-   OpenAI Agents SDK --- TypeScript Tools:
    https://openai.github.io/openai-agents-js/guides/tools/

-   LiteLLM Documentation: https://docs.litellm.ai/

-   React Flow: https://reactflow.dev/

-   HashiCorp Vault --- Database Secrets Engine:
    https://developer.hashicorp.com/vault/docs/secrets/databases

-   Temporal Documentation: https://docs.temporal.io/

## Appendix A --- Minimal AgentSpec

``` text
class AgentSpec(BaseModel):
    id: str
    name: str
    description: str
    instructions: str
    model: ModelConfig

    tools: list[ToolBinding] = []
    memory: MemoryConfig | None = None
    knowledge: KnowledgeConfig | None = None

    policy_id: str
    output_schema: dict | None = None

    max_turns: int = 20
    max_tool_calls: int = 20
    timeout_seconds: int = 120
```

## Appendix B --- Minimal ToolSpec

``` text
class ToolSpec(BaseModel):
    id: str
    name: str
    description: str
    version: int

    input_schema: dict
    output_schema: dict

    runtime: RuntimeConfig
    credentials: list[CredentialRequirement] = []
    permissions: list[str] = []

    timeout_seconds: int = 30
    enabled: bool = True
```

## Appendix C --- Minimal AgentToolBinding

``` text
class AgentToolBinding(BaseModel):
    agent_id: str
    tool_id: str

    credential_id: str | None = None
    policy_id: str | None = None

    config: dict = {}
    enabled: bool = True
```

| Area \| Decision \|

| --- \| --- \|

| Primary product \| Agent Control Center / Agent Factory \|

| Core model \| Manager Agent creates and manages first-class Agents \|

| Agent capabilities \| Reusable Tools, Skills, Memory, Knowledge,
  Credentials, Policies \|

| Visual UI \| Agent manager + optional workflow/graph editor \|

| LLM layer \| LiteLLM-based model abstraction \|

| Backend \| Python + FastAPI + PostgreSQL \|

| Frontend \| React + TypeScript + React Flow for graph editing \|

| Execution \| Dedicated runtime workers; generated code isolated in
  sandbox \|

| Secrets \| Credential references + external secret manager \|

| External interface \| REST, streaming events, SDK, webhooks, UI/Chat
  \|

| Principle \| Implementation rule \|

| --- \| --- \|

| Declarative control plane \| UI and Manager Agent produce validated
  resource specifications, not direct runtime mutations. \|

| Runtime separation \| API/control services do not execute arbitrary
  generated code. \|

| Capability-based security \| Tools receive only the credentials,
  network access, and permissions explicitly granted. \|

| Version everything \| Agent, Tool, Skill, workflow graph, policies,
  and deployments are versioned. \|

| Credential isolation \| Secrets are never stored in prompts, graph
  JSON, generated source, or ordinary logs. \|

| Schema-first tools \| Tool inputs/outputs and configuration are
  explicit JSON/Pydantic schemas. \|

| Human approval \| Sensitive operations can pause execution and require
  approval. \|

| Universal callable interface \| Agent.run is the internal contract;
  REST/SDK/UI/Webhooks are adapters. \|

| Observable execution \| Every important state transition becomes an
  event. \|

| AI-assisted, deterministic core \| LLMs propose changes; validators
  and registries enforce state. \|

| Resource \| Purpose \| Example \|

| --- \| --- \| --- \|

| Agent \| Reasoning entity configured with model, instructions,
  capabilities, and runtime policy. \| Customer Support Agent \|

| Tool \| Callable capability with an explicit contract. \|
  postgres_query \|

| Skill \| Reusable capability/implementation, including generated code.
  \| invoice_parser \|

| Credential \| Secure reference to authentication material. \|
  production-postgres \|

| Policy \| Authorization, limits, approvals, and resource constraints.
  \| support-readonly \|

| Resource \| External object the runtime can access. \| PostgreSQL
  database \|

| Deployment \| Published agent version made callable. \|
  customer-support v3 \|

| Execution \| One invocation of an agent/workflow. \| exec_9a8f \|

| Execution Event \| Append-only state/trace event. \| tool.completed \|

| Tool type \| Runtime \| Typical use \|

| --- \| --- \| --- \|

| Native function \| Trusted application process \| Small deterministic
  helpers \|

| HTTP tool \| HTTP client worker \| REST/SaaS APIs \|

| Database tool \| DB worker \| SQL/query access \|

| MCP tool \| MCP client/server \| External tool ecosystems \|

| Dynamic skill \| Sandbox worker \| LLM-generated code \|

| Agent-as-tool \| Agent runtime \| Delegation to another agent \|

| State \| Meaning \|

| --- \| --- \|

| draft \| Generated but not validated. \|

| validated \| Schema/security checks passed. \|

| tested \| Sandbox tests passed. \|

| approved \| Human/policy approval completed where required. \|

| published \| Immutable version available to agents. \|

| deprecated \| No new bindings; existing deployments may remain. \|

| revoked \| Execution prohibited. \|

| Entity \| Key relationships \|

| --- \| --- \|

| Agent \| project -\> versions -\> deployments \|

| AgentToolBinding \| agent -\> tool + optional credential +
  policy/config \|

| Tool \| project -\> versions; can be attached to many agents \|

| Skill \| tool-like reusable capability; may be implemented by
  generated artifact \|

| Credential \| project -\> secret reference; never raw secret in agent
  JSON \|

| Execution \| agent deployment/version -\> events + session \|

| Session \| agent -\> messages/executions \|

| Threat \| Control \|

| --- \| --- \|

| Prompt injection \| Treat external content as data; enforce tool
  policy independently of model instructions. \|

| Generated code execution \| Sandbox, resource limits, network
  allowlists, static checks, approval. \|

| Secret leakage \| Secret manager, secret references, redacted logs, no
  secret in prompts. \|

| Privilege escalation \| Capability-based credentials and runtime
  authorization. \|

| Agent recursion \| Depth/call-count/time/budget limits and cycle
  detection. \|

| Data exfiltration \| Network policy + tool-specific data access
  controls. \|

| Unsafe writes \| Separate read/write permissions and human approval.
  \|

| Version drift \| Immutable published versions and deployment pinning.
  \|

| Tenant isolation \| Project/tenant-scoped resources, credentials,
  logs, and execution context. \|

| Audit gaps \| Append-only execution events and admin audit logs. \|

| Phase \| Deliverables \|

| --- \| --- \|

| 1. Runtime foundation \| LiteLLM adapter, Agent class, tool interface,
  registry, execution context. \|

| 2. Control plane \| FastAPI, PostgreSQL models, Agent/Tool/Version
  CRUD, validation. \|

| 3. Agent UI \| Agent list, detail page, configuration inspector,
  test/run panel. \|

| 4. Credentials \| Credential registry, secret manager adapter,
  credential binding and testing. \|

| 5. Tool ecosystem \| HTTP, DB, native Python, MCP, agent-as-tool. \|

| 6. Visual editor \| React Flow graph, node inspector, graph
  serialization, graph patches. \|

| 7. Manager Agent \| Natural-language agent creation and management
  tools. \|

| 8. Dynamic Skills \| LLM code generation, manifest, sandbox, testing,
  versioning. \|

| 9. Policy/HITL \| Permission engine, approval interruptions, audit
  trails. \|

| 10. Deployment/API \| REST/SSE, API keys, sessions, published
  deployments, SDK. \|

| 11. Durable execution \| Queue/worker architecture; add Temporal or
  equivalent when needed. \|

| 12. Enterprise hardening \| Tenant isolation, SSO/RBAC, advanced
  secrets, observability, quotas. \|

| Decision \| Final recommendation \|

| --- \| --- \|

| Product shape \| Agent Control Center / Agent Factory, not only a
  workflow builder. \|

| Manager \| Manager Agent operates declarative agent/resource APIs. \|

| UI \| Agent-first management UI with optional React Flow visual
  editor. \|

| Source of truth \| Versioned declarative resource model, not canvas
  state. \|

| Tool model \| Versioned contract + implementation + permissions +
  requirements. \|

| Generated functions \| Persistent Skills/Tools executed only in an
  isolated runtime. \|

| Credentials \| Separate first-class resources; resolve at execution
  time. \|

| Agents as tools \| Supported as a normal callable capability. \|

| API \| Universal /v1/agents/{id}/run interface with streaming events.
  \|

| Runtime \| Separate workers from API/control services. \|

| Security \| Policy engine + sandbox + capability-based access. \|

| Durability \| Persist execution state; add durable workflow engine for
  long-running runs. \|

| Versioning \| Immutable published versions and pinned deployments. \|
