import React, { useState, useEffect, useCallback } from "react";
import { useNodesState, useEdgesState, Node, Edge } from "@xyflow/react";
import { Header } from "./components/Header";
import { NodePalette } from "./components/NodePalette";
import { WorkflowCanvas } from "./canvas/WorkflowCanvas";
import { Inspector } from "./components/Inspector";
import { ExecutionDrawer } from "./components/ExecutionDrawer";
import { WorkflowListModal } from "./components/WorkflowListModal";
import { ExecutionHistoryModal } from "./components/ExecutionHistoryModal";
import { api } from "./api/client";
import { streamClient } from "./api/websocket";
import { WorkflowDefinition, NodeDefinition, ExecutionState, WorkflowNode } from "./types/workflow";

// Canonical starter workflow conforming to MVP specs
const DEFAULT_WORKFLOW: WorkflowDefinition = {
  id: "canonical_ai_pipeline",
  name: "AI Research & Approval Pipeline",
  description: "Searches vector memory, synthesizes findings via AI Agent, and gates publication with Human Approval.",
  version: "1.0",
  active: false,
  status: "draft",
  variables: { env: "production", confidence_threshold: 0.8 },
  settings: { timeout: 300, max_concurrency: 5 },
  nodes: [
    {
      id: "trigger_1",
      type: "manual_trigger",
      name: "Manual Start",
      position: { x: 50, y: 150 },
      config: { default_payload: { query: "Latest breakthroughs in Agentic Workflows", user_id: "usr_99" } },
      inputs: [],
      outputs: ["output"],
    },
    {
      id: "vector_1",
      type: "vector_search",
      name: "Knowledge Search",
      position: { x: 340, y: 150 },
      config: { query: "{{ trigger.query }}", top_k: 3 },
      inputs: ["input"],
      outputs: ["output"],
    },
    {
      id: "agent_1",
      type: "agent",
      name: "Research Agent",
      position: { x: 630, y: 150 },
      config: {
        model: "openai/gpt-4o-mini",
        prompt: "Synthesize these findings for executive review: {{ vector_1.output }}",
        system_prompt: "You are a senior technical analyst. Summarize findings clearly.",
      },
      inputs: ["input"],
      outputs: ["output"],
    },
    {
      id: "human_1",
      type: "human",
      name: "Executive Approval",
      position: { x: 920, y: 150 },
      config: { message: "Please review and approve publication of the agent report." },
      inputs: ["input"],
      outputs: ["approved", "rejected"],
    },
    {
      id: "output_1",
      type: "output",
      name: "Publication Output",
      position: { x: 1210, y: 150 },
      config: { response: "{{ agent_1.output }}" },
      inputs: ["input"],
      outputs: [],
    },
  ],
  edges: [
    { id: "e1", source: "trigger_1", target: "vector_1" },
    { id: "e2", source: "vector_1", target: "agent_1" },
    { id: "e3", source: "agent_1", target: "human_1" },
    { id: "e4", source: "human_1", target: "output_1", sourceHandle: "approved" },
  ],
};

export default function App() {
  const [workflow, setWorkflow] = useState<WorkflowDefinition>(DEFAULT_WORKFLOW);
  const [availableNodes, setAvailableNodes] = useState<NodeDefinition[]>([]);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [executionState, setExecutionState] = useState<ExecutionState | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [isWorkflowsModalOpen, setIsWorkflowsModalOpen] = useState(false);
  const [isHistoryModalOpen, setIsHistoryModalOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [isSubmittingApproval, setIsSubmittingApproval] = useState(false);

  // React Flow state
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  // Load available node schemas and initial workflow
  useEffect(() => {
    async function init() {
      try {
        const defs = await api.getAvailableNodes();
        setAvailableNodes(defs);

        const wfs = await api.getWorkflows();
        if (wfs.length > 0) {
          loadWorkflowIntoCanvas(wfs[0]);
        } else {
          loadWorkflowIntoCanvas(DEFAULT_WORKFLOW);
          await api.saveWorkflow(DEFAULT_WORKFLOW);
        }
      } catch (err) {
        console.warn("Could not connect to backend, running in offline mode:", err);
        loadWorkflowIntoCanvas(DEFAULT_WORKFLOW);
      }
    }
    init();
  }, []);

  const loadWorkflowIntoCanvas = (wf: WorkflowDefinition) => {
    setWorkflow(wf);
    setSelectedNode(null);

    const mappedNodes: Node[] = wf.nodes.map((n) => ({
      id: n.id,
      type: "custom",
      position: n.position,
      data: {
        id: n.id,
        type: n.type,
        name: n.name,
        category: getCategoryForType(n.type),
        description: "",
        inputs: n.inputs,
        outputs: n.outputs,
        config: n.config || {},
        status: "idle",
      },
    }));

    const mappedEdges: Edge[] = wf.edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      sourceHandle: e.sourceHandle || undefined,
      targetHandle: e.targetHandle || undefined,
      animated: true,
      style: { stroke: "#38bdf8", strokeWidth: 2 },
    }));

    setNodes(mappedNodes);
    setEdges(mappedEdges);
  };

  const getCategoryForType = (type: string) => {
    if (type.includes("trigger")) return "Triggers";
    if (type === "agent" || type === "llm") return "AI & Agents";
    if (type === "tool") return "Tools";
    if (type === "memory" || type === "vector_search") return "Memory & Vector";
    if (type === "condition" || type === "transform") return "Logic & Control";
    if (type === "human") return "Human in the Loop";
    if (type === "output") return "Input & Output";
    return "AI & Agents";
  };

  // Convert canvas state back to WorkflowDefinition
  const getWorkflowFromCanvas = (): WorkflowDefinition => {
    const wfNodes: WorkflowNode[] = nodes.map((n) => ({
      id: n.id,
      type: n.data.type as string,
      name: n.data.name as string,
      position: n.position,
      config: (n.data.config as Record<string, any>) || {},
      inputs: (n.data.inputs as string[]) || [],
      outputs: (n.data.outputs as string[]) || [],
    }));

    const wfEdges = edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      sourceHandle: e.sourceHandle || null,
      targetHandle: e.targetHandle || null,
    }));

    return {
      ...workflow,
      nodes: wfNodes,
      edges: wfEdges,
    };
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const current = getWorkflowFromCanvas();
      const saved = await api.saveWorkflow(current);
      setWorkflow(saved);
    } catch (err: any) {
      alert(`Save failed: ${err.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleTestRun = async () => {
    setIsRunning(true);
    setIsDrawerOpen(true);

    // Reset node status on canvas
    setNodes((nds) =>
      nds.map((n) => ({
        ...n,
        data: { ...n.data, status: "idle", duration: undefined },
      }))
    );

    try {
      // First save latest graph
      const current = getWorkflowFromCanvas();
      await api.saveWorkflow(current);

      const triggerPayload =
        current.nodes.find((n) => n.type.includes("trigger"))?.config?.default_payload || {};

      const res = await api.executeWorkflow(current.id, triggerPayload, true);

      // Connect WebSocket stream
      streamClient.disconnect();
      streamClient.connect(res.execution_id);

      streamClient.subscribe((event) => {
        if (event.type === "node.started") {
          setNodes((nds) =>
            nds.map((n) =>
              n.id === event.node_id ? { ...n, data: { ...n.data, status: "running" } } : n
            )
          );
        } else if (event.type === "node.completed") {
          setNodes((nds) =>
            nds.map((n) =>
              n.id === event.node_id
                ? { ...n, data: { ...n.data, status: "completed", duration: event.duration } }
                : n
            )
          );
        } else if (event.type === "node.failed") {
          setNodes((nds) =>
            nds.map((n) =>
              n.id === event.node_id ? { ...n, data: { ...n.data, status: "failed" } } : n
            )
          );
        } else if (event.type === "human.required") {
          setNodes((nds) =>
            nds.map((n) =>
              n.id === event.node_id ? { ...n, data: { ...n.data, status: "waiting_for_human" } } : n
            )
          );
        }

        // Fetch execution state snapshot
        api.getExecution(res.execution_id).then(setExecutionState).catch(console.warn);

        if (event.type === "workflow.completed" || event.type === "workflow.failed") {
          setIsRunning(false);
        }
      });
    } catch (err: any) {
      alert(`Execution failed: ${err.message}`);
      setIsRunning(false);
    }
  };

  const handleApprove = async (approved: boolean, userInput?: string, selectedOption?: string) => {
    if (!executionState) return;
    setIsSubmittingApproval(true);
    try {
      await api.approveExecution(executionState.execution_id, approved, userInput, selectedOption);
    } catch (err: any) {
      alert(`Approval error: ${err.message}`);
    } finally {
      setIsSubmittingApproval(false);
    }
  };

  const handleAddNodeFromPalette = (def: NodeDefinition) => {
    const newNode: Node = {
      id: `${def.type}_${Date.now().toString().slice(-5)}`,
      type: "custom",
      position: { x: 300 + Math.random() * 100, y: 200 + Math.random() * 100 },
      data: {
        id: `${def.type}_${Date.now().toString().slice(-5)}`,
        type: def.type,
        name: def.name,
        category: def.category,
        description: def.description,
        inputs: def.inputs,
        outputs: def.outputs,
        config: {},
        status: "idle",
      },
    };
    setNodes((nds) => nds.concat(newNode));
    setSelectedNode(newNode);
  };

  const handleUpdateNodeData = (nodeId: string, updatedData: any) => {
    setNodes((nds) =>
      nds.map((n) => (n.id === nodeId ? { ...n, data: { ...n.data, ...updatedData } } : n))
    );
    if (selectedNode && selectedNode.id === nodeId) {
      setSelectedNode((prev) => (prev ? { ...prev, data: { ...prev.data, ...updatedData } } : null));
    }
  };

  const handleDeleteNode = (nodeId: string) => {
    setNodes((nds) => nds.filter((n) => n.id !== nodeId));
    setEdges((eds) => eds.filter((e) => e.source !== nodeId && e.target !== nodeId));
    setSelectedNode(null);
  };

  const handleExport = () => {
    const current = getWorkflowFromCanvas();
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(current, null, 2));
    const dl = document.createElement("a");
    dl.setAttribute("href", dataStr);
    dl.setAttribute("download", `${current.id || "workflow"}.json`);
    dl.click();
  };

  const handleImport = () => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".json";
    input.onchange = (e: any) => {
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (event) => {
        try {
          const parsed = JSON.parse(event.target?.result as string);
          loadWorkflowIntoCanvas(parsed);
        } catch (err) {
          alert("Invalid JSON file.");
        }
      };
      reader.readAsText(file);
    };
    input.click();
  };

  return (
    <div className="flex flex-col h-screen w-screen bg-[#0b0f19] text-slate-100 overflow-hidden font-sans">
      <Header
        workflow={workflow}
        onUpdateWorkflow={(updated) => setWorkflow((prev) => ({ ...prev, ...updated }))}
        onSave={handleSave}
        onTestRun={handleTestRun}
        onOpenWorkflowsList={() => setIsWorkflowsModalOpen(true)}
        onOpenHistory={() => setIsHistoryModalOpen(true)}
        onExport={handleExport}
        onImport={handleImport}
        isSaving={isSaving}
        isRunning={isRunning}
      />

      <div className="flex-1 flex relative overflow-hidden">
        <NodePalette availableNodes={availableNodes} onAddNode={handleAddNodeFromPalette} />

        <main className="flex-1 h-full relative">
          <WorkflowCanvas
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            setNodes={setNodes}
            setEdges={setEdges}
            onSelectNode={setSelectedNode}
            availableNodes={availableNodes}
          />
        </main>

        <Inspector
          selectedNode={selectedNode}
          availableNodes={availableNodes}
          onUpdateNodeData={handleUpdateNodeData}
          onDeleteNode={handleDeleteNode}
          executionRecord={
            selectedNode && executionState?.node_records
              ? executionState.node_records[selectedNode.id]
              : null
          }
        />
      </div>

      <ExecutionDrawer
        executionState={executionState}
        isOpen={isDrawerOpen}
        onToggle={() => setIsDrawerOpen((prev) => !prev)}
        onApprove={handleApprove}
        isSubmittingApproval={isSubmittingApproval}
      />

      <WorkflowListModal
        isOpen={isWorkflowsModalOpen}
        onClose={() => setIsWorkflowsModalOpen(false)}
        onSelectWorkflow={(wf) => {
          loadWorkflowIntoCanvas(wf);
          setIsWorkflowsModalOpen(false);
        }}
        onCreateNew={() => {
          const newWf: WorkflowDefinition = {
            ...DEFAULT_WORKFLOW,
            id: `wf_${Date.now().toString().slice(-6)}`,
            name: "New AI Workflow",
            nodes: [DEFAULT_WORKFLOW.nodes[0]],
            edges: [],
          };
          loadWorkflowIntoCanvas(newWf);
          setIsWorkflowsModalOpen(false);
        }}
      />

      <ExecutionHistoryModal
        isOpen={isHistoryModalOpen}
        onClose={() => setIsHistoryModalOpen(false)}
        workflowId={workflow.id}
        onSelectExecution={(exec) => {
          setExecutionState(exec);
          setIsDrawerOpen(true);
        }}
      />
    </div>
  );
}
