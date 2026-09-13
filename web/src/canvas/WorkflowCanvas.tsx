import React, { useCallback, useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Connection,
  Edge,
  Node,
  addEdge,
  BackgroundVariant,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Zap, Info, ChevronDown, ChevronUp, Wrench } from "lucide-react";
import { CustomNode } from "./CustomNode";
import { NodeDefinition } from "../types/workflow";

interface WorkflowCanvasProps {
  nodes: Node[];
  edges: Edge[];
  onNodesChange: any;
  onEdgesChange: any;
  setNodes: React.Dispatch<React.SetStateAction<Node[]>>;
  setEdges: React.Dispatch<React.SetStateAction<Edge[]>>;
  onSelectNode: (node: Node | null) => void;
  availableNodes: NodeDefinition[];
}

export const WorkflowCanvas: React.FC<WorkflowCanvasProps> = ({
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  setNodes,
  setEdges,
  onSelectNode,
  availableNodes,
}) => {
  const [showGuide, setShowGuide] = useState(true);
  const nodeTypes = useMemo(() => ({ custom: CustomNode }), []);

  const onConnect = useCallback(
    (connection: Connection) => {
      const sourceNode = nodes.find((n) => n.id === connection.source);
      const targetNode = nodes.find((n) => n.id === connection.target);

      const isToolSource =
        connection.sourceHandle === "tool" ||
        sourceNode?.data?.type?.toString().includes("tool") ||
        sourceNode?.data?.category === "Tools";

      const isAgentTarget = targetNode?.data?.type === "agent";
      const isToolWire = isToolSource && isAgentTarget;

      const effectiveTargetHandle = isToolWire
        ? "tools"
        : connection.targetHandle || "input";
      const effectiveSourceHandle = isToolWire
        ? "tool"
        : connection.sourceHandle || "output";

      setEdges((eds) =>
        addEdge(
          {
            ...connection,
            sourceHandle: effectiveSourceHandle,
            targetHandle: effectiveTargetHandle,
            animated: true,
            label: isToolWire ? "🧩 Tool" : undefined,
            labelStyle: isToolWire
              ? { fill: "#34d399", fontWeight: 600, fontSize: 10 }
              : undefined,
            labelBgStyle: isToolWire
              ? { fill: "#064e3b", fillOpacity: 0.9, rx: 4, ry: 4 }
              : undefined,
            labelBgPadding: isToolWire ? [6, 2] : undefined,
            style: {
              stroke: isToolWire ? "#34d399" : "#38bdf8",
              strokeWidth: isToolWire ? 2.5 : 2,
            },
          },
          eds
        )
      );
    },
    [nodes, setEdges]
  );

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const nodeType = event.dataTransfer.getData("application/reactflow-type");
      if (!nodeType) return;

      const def = availableNodes.find((n) => n.type === nodeType);
      if (!def) return;

      const bounds = event.currentTarget.getBoundingClientRect();
      const position = {
        x: event.clientX - bounds.left - 120,
        y: event.clientY - bounds.top - 40,
      };

      const newNode: Node = {
        id: `${nodeType}_${Date.now().toString().slice(-5)}`,
        type: "custom",
        position,
        data: {
          id: `${nodeType}_${Date.now().toString().slice(-5)}`,
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
      onSelectNode(newNode);
    },
    [availableNodes, setNodes, onSelectNode]
  );

  const onSelectionChange = useCallback(
    ({ nodes: selectedNodes }: { nodes: Node[] }) => {
      if (selectedNodes.length > 0) {
        onSelectNode(selectedNodes[0]);
      } else {
        onSelectNode(null);
      }
    },
    [onSelectNode]
  );

  return (
    <div className="w-full h-full relative" onDragOver={onDragOver} onDrop={onDrop}>
      {/* Floating Canvas Wiring Guide */}
      <div className="absolute top-3 left-3 z-10 bg-[#0f172a]/90 backdrop-blur-md border border-slate-800/90 rounded-xl shadow-2xl overflow-hidden transition-all duration-200 select-none max-w-sm">
        <div
          onClick={() => setShowGuide((prev) => !prev)}
          className="flex items-center justify-between px-3 py-2 bg-slate-900/60 hover:bg-slate-900 cursor-pointer border-b border-slate-800/60"
        >
          <div className="flex items-center gap-1.5 text-xs font-bold text-slate-200">
            <Zap className="w-3.5 h-3.5 text-sky-400" />
            <span>Workflow Wiring Guide</span>
          </div>
          <button className="text-slate-400 hover:text-slate-200 text-xs">
            {showGuide ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
        </div>

        {showGuide && (
          <div className="p-3 space-y-2 text-[11px] bg-[#0f172a]/95">
            <div className="flex items-start gap-2.5 bg-slate-900/60 p-2 rounded-lg border border-slate-800">
              <span className="w-2.5 h-2.5 rounded-full bg-sky-400 mt-1 shrink-0 shadow-sm shadow-sky-400/40" />
              <div>
                <div className="font-semibold text-sky-300">Data Flow (Blue Wire)</div>
                <div className="text-slate-400 text-[10px] leading-snug">
                  Connect <span className="text-sky-300 font-mono">[📤 Data Out]</span> ──► <span className="text-sky-300 font-mono">[📥 Data In]</span> to send user inputs & pipeline responses downstream.
                </div>
              </div>
            </div>

            <div className="flex items-start gap-2.5 bg-emerald-950/30 p-2 rounded-lg border border-emerald-800/40">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 mt-1 shrink-0 shadow-sm shadow-emerald-400/50" />
              <div>
                <div className="font-semibold text-emerald-300">Tool Attachment (Green Wire)</div>
                <div className="text-slate-400 text-[10px] leading-snug">
                  Connect Tool <span className="text-emerald-300 font-mono">[🧩 Tool Out]</span> ──► Agent <span className="text-emerald-300 font-mono">[🧩 Tools In]</span> to equip the AI with live search & math.
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onSelectionChange={onSelectionChange}
        nodeTypes={nodeTypes}
        fitView
        className="bg-[#0b0f19]"
        defaultEdgeOptions={{
          animated: true,
          style: { stroke: "#38bdf8", strokeWidth: 2 },
        }}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1.5} color="#1e293b" />
        <Controls className="!bg-[#1e293b] !border-slate-700 !fill-slate-200 !rounded-lg overflow-hidden shadow-xl" />
        <MiniMap
          className="!bg-[#111827] !border !border-slate-800 !rounded-lg overflow-hidden"
          nodeColor={(node) => {
            if (node.data?.status === "completed") return "#10b981";
            if (node.data?.status === "running") return "#38bdf8";
            if (node.data?.status === "waiting_for_human") return "#f59e0b";
            if (node.data?.status === "failed") return "#f43f5e";
            return "#334155";
          }}
          maskColor="rgba(15, 23, 42, 0.7)"
        />
      </ReactFlow>
    </div>
  );
};
