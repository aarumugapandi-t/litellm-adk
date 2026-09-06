import React, { useCallback, useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Connection,
  Edge,
  Node,
  addEdge,
  useNodesState,
  useEdgesState,
  BackgroundVariant,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
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
  const nodeTypes = useMemo(() => ({ custom: CustomNode }), []);

  const onConnect = useCallback(
    (connection: Connection) => {
      setEdges((eds) =>
        addEdge(
          {
            ...connection,
            animated: true,
            style: { stroke: "#38bdf8", strokeWidth: 2 },
          },
          eds
        )
      );
    },
    [setEdges]
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
