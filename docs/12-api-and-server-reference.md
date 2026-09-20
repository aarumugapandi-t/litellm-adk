# REST API & Server Reference

The LiteLLM ADK includes a FastAPI server (`src/litellm_adk/server/`) that serves the visual canvas frontend, provides workflow CRUD, orchestrates asynchronous executions, and streams live events over WebSockets.

---

## 1. Running the Server

### Start with Python Module
```bash
python -m litellm_adk.server --host 0.0.0.0 --port 8000 --reload
```

### Start Programmatically
```python
from litellm_adk.server import serve

serve(host="0.0.0.0", port=8000, reload=False)
```

---

## 2. API Endpoints Catalog

All API endpoints are grouped under `/api/v1`:

### Workflows API (`/api/v1/workflows`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/workflows` | Lists all saved workflow definitions. |
| `POST` | `/api/v1/workflows` | Creates a new workflow definition. |
| `GET` | `/api/v1/workflows/{id}` | Retrieves a specific workflow definition by ID. |
| `PUT` | `/api/v1/workflows/{id}` | Updates an existing workflow definition. |
| `DELETE` | `/api/v1/workflows/{id}` | Permanently deletes a workflow. |
| `POST` | `/api/v1/workflows/{id}/activate` | Activates workflow for production triggers. |
| `POST` | `/api/v1/workflows/{id}/deactivate` | Deactivates workflow. |
| `POST` | `/api/v1/workflows/{id}/duplicate` | Creates a copy of an existing workflow. |
| `POST` | `/api/v1/workflows/{id}/execute` | Executes a workflow asynchronously or synchronously. |

#### Workflow Execution Payload
```json
{
  "trigger_data": {
    "user_name": "Alice",
    "tone": "friendly"
  },
  "variables": {
    "default_model": "gpt-4o"
  },
  "run_async": true
}
```

---

### Executions API (`/api/v1/executions`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/executions` | Retrieves execution history (optional query `?workflow_id=...`). |
| `GET` | `/api/v1/executions/{id}` | Gets full `ExecutionState` and audit trail for a specific run. |
| `POST` | `/api/v1/executions/{id}/cancel` | Cancels an active or paused execution. |
| `POST` | `/api/v1/executions/{id}/approve` | Submits a human decision (`approved`, `rejected`) with feedback. |

#### Approval Payload
```json
{
  "approved": true,
  "user_input": "Approved by security team.",
  "selected_option": "approve"
}
```

---

### Master Agent & Synthesis API (`/api/v1/manager`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/manager/status` | Returns Master Agent readiness and active model provider. |
| `POST` | `/api/v1/manager/configure` | Sets model, API key, and optional base URL for the Master Agent. |
| `POST` | `/api/v1/manager/test-connection` | Performs a lightweight probe completion to verify connectivity. |
| `POST` | `/api/v1/manager/synthesize` | Compiles a prompt into `AgentSpec`, dynamic tools, and canvas graph. |
| `POST` | `/api/v1/manager/tools/test` | Runs dynamic tool Python code inside the safe AST sandbox. |
| `GET` | `/api/v1/manager/templates` | Returns starter agent templates. |

---

### Node Metadata Catalog (`/api/v1/metadata/nodes`)

Returns schema, inputs, outputs, and JSON Schema definitions for all registered node types in `node_registry`:

```json
[
  {
    "type": "agent",
    "name": "AI Agent",
    "category": "AI & Agents",
    "inputs": ["input", "tools"],
    "outputs": ["output"],
    "config_schema": { ... }
  },
  {
    "type": "dynamic_tool",
    "name": "Dynamic Tool",
    "category": "Tools",
    "inputs": ["input"],
    "outputs": ["tool", "output"],
    "config_schema": { ... }
  }
]
```

---

## 3. WebSocket Real-Time Event Stream

Connect to `/api/v1/stream/{execution_id}` via WebSocket to receive live execution events:

```javascript
const ws = new WebSocket(`ws://localhost:8000/api/v1/stream/${executionId}`);

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  switch (data.type) {
    case "node.started":
      console.log(`Node started: ${data.node_name}`);
      break;
    case "node.completed":
      console.log(`Node completed in ${data.duration}s`);
      break;
    case "human.required":
      console.warn("Human approval required:", data.approval);
      break;
    case "workflow.completed":
      console.log("Workflow finished:", data.outputs);
      break;
  }
};
```
