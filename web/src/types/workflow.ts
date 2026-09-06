export interface NodePosition {
  x: number;
  y: number;
}

export interface WorkflowNode {
  id: string;
  type: string;
  name: string;
  version?: string;
  position: NodePosition;
  config: Record<string, any>;
  inputs: string[];
  outputs: string[];
}

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string | null;
  targetHandle?: string | null;
}

export interface WorkflowSettings {
  timeout: number;
  max_concurrency: number;
  retry_policy?: Record<string, any>;
}

export type WorkflowStatus = "draft" | "active" | "inactive" | "archived";

export interface WorkflowDefinition {
  id: string;
  name: string;
  description?: string;
  version: string;
  active: boolean;
  status: WorkflowStatus;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  variables: Record<string, any>;
  settings: WorkflowSettings;
  created_at?: string;
  updated_at?: string;
}

export interface NodeDefinition {
  type: string;
  name: string;
  description: string;
  category: string;
  icon: string;
  inputs: string[];
  outputs: string[];
  config_schema: Record<string, any>;
}

export type ExecutionStatus =
  | "idle"
  | "pending"
  | "running"
  | "waiting_for_human"
  | "completed"
  | "failed"
  | "cancelled";

export interface NodeExecutionRecord {
  id: string;
  node_id: string;
  node_type: string;
  status: ExecutionStatus;
  input_data?: any;
  output_data?: any;
  error?: string | null;
  duration: number;
  started_at?: string;
  finished_at?: string;
}

export interface ExecutionState {
  execution_id: string;
  workflow_id: string;
  workflow_version: string;
  status: ExecutionStatus;
  trigger_data: Record<string, any>;
  current_nodes: string[];
  completed_nodes: string[];
  node_outputs: Record<string, any>;
  node_records: Record<string, NodeExecutionRecord>;
  variables: Record<string, any>;
  pending_approval?: {
    node_id?: string;
    message?: string;
    approval_type?: string;
    options?: string[];
  } | null;
  errors: string[];
  started_at?: string;
  finished_at?: string;
  total_duration: number;
  total_tokens: number;
  estimated_cost: number;
}
