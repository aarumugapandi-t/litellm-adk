import React, { memo, useState } from "react";
import { Handle, Position, NodeProps, useEdges, useNodes } from "@xyflow/react";
import {
  PlayCircle,
  Sparkles,
  Bot,
  Wrench,
  Database,
  Search,
  GitBranch,
  Binary,
  UserCheck,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  Loader2,
  Clock,
  Globe,
  Calculator,
  ExternalLink,
  Key,
  Plus,
} from "lucide-react";
import { ExecutionStatus } from "../types/workflow";

// Icon mapping based on node type
const ICON_MAP: Record<string, React.ElementType> = {
  manual_trigger: PlayCircle,
  webhook_trigger: PlayCircle,
  llm: Sparkles,
  agent: Bot,
  tool: Wrench,
  web_search_tool: Globe,
  calculator_tool: Calculator,
  http_tool: ExternalLink,
  memory: Database,
  vector_search: Search,
  condition: GitBranch,
  transform: Binary,
  human: UserCheck,
  output: CheckCircle2,
};

// Category theme colors
const CATEGORY_STYLES: Record<string, { bg: string; border: string; text: string; badge: string }> = {
  Triggers: { bg: "bg-amber-950/30", border: "border-amber-500/40", text: "text-amber-400", badge: "bg-amber-500/20 text-amber-300" },
  "AI & Agents": { bg: "bg-blue-950/30", border: "border-blue-500/40", text: "text-blue-400", badge: "bg-blue-500/20 text-blue-300" },
  Tools: { bg: "bg-emerald-950/30", border: "border-emerald-500/40", text: "text-emerald-400", badge: "bg-emerald-500/20 text-emerald-300" },
  "Memory & Vector": { bg: "bg-indigo-950/30", border: "border-indigo-500/40", text: "text-indigo-400", badge: "bg-indigo-500/20 text-indigo-300" },
  "Logic & Control": { bg: "bg-violet-950/30", border: "border-violet-500/40", text: "text-violet-400", badge: "bg-violet-500/20 text-violet-300" },
  "Human in the Loop": { bg: "bg-rose-950/30", border: "border-rose-500/40", text: "text-rose-400", badge: "bg-rose-500/20 text-rose-300" },
  "Input & Output": { bg: "bg-slate-900/50", border: "border-slate-500/40", text: "text-slate-300", badge: "bg-slate-500/20 text-slate-300" },
};

export const CustomNode = memo(({ id, data, selected }: NodeProps) => {
  const edges = useEdges();
  const nodes = useNodes();

  const nodeType = (data.type as string) || "agent";
  const category = (data.category as string) || "AI & Agents";
  const name = (data.name as string) || "Node";
  const status = (data.status as ExecutionStatus) || "idle";
  const duration = data.duration as number | undefined;
  const config = (data.config as Record<string, any>) || {};

  const IconComponent = ICON_MAP[nodeType] || Bot;
  const style = CATEGORY_STYLES[category] || CATEGORY_STYLES["AI & Agents"];

  // Dynamic execution border styling
  let statusBorder = style.border;
  let statusGlow = "";
  if (status === "running") {
    statusBorder = "border-blue-400 animate-pulse";
    statusGlow = "ring-2 ring-blue-500/50 shadow-lg shadow-blue-500/20";
  } else if (status === "completed") {
    statusBorder = "border-emerald-500";
    statusGlow = "ring-1 ring-emerald-500/40";
  } else if (status === "waiting_for_human") {
    statusBorder = "border-amber-400 animate-bounce";
    statusGlow = "ring-2 ring-amber-500/60 shadow-lg shadow-amber-500/30";
  } else if (status === "failed") {
    statusBorder = "border-rose-500";
    statusGlow = "ring-2 ring-rose-500/50";
  }

  const isSelected = selected ? "ring-2 ring-sky-400 shadow-xl" : "";

  const inputs: string[] = (data.inputs as string[]) || [];
  const outputs: string[] = (data.outputs as string[]) || [];

  const [showToolMenu, setShowToolMenu] = useState(false);

  // Visual tool discovery for Agent nodes
  const connectedToolEdges = edges.filter(
    (e) => e.target === id && (e.targetHandle === "tools" || !e.targetHandle)
  );
  const visualToolNodes = connectedToolEdges
    .map((e) => nodes.find((n) => n.id === e.source))
    .filter((n): n is NonNullable<typeof n> =>
      Boolean(n && (n.data?.type?.toString().includes("tool") || n.data?.category === "Tools"))
    );

  const staticTools: string[] = Array.isArray(config.tools)
    ? config.tools
    : typeof config.tools === "string" && config.tools
    ? config.tools.split(",").map((s: string) => s.trim()).filter(Boolean)
    : [];

  const totalToolsCount = visualToolNodes.length + staticTools.length;

  return (
    <div
      className={`relative min-w-[280px] max-w-[320px] rounded-xl border bg-[#131b2e] p-3 shadow-md transition-all duration-200 ${
        nodeType === "agent" ? "pb-6" : ""
      } ${statusBorder} ${statusGlow} ${isSelected}`}
    >
      {/* 1. AGENT LEFT INPUT: Single Input Port (Flow In) */}
      {nodeType === "agent" && (
        <div className="absolute left-0 top-1/2 -translate-y-1/2 -translate-x-1.5 flex items-center z-10">
          <Handle
            type="target"
            position={Position.Left}
            id="input"
            style={{ position: "relative", transform: "none", top: "auto", left: "auto" }}
            className="!w-2.5 !h-6 !rounded-sm !bg-slate-400 !border-2 !border-[#0f172a] hover:!bg-sky-400 transition-all shadow-md cursor-pointer"
            title="Workflow Flow In: Connect from trigger or upstream node"
          />
        </div>
      )}

      {/* 2. AGENT RIGHT OUTPUT: Single Output Port with [+] (Flow Out) */}
      {nodeType === "agent" && (
        <div className="absolute right-0 top-1/2 -translate-y-1/2 translate-x-full flex items-center z-10 pl-1">
          <Handle
            type="source"
            position={Position.Right}
            id="output"
            style={{ position: "relative", transform: "none", top: "auto", right: "auto" }}
            className="!w-3.5 !h-3.5 !rounded-full !bg-slate-300 !border-2 !border-[#0f172a] hover:!bg-sky-400 transition-all shadow-md cursor-pointer"
            title="Workflow Flow Out: Connect downstream nodes"
          />
          <div className="w-2.5 h-0.5 bg-slate-600" />
          <button
            type="button"
            className="w-5 h-5 rounded border border-slate-700 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white flex items-center justify-center text-xs shadow transition active:scale-95"
            title="Connect Next Node"
          >
            <Plus className="w-3 h-3" />
          </button>
        </div>
      )}

      {/* 3. AGENT BOTTOM SOCKETS: Chat Model*, Memory, Tool (matching reference image) */}
      {nodeType === "agent" && (
        <div className="absolute -bottom-10 left-0 right-0 flex justify-around pointer-events-auto select-none z-20">
          {/* Chat Model socket */}
          <div className="flex flex-col items-center group relative">
            <Handle
              type="target"
              position={Position.Bottom}
              id="model"
              style={{
                position: "absolute",
                top: -8,
                left: "50%",
                transform: "translateX(-50%) rotate(45deg)",
              }}
              className="!w-3 !h-3 !bg-blue-400 !border-2 !border-[#0f172a] !rounded-none transition-transform hover:scale-125 cursor-pointer shadow-sm shadow-blue-500/50"
              title="Connect Chat Model"
            />
            <div className="w-px h-2.5 bg-slate-600 mb-0.5" />
            <span className="text-[10px] text-slate-400 font-medium group-hover:text-slate-200 transition">
              Chat Model<span className="text-rose-400">*</span>
            </span>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                if ((data as any).onAttachModel) (data as any).onAttachModel();
                window.dispatchEvent(new CustomEvent("select-agent-node", { detail: { agentNodeId: id } }));
              }}
              className="mt-1 w-5 h-5 rounded border border-slate-700 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white flex items-center justify-center text-xs shadow transition active:scale-95"
              title="Configure Chat Model in Inspector"
            >
              <Plus className="w-3 h-3" />
            </button>
          </div>

          {/* Memory socket */}
          <div className="flex flex-col items-center group relative">
            <Handle
              type="target"
              position={Position.Bottom}
              id="memory"
              style={{
                position: "absolute",
                top: -8,
                left: "50%",
                transform: "translateX(-50%) rotate(45deg)",
              }}
              className="!w-3 !h-3 !bg-indigo-400 !border-2 !border-[#0f172a] !rounded-none transition-transform hover:scale-125 cursor-pointer shadow-sm shadow-indigo-500/50"
              title="Connect Memory"
            />
            <div className="w-px h-2.5 bg-slate-600 mb-0.5" />
            <span className="text-[10px] text-slate-400 font-medium group-hover:text-slate-200 transition">
              Memory
            </span>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                if ((data as any).onAttachMemory) (data as any).onAttachMemory();
                window.dispatchEvent(new CustomEvent("select-agent-node", { detail: { agentNodeId: id } }));
              }}
              className="mt-1 w-5 h-5 rounded border border-slate-700 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white flex items-center justify-center text-xs shadow transition active:scale-95"
              title="Attach Memory"
            >
              <Plus className="w-3 h-3" />
            </button>
          </div>

          {/* Tool socket */}
          <div className="flex flex-col items-center group relative">
            <Handle
              type="target"
              position={Position.Bottom}
              id="tools"
              style={{
                position: "absolute",
                top: -8,
                left: "50%",
                transform: "translateX(-50%) rotate(45deg)",
              }}
              className="!w-3 !h-3 !bg-emerald-400 !border-2 !border-[#0f172a] !rounded-none shadow-md shadow-emerald-500/60 ring-2 ring-emerald-500/30 transition-transform hover:scale-125 cursor-pointer"
              title="Connect Tool nodes here"
            />
            <div className="w-px h-2.5 bg-emerald-600 mb-0.5" />
            <span className="text-[10px] text-emerald-300 font-semibold group-hover:text-emerald-200 transition">
              Tool
            </span>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setShowToolMenu((prev) => !prev);
              }}
              className="mt-1 w-5 h-5 rounded border border-emerald-700 bg-emerald-950 hover:bg-emerald-900 text-emerald-300 hover:text-white flex items-center justify-center text-xs shadow transition active:scale-95"
              title="Add a Tool to this Agent"
            >
              <Plus className="w-3 h-3" />
            </button>

            {/* Quick Tool Attachment Dropdown */}
            {showToolMenu && (
              <div
                className="absolute top-16 right-0 w-44 bg-[#0f172a] border border-emerald-700/60 rounded-xl shadow-2xl p-1.5 space-y-1 z-50 text-left font-sans"
                onClick={(e) => e.stopPropagation()}
              >
                <div className="text-[9px] font-bold uppercase tracking-wider text-emerald-400 px-2 py-1 border-b border-slate-800">
                  Attach Tool to Agent
                </div>
                <button
                  type="button"
                  onClick={() => {
                    if ((data as any).onAttachTool) (data as any).onAttachTool("web_search_tool");
                    window.dispatchEvent(new CustomEvent("attach-tool-to-agent", { detail: { toolType: "web_search_tool", agentNodeId: id } }));
                    setShowToolMenu(false);
                  }}
                  className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-slate-200 hover:bg-emerald-950/60 hover:text-emerald-300 text-xs transition text-left"
                >
                  <Globe className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                  <span>Web Search</span>
                </button>
                <button
                  type="button"
                  onClick={() => {
                    if ((data as any).onAttachTool) (data as any).onAttachTool("calculator_tool");
                    window.dispatchEvent(new CustomEvent("attach-tool-to-agent", { detail: { toolType: "calculator_tool", agentNodeId: id } }));
                    setShowToolMenu(false);
                  }}
                  className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-slate-200 hover:bg-emerald-950/60 hover:text-emerald-300 text-xs transition text-left"
                >
                  <Calculator className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                  <span>Calculator</span>
                </button>
                <button
                  type="button"
                  onClick={() => {
                    if ((data as any).onAttachTool) (data as any).onAttachTool("http_tool");
                    window.dispatchEvent(new CustomEvent("attach-tool-to-agent", { detail: { toolType: "http_tool", agentNodeId: id } }));
                    setShowToolMenu(false);
                  }}
                  className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-slate-200 hover:bg-emerald-950/60 hover:text-emerald-300 text-xs transition text-left"
                >
                  <ExternalLink className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                  <span>HTTP Request</span>
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 4. Missing required model/credentials warning badge (reference image) */}
      {nodeType === "agent" && (!config.api_key && config.use_workflow_credentials === false) && (
        <div className="absolute bottom-2 right-2 text-rose-500 animate-pulse z-10" title="Missing required Chat Model credentials">
          <AlertTriangle className="w-4 h-4 fill-rose-500/20 text-rose-500" />
        </div>
      )}

      {/* 5. TOOL TOP CONNECTOR: Connects UP to Agent's bottom Tool socket */}
      {nodeType.includes("tool") && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2 flex flex-col items-center z-10">
          <Handle
            type="source"
            position={Position.Top}
            id="tool"
            style={{ position: "relative", transform: "rotate(45deg)", top: "auto", left: "auto" }}
            className="!w-3 !h-3 !rounded-none !bg-emerald-400 !border-2 !border-[#0f172a] shadow-md shadow-emerald-500/60 ring-2 ring-emerald-500/30 transition-transform hover:scale-125 cursor-pointer"
            title="Wire UP to Agent's bottom [Tool] socket"
          />
          <span className="mt-1 text-[8px] font-mono font-bold text-emerald-400 bg-emerald-950/90 px-1 rounded border border-emerald-700/60 uppercase">
            Tool
          </span>
        </div>
      )}

      {/* 6. STANDARD INPUT HANDLES (for non-agent, non-tool nodes) */}
      {nodeType !== "agent" && !nodeType.includes("tool") && inputs.map((inputName, idx) => {
        const topPercent = inputs.length === 1 ? 50 : ((idx + 1) / (inputs.length + 1)) * 100;
        let labelText = inputName === "input" ? "Data In" : inputName;
        let labelIcon = "📥";
        let labelStyle = "text-sky-300 bg-slate-900/95 border-sky-500/40";

        return (
          <div key={`in-${inputName}-${idx}`}>
            <Handle
              type="target"
              position={Position.Left}
              id={inputName}
              style={{ top: `${topPercent}%` }}
              className="!w-3.5 !h-3.5 !border-2 !border-[#0f172a] !bg-sky-400 shadow-md shadow-sky-500/40 transition-transform hover:scale-125"
              title={`Connect upstream data here (${labelText})`}
            />
            <span
              style={{ top: `${topPercent}%` }}
              className={`absolute left-4 -translate-y-1/2 text-[9px] font-mono px-1.5 py-0.5 rounded border pointer-events-none flex items-center gap-1 shadow-sm whitespace-nowrap z-10 ${labelStyle}`}
            >
              <span>{labelIcon}</span>
              <span>{labelText}</span>
            </span>
          </div>
        );
      })}

      {/* Header */}
      <div className="flex items-center justify-between gap-2 border-b border-slate-800 pb-2 mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <div className={`p-1.5 rounded-lg shrink-0 ${style.bg} ${style.text}`}>
            <IconComponent className="w-4 h-4" />
          </div>
          <span className="font-semibold text-sm text-slate-100 truncate">{name}</span>
        </div>
        <span className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded shrink-0 ${style.badge}`}>
          {category}
        </span>
      </div>

      {/* Streamlined Agent Card Body */}
      {nodeType === "agent" && (
        <div className="space-y-2 mb-1 text-xs">
          {/* Model Badge */}
          <div className="flex items-center justify-between bg-slate-900/60 border border-slate-800 rounded-lg px-2 py-1">
            <span className="text-[10px] text-slate-400">Model:</span>
            <span
              className="font-mono text-[11px] text-sky-300 font-medium truncate max-w-[160px]"
              title={config.model || "Default Model"}
            >
              {config.model ? (config.model.split("/").pop() || config.model) : "ministral-3b-2512"}
            </span>
          </div>

          {/* Credentials Status */}
          <div className="flex items-center justify-between text-[10px] px-0.5">
            <span className="text-slate-400 flex items-center gap-1">
              <Key className="w-3 h-3 text-amber-400" />
              <span>Auth:</span>
            </span>
            {config.use_workflow_credentials !== false && !config.api_key ? (
              <span className="text-emerald-400 font-medium font-mono">Workflow Default</span>
            ) : config.api_key ? (
              <span className="text-emerald-400 font-medium font-mono">Custom Key</span>
            ) : (
              <span className="text-amber-400 font-semibold font-mono">Missing Key</span>
            )}
          </div>

          {/* Attached Tools Section */}
          <div className="pt-2 border-t border-slate-800 space-y-1.5">
            <div className="flex items-center justify-between text-[10px]">
              <span className="text-emerald-300 font-bold flex items-center gap-1">
                <Wrench className="w-3.5 h-3.5 text-emerald-400" />
                <span>Agent Tools Socket</span>
              </span>
              <span className="font-mono text-emerald-400 text-[9px] bg-emerald-950/90 px-1.5 py-0.5 rounded border border-emerald-700/60 font-semibold">
                {totalToolsCount} Connected
              </span>
            </div>

            {totalToolsCount === 0 ? (
              <div className="text-[10px] text-slate-300 p-2 rounded-lg bg-emerald-950/20 border border-dashed border-emerald-500/40 space-y-1">
                <div className="text-emerald-400 font-semibold flex items-center gap-1">
                  <span>💡 How to add tools:</span>
                </div>
                <p className="text-[9px] text-slate-400 leading-tight">
                  Click the <b>[+]</b> button under the <b>Tool</b> socket below, or attach via the Inspector.
                </p>
              </div>
            ) : (
              <div className="space-y-1 p-1.5 rounded-lg bg-slate-950/60 border border-slate-800">
                <div className="text-[9px] text-slate-400 font-mono flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  <span>Tools plugged into [Tool] socket:</span>
                </div>
                <div className="flex flex-wrap gap-1">
                  {visualToolNodes.map((toolNode) => (
                    <span
                      key={toolNode.id}
                      className="inline-flex items-center gap-1 text-[9px] px-1.5 py-0.5 rounded bg-emerald-950/90 text-emerald-300 border border-emerald-600/60 font-mono truncate max-w-[130px]"
                      title={`Plugged in from ${toolNode.data?.name || toolNode.id}`}
                    >
                      <span className="truncate">{(toolNode.data?.name as string) || toolNode.id}</span>
                    </span>
                  ))}
                  {staticTools.map((tName) => (
                    <span
                      key={tName}
                      className="text-[9px] px-1.5 py-0.5 rounded bg-slate-800/80 text-slate-300 border border-slate-700 font-mono truncate max-w-[110px]"
                    >
                      🔧 {tName}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Streamlined Tool Nodes */}
      {nodeType.includes("tool") && (
        <div className="space-y-2 mb-1 text-xs">
          {/* Tool Role & Agent-Driven Input Info */}
          <div className="p-2 rounded-lg bg-emerald-950/30 border border-emerald-500/40 text-[10px] space-y-1">
            <div className="flex items-center justify-between text-emerald-300 font-bold">
              <span className="flex items-center gap-1">
                <Wrench className="w-3.5 h-3.5 text-emerald-400" />
                <span>Agent Tool Provider</span>
              </span>
              <span className="text-[9px] font-mono bg-emerald-500/20 text-emerald-300 px-1.5 py-0.2 rounded border border-emerald-500/30">
                Sub-node
              </span>
            </div>
            <p className="text-[9px] text-slate-300 leading-tight">
              Input parameters are provided <b>dynamically by the Agent</b> during LLM execution.
            </p>
          </div>

          {nodeType === "web_search_tool" && (
            <div className="text-[10px] text-slate-300 bg-slate-900/60 border border-slate-800 p-1.5 rounded space-y-0.5">
              <div className="flex justify-between text-slate-300 font-medium">
                <span>Web Search Engine</span>
                <span className="font-mono text-[9px] text-slate-400">Max: {config.max_results || 5}</span>
              </div>
              <p className="text-[9px] text-slate-400 italic truncate">
                {config.default_query ? `Query: "${config.default_query}"` : "Accepts upstream or agent queries"}
              </p>
            </div>
          )}

          {nodeType === "calculator_tool" && (
            <div className="text-[10px] text-slate-300 bg-slate-900/60 border border-slate-800 p-1.5 rounded space-y-0.5">
              <div className="flex justify-between text-slate-300 font-medium">
                <span>Math Evaluator</span>
                <span className="font-mono text-[9px] text-slate-400">Safe AST</span>
              </div>
              <p className="text-[9px] text-slate-400 italic truncate">
                {config.default_expression ? `Expr: ${config.default_expression}` : "Accepts math expressions"}
              </p>
            </div>
          )}

          {nodeType === "http_tool" && (
            <div className="text-[10px] text-slate-300 bg-slate-900/60 border border-slate-800 p-1.5 rounded space-y-0.5">
              <div className="flex justify-between text-slate-300 font-medium">
                <span>HTTP Request</span>
                <span className="font-mono text-[9px] uppercase text-slate-400">{config.method || "GET"}</span>
              </div>
              <p className="text-[9px] text-slate-400 italic truncate font-mono">
                {config.url || "https://api..."}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Trigger Node Wiring Instructions */}
      {nodeType.includes("trigger") && (
        <div className="p-2 rounded-lg bg-amber-950/20 border border-amber-500/30 text-[10px] space-y-1 mb-1">
          <div className="flex items-center justify-between text-amber-400 font-bold">
            <span className="flex items-center gap-1">
              <PlayCircle className="w-3.5 h-3.5" />
              <span>Workflow Trigger</span>
            </span>
            <span className="text-[9px] font-mono bg-amber-500/20 text-amber-300 px-1 rounded">Start</span>
          </div>
          <p className="text-[9px] text-slate-400 font-mono">
            Wire <span className="text-sky-300 font-semibold">[📤 Data Out]</span> ──► Agent <span className="text-sky-300 font-semibold">[📥 Data In]</span>
          </p>
        </div>
      )}

      {/* Output Node Wiring Instructions */}
      {nodeType === "output" && (
        <div className="p-2 rounded-lg bg-slate-900/60 border border-slate-700/50 text-[10px] space-y-1 mb-1">
          <div className="flex items-center justify-between text-slate-200 font-bold">
            <span className="flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              <span>Final Output</span>
            </span>
            <span className="text-[9px] font-mono bg-slate-800 text-slate-300 px-1 rounded">End</span>
          </div>
          <p className="text-[9px] text-slate-400 font-mono">
            Receives response from Agent <span className="text-sky-300 font-semibold">[📤 Data Out]</span>
          </p>
        </div>
      )}

      {/* Streamlined LLM Node */}
      {nodeType === "llm" && (
        <div className="space-y-1.5 mb-1 text-xs">
          <div className="flex items-center justify-between bg-slate-900/60 border border-slate-800 rounded px-2 py-1">
            <span className="text-[10px] text-slate-400">Model:</span>
            <span className="font-mono text-[11px] text-sky-300 font-medium truncate max-w-[160px]">
              {config.model ? (config.model.split("/").pop() || config.model) : "gpt-4o-mini"}
            </span>
          </div>
        </div>
      )}

      {/* Default Description for other nodes */}
      {nodeType !== "agent" && !nodeType.includes("tool") && !nodeType.includes("trigger") && nodeType !== "output" && nodeType !== "llm" && (
        <div className="text-xs text-slate-400 line-clamp-2">
          {(data.description as string) || "Configure parameters in inspector."}
        </div>
      )}

      {/* Status Bar */}
      {status !== "idle" && (
        <div className="mt-2 pt-1.5 border-t border-slate-800/60 flex items-center justify-between text-[11px]">
          <div className="flex items-center gap-1.5">
            {status === "running" && (
              <>
                <Loader2 className="w-3 h-3 text-blue-400 animate-spin" />
                <span className="text-blue-400 font-medium">Running...</span>
              </>
            )}
            {status === "completed" && (
              <>
                <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                <span className="text-emerald-400 font-medium">Completed</span>
              </>
            )}
            {status === "waiting_for_human" && (
              <>
                <UserCheck className="w-3 h-3 text-amber-400" />
                <span className="text-amber-400 font-medium">Approval Required</span>
              </>
            )}
            {status === "failed" && (
              <>
                <AlertCircle className="w-3 h-3 text-rose-400" />
                <span className="text-rose-400 font-medium">Failed</span>
              </>
            )}
          </div>

          {duration !== undefined && (
            <div className="flex items-center gap-1 text-slate-500 font-mono text-[10px]">
              <Clock className="w-2.5 h-2.5" />
              <span>{duration.toFixed(2)}s</span>
            </div>
          )}
        </div>
      )}

      {/* Standard Output Handles (for non-agent, non-tool nodes) */}
      {nodeType !== "agent" && !nodeType.includes("tool") && outputs.map((outputName, idx) => {
        const topPercent = outputs.length === 1 ? 50 : ((idx + 1) / (outputs.length + 1)) * 100;
        const isToolHandle = outputName === "tool";

        let labelText = "Data Out";
        let labelIcon = "📤";
        let labelStyle = "text-sky-300 bg-slate-900/95 border-sky-500/40";

        if (isToolHandle) {
          labelText = "Tool Out";
          labelIcon = "🧩";
          labelStyle = "text-emerald-300 bg-emerald-950/95 border-emerald-500/60 font-bold shadow-sm shadow-emerald-500/30";
        } else if (outputName !== "output") {
          labelText = outputName;
          labelIcon = "🔀";
        }

        return (
          <div key={`out-${outputName}-${idx}`}>
            <Handle
              type="source"
              position={Position.Right}
              id={outputName}
              style={{ top: `${topPercent}%` }}
              className={`!w-3.5 !h-3.5 !border-2 !border-[#0f172a] transition-transform hover:scale-125 ${
                isToolHandle
                  ? "!bg-emerald-400 shadow-md shadow-emerald-500/60 ring-2 ring-emerald-500/30"
                  : "!bg-sky-400 shadow-md shadow-sky-500/40"
              }`}
              title={isToolHandle ? "Wire to Agent's [🧩 Tools In] port" : `Output to next node (${labelText})`}
            />
            <span
              style={{ top: `${topPercent}%` }}
              className={`absolute right-4 -translate-y-1/2 text-[9px] font-mono px-1.5 py-0.5 rounded border pointer-events-none flex items-center gap-1 shadow-sm whitespace-nowrap z-10 ${labelStyle}`}
            >
              <span>{labelText}</span>
              <span>{labelIcon}</span>
            </span>
          </div>
        );
      })}
    </div>
  );
});
