import {
  WorkflowDefinition,
  NodeDefinition,
  ExecutionState,
} from "../types/workflow";

const API_BASE = "/api/v1";

export const api = {
  async getWorkflows(): Promise<WorkflowDefinition[]> {
    const res = await fetch(`${API_BASE}/workflows`);
    if (!res.ok) throw new Error("Failed to fetch workflows");
    return res.json();
  },

  async getWorkflow(id: string): Promise<WorkflowDefinition> {
    const res = await fetch(`${API_BASE}/workflows/${id}`);
    if (!res.ok) throw new Error(`Workflow '${id}' not found`);
    return res.json();
  },

  async saveWorkflow(workflow: WorkflowDefinition): Promise<WorkflowDefinition> {
    // If workflow already exists, PUT; else POST
    let res = await fetch(`${API_BASE}/workflows/${workflow.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(workflow),
    });

    if (res.status === 404) {
      res = await fetch(`${API_BASE}/workflows`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(workflow),
      });
    }

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to save workflow");
    }

    const data = await res.json();
    return data.workflow || workflow;
  },

  async deleteWorkflow(id: string): Promise<void> {
    const res = await fetch(`${API_BASE}/workflows/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error("Failed to delete workflow");
  },

  async activateWorkflow(id: string): Promise<void> {
    const res = await fetch(`${API_BASE}/workflows/${id}/activate`, { method: "POST" });
    if (!res.ok) throw new Error("Failed to activate workflow");
  },

  async deactivateWorkflow(id: string): Promise<void> {
    const res = await fetch(`${API_BASE}/workflows/${id}/deactivate`, { method: "POST" });
    if (!res.ok) throw new Error("Failed to deactivate workflow");
  },

  async duplicateWorkflow(id: string): Promise<WorkflowDefinition> {
    const res = await fetch(`${API_BASE}/workflows/${id}/duplicate`, { method: "POST" });
    if (!res.ok) throw new Error("Failed to duplicate workflow");
    const data = await res.json();
    return data.workflow;
  },

  async executeWorkflow(
    workflowId: string,
    triggerData: any = {},
    runAsync: boolean = true
  ): Promise<{ execution_id: string; status: string; outputs?: any }> {
    const res = await fetch(`${API_BASE}/workflows/${workflowId}/execute`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ trigger_data: triggerData, run_async: runAsync }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to execute workflow");
    }
    return res.json();
  },

  async getExecutions(workflowId?: string): Promise<any[]> {
    const query = workflowId ? `?workflow_id=${encodeURIComponent(workflowId)}` : "";
    const res = await fetch(`${API_BASE}/executions${query}`);
    if (!res.ok) throw new Error("Failed to fetch executions");
    return res.json();
  },

  async getExecution(id: string): Promise<ExecutionState> {
    const res = await fetch(`${API_BASE}/executions/${id}`);
    if (!res.ok) throw new Error(`Execution '${id}' not found`);
    return res.json();
  },

  async approveExecution(
    id: string,
    approved: boolean,
    userInput?: string,
    selectedOption?: string
  ): Promise<any> {
    const res = await fetch(`${API_BASE}/executions/${id}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        approved,
        user_input: userInput,
        selected_option: selectedOption,
      }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to submit approval");
    }
    return res.json();
  },

  async getAvailableNodes(): Promise<NodeDefinition[]> {
    const res = await fetch(`${API_BASE}/nodes`);
    if (!res.ok) throw new Error("Failed to load node registry");
    return res.json();
  },

  async getTools(): Promise<any[]> {
    const res = await fetch(`${API_BASE}/tools`);
    if (!res.ok) return [];
    return res.json();
  },
};
