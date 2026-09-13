import { Node, Edge } from "@xyflow/react";

export interface VariableItem {
  key: string;
  label: string;
  category: "Trigger" | "Upstream Output" | "Workflow Variable";
  nodeId?: string;
  nodeName?: string;
  description: string;
  type?: string;
}

/**
 * Traverses backwards through DAG edges to find all ancestor nodes that execute before targetNodeId.
 */
export function getUpstreamNodes(
  targetNodeId: string,
  nodes: Node[],
  edges: Edge[]
): Node[] {
  const nodeMap = new Map<string, Node>(nodes.map((n) => [n.id, n]));
  const upstreamIds = new Set<string>();
  const queue: string[] = [];

  // Initial immediate parents
  for (const edge of edges) {
    if (edge.target === targetNodeId) {
      queue.push(edge.source);
    }
  }

  while (queue.length > 0) {
    const currId = queue.shift()!;
    if (!upstreamIds.has(currId)) {
      upstreamIds.add(currId);
      for (const edge of edges) {
        if (edge.target === currId) {
          queue.push(edge.source);
        }
      }
    }
  }

  return nodes.filter((n) => upstreamIds.has(n.id));
}

/**
 * Compiles a catalog of all valid upstream node outputs and workflow variables available to targetNodeId.
 */
export function getAvailableVariables(
  targetNodeId: string | null,
  nodes: Node[],
  edges: Edge[],
  workflowVariables: Record<string, any> = {}
): VariableItem[] {
  const items: VariableItem[] = [];

  // 1. Upstream Nodes
  const upstream = targetNodeId ? getUpstreamNodes(targetNodeId, nodes, edges) : nodes;

  for (const node of upstream) {
    const nodeType = (node.data?.type as string) || "";
    const nodeName = (node.data?.name as string) || node.id;
    const config = (node.data?.config as Record<string, any>) || {};

    if (nodeType.includes("trigger")) {
      items.push({
        key: "trigger.input",
        label: `${nodeName} → input`,
        category: "Trigger",
        nodeId: node.id,
        nodeName,
        description: "Entire incoming trigger payload",
        type: "object",
      });

      // Look for default payload fields
      const payload = config.default_payload || {};
      if (typeof payload === "object") {
        for (const k of Object.keys(payload)) {
          items.push({
            key: `trigger.${k}`,
            label: `${nodeName} → ${k}`,
            category: "Trigger",
            nodeId: node.id,
            nodeName,
            description: `Trigger parameter '${k}'`,
            type: typeof payload[k],
          });
        }
      }
    } else if (nodeType === "agent") {
      items.push({
        key: `${node.id}.output`,
        label: `${nodeName} → output (text)`,
        category: "Upstream Output",
        nodeId: node.id,
        nodeName,
        description: "Agent final response text",
        type: "string",
      });
      items.push({
        key: `${node.id}.output.tool_calls`,
        label: `${nodeName} → tool calls`,
        category: "Upstream Output",
        nodeId: node.id,
        nodeName,
        description: "List of tool invocations performed",
        type: "array",
      });
    } else if (nodeType === "llm") {
      items.push({
        key: `${node.id}.output`,
        label: `${nodeName} → output`,
        category: "Upstream Output",
        nodeId: node.id,
        nodeName,
        description: "Generated LLM completion text",
        type: "string",
      });
    } else if (nodeType === "web_search_tool") {
      items.push({
        key: `${node.id}.output`,
        label: `${nodeName} → search results`,
        category: "Upstream Output",
        nodeId: node.id,
        nodeName,
        description: "Synthesized web search snippets and sources",
        type: "string",
      });
    } else if (nodeType === "vector_search") {
      items.push({
        key: `${node.id}.output`,
        label: `${nodeName} → retrieved context`,
        category: "Upstream Output",
        nodeId: node.id,
        nodeName,
        description: "Top-k semantic matches and chunks",
        type: "array",
      });
    } else if (nodeType === "human") {
      items.push({
        key: `${node.id}.output.approved`,
        label: `${nodeName} → approval decision`,
        category: "Upstream Output",
        nodeId: node.id,
        nodeName,
        description: "True if approved, False if rejected",
        type: "boolean",
      });
      items.push({
        key: `${node.id}.output.user_input`,
        label: `${nodeName} → reviewer comment`,
        category: "Upstream Output",
        nodeId: node.id,
        nodeName,
        description: "Human reviewer feedback comment",
        type: "string",
      });
    } else {
      items.push({
        key: `${node.id}.output`,
        label: `${nodeName} → output`,
        category: "Upstream Output",
        nodeId: node.id,
        nodeName,
        description: `Output data from ${nodeName}`,
        type: "any",
      });
    }
  }

  // 2. Workflow Variables
  for (const [vKey, vVal] of Object.entries(workflowVariables)) {
    items.push({
      key: `variables.${vKey}`,
      label: `variables.${vKey}`,
      category: "Workflow Variable",
      description: `Workflow variable: ${String(vVal).slice(0, 30)}`,
      type: typeof vVal,
    });
  }

  return items;
}
