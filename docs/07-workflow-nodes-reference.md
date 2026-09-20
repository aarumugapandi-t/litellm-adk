# Workflow Nodes Reference

This reference documents the complete catalog of visual workflow nodes available in the LiteLLM ADK (`src/litellm_adk/workflow/nodes/`). All nodes inherit from `BaseNode` and are registered in `node_registry`.

---

## 1. Node Types Overview

| Node Type | Category | Inputs | Outputs | Description |
|---|---|---|---|---|
| `manual_trigger` | Triggers | None | `output` | Initiates workflow manually from UI or API with custom payload. |
| `webhook_trigger` | Triggers | None | `output` | Listens for external incoming HTTP POST requests. |
| `agent` | AI & Agents | `input`, `tools` | `output` | Multi-turn autonomous agent with tool calling and memory. |
| `dynamic_tool` | Tools | `input` (optional) | `tool`, `output` | Synthesized Python tool executing in AST-safe sandbox. |
| `web_search_tool` | Tools | None | `tool` | Live Internet search via Google/DuckDuckGo. |
| `calculator_tool` | Tools | None | `tool` | Safe arithmetic evaluation. |
| `http_tool` | Tools | `input` (optional) | `tool`, `output` | Generic REST API client. |
| `transform` | Logic & Control | `input` | `output` | JSON and template data transformation. |
| `condition` | Logic & Control | `input` | `true`, `false` | Conditional branching based on expression evaluation. |
| `human` | Human in the Loop | `input` | `approved`, `rejected` | Pauses execution until a human operator signs off. |
| `output` | Input & Output | `input` | None | Collects and returns the final workflow response. |

---

## 2. Detailed Node Specifications

### 1. `manual_trigger`
- **Description**: Starting point for manual test runs or API-triggered workflows.
- **Config Schema**:
  ```json
  {
    "default_payload": {
      "user_name": "Alice",
      "tone": "friendly"
    }
  }
  ```
- **Output**: Emits the provided `trigger_data` or `default_payload`.

---

### 2. `agent` (AI Agent)
- **Description**: Executes a multi-turn LLM reasoning loop with connected tools.
- **Handles**:
  - `input`: Primary data input from upstream nodes.
  - `tools`: Green socket accepting incoming wires from tool nodes (`dynamic_tool`, `web_search_tool`, etc.).
  - `output`: Final text or structured output produced by the agent.
- **Config Schema**:
  ```json
  {
    "model": "gpt-4o",
    "api_key": "sk-...",
    "base_url": "http://localhost:9000/v1",
    "system_prompt": "You are a specialized customer assistant.",
    "prompt": "Address this request: {{ trigger_1.query }}",
    "max_iterations": 10,
    "temperature": 0.7,
    "use_workflow_credentials": true
  }
  ```

---

### 3. `dynamic_tool`
- **Description**: Synthesized Python tool executing inside the AST-safe sandbox.
- **Handles**:
  - `input` (optional): If wired in a pipeline, executes tool directly with input args.
  - `tool`: Green handle wired into an Agent's `tools` socket.
  - `output`: Result of direct execution (if triggered in pipeline).
- **Config Schema**:
  ```json
  {
    "tool_name": "generate_greeting",
    "description": "Generates a personalized welcome greeting.",
    "parameters": {
      "type": "object",
      "properties": {
        "user_name": {"type": "string"}
      },
      "required": ["user_name"]
    },
    "code": "def run(user_name: str):\n    return {'message': f'Hello, {user_name}!'}",
    "timeout_seconds": 5.0,
    "approval_required": false
  }
  ```

---

### 4. `transform`
- **Description**: Reshapes data using expression templates.
- **Config Schema**:
  ```json
  {
    "template": {
      "greeting_text": "Hello, {{ trigger.user_name }}!",
      "processed_at": "{{ execution.id }}"
    }
  }
  ```

---

### 5. `condition`
- **Description**: Evaluates a boolean expression and routes execution to either the `true` or `false` output handle.
- **Config Schema**:
  ```json
  {
    "expression": "{{ agent_1.output.risk_score }} > 75"
  }
  ```
- **Branching**: If the expression evaluates to `true`, only the edge connected to the `true` handle activates; the `false` path is marked inactive.

---

### 6. `human` (Human in the Loop)
- **Description**: Halts workflow execution until an operator approves or rejects the request.
- **Config Schema**:
  ```json
  {
    "message": "Please review order cancellation request for {{ trigger_1.order_id }}.",
    "timeout_minutes": 1440
  }
  ```
- **Outputs**:
  - `approved`: Traversed if the user selects Approve.
  - `rejected`: Traversed if the user selects Reject.

---

### 7. `output`
- **Description**: Terminal node representing the result of the workflow.
- **Config Schema**:
  ```json
  {
    "response": "{{ agent_1.output }}"
  }
  ```
