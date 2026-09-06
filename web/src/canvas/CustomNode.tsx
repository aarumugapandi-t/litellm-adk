import React, { memo, useState } from "react";
import { Handle, Position, NodeProps, useReactFlow } from "@xyflow/react";
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
  Loader2,
  Clock,
  Eye,
  EyeOff,
} from "lucide-react";
import { ExecutionStatus } from "../types/workflow";

// Icon mapping based on node type
const ICON_MAP: Record<string, React.ElementType> = {
  manual_trigger: PlayCircle,
  webhook_trigger: PlayCircle,
  llm: Sparkles,
  agent: Bot,
  tool: Wrench,
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
  const { updateNodeData } = useReactFlow();
  const nodeType = (data.type as string) || "agent";
  const category = (data.category as string) || "AI & Agents";
  const name = (data.name as string) || "Node";
  const status = (data.status as ExecutionStatus) || "idle";
  const duration = data.duration as number | undefined;
  const config = (data.config as Record<string, any>) || {};
  const [showApiKey, setShowApiKey] = useState(false);

  const handleConfigChange = (key: string, value: any) => {
    updateNodeData(id, {
      ...data,
      config: {
        ...config,
        [key]: value,
      },
    });
  };

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
  const toolsList: string[] = Array.isArray(config.tools)
    ? config.tools
    : typeof config.tools === "string" && config.tools
    ? config.tools.split(",").map((s: string) => s.trim()).filter(Boolean)
    : [];

  return (
    <div
      className={`relative min-w-[260px] max-w-[300px] rounded-xl border bg-[#131b2e] p-3 shadow-md transition-all duration-200 ${statusBorder} ${statusGlow} ${isSelected}`}
    >
      {/* Input Handles */}
      {inputs.map((inputName, idx) => (
        <Handle
          key={`in-${inputName}-${idx}`}
          type="target"
          position={Position.Left}
          id={inputName}
          style={{ top: `${((idx + 1) / (inputs.length + 1)) * 100}%` }}
          className="!bg-sky-400 !w-3 !h-3 !border-2 !border-[#0f172a]"
        />
      ))}

      {/* Header */}
      <div className="flex items-center justify-between gap-2 border-b border-slate-800 pb-2 mb-2">
        <div className="flex items-center gap-2">
          <div className={`p-1.5 rounded-lg ${style.bg} ${style.text}`}>
            <IconComponent className="w-4 h-4" />
          </div>
          <span className="font-semibold text-sm text-slate-100 truncate">{name}</span>
        </div>
        <span className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded ${style.badge}`}>
          {category}
        </span>
      </div>

      {/* Agent Specific Node Inputs */}
      {nodeType === "agent" && (
        <div className="space-y-2 mb-2 text-xs">
          {/* Model Input Box */}
          <div className="space-y-0.5">
            <div className="flex items-center justify-between text-[10px] text-slate-400">
              <span className="font-semibold text-slate-300">Model (required):</span>
            </div>
            <input
              type="text"
              value={config.model !== undefined ? config.model : "openrouter/mistralai/ministral-3b-2512"}
              onChange={(e) => handleConfigChange("model", e.target.value)}
              placeholder="openrouter/mistralai/ministral-3b-2512"
              className="nodrag nopan w-full bg-[#1e293b] border border-slate-700/80 rounded px-2 py-1 text-[11px] font-mono text-sky-300 focus:outline-none focus:border-sky-500"
            />
          </div>

          {/* Base URL Input Box */}
          <div className="space-y-0.5">
            <div className="flex items-center justify-between text-[10px] text-slate-400">
              <span className="font-semibold text-slate-300">Base URL (endpoint):</span>
            </div>
            <input
              type="text"
              value={config.base_url !== undefined ? config.base_url : ""}
              onChange={(e) => handleConfigChange("base_url", e.target.value)}
              placeholder="http://localhost:9000/v1"
              className="nodrag nopan w-full bg-[#1e293b] border border-slate-700/80 rounded px-2 py-1 text-[11px] font-mono text-slate-200 focus:outline-none focus:border-sky-500"
            />
          </div>

          {/* API Key Input Box */}
          <div className="space-y-0.5">
            <div className="flex items-center justify-between text-[10px] text-slate-400">
              <span className="font-semibold text-slate-300">API Key (required):</span>
              <span className={`font-mono text-[9px] ${config.api_key ? "text-emerald-400 font-medium" : "text-amber-400 font-semibold"}`}>
                {config.api_key ? "✓ Configured" : "⚠️ Required"}
              </span>
            </div>
            <div className="relative">
              <input
                type={showApiKey ? "text" : "password"}
                value={config.api_key !== undefined ? config.api_key : ""}
                onChange={(e) => handleConfigChange("api_key", e.target.value)}
                placeholder="sk-1234 or {{ variables.api_key }}"
                className="nodrag nopan w-full bg-[#1e293b] border border-slate-700/80 rounded pl-2 pr-7 py-1 text-[11px] font-mono text-slate-100 focus:outline-none focus:border-sky-500"
              />
              <button
                type="button"
                onClick={() => setShowApiKey(!showApiKey)}
                className="nodrag nopan absolute right-1.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 focus:outline-none p-0.5"
                title={showApiKey ? "Hide API key" : "Show API key"}
              >
                {showApiKey ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
              </button>
            </div>
          </div>

          {/* Tools Badges */}
          {toolsList.length > 0 && (
            <div className="flex flex-wrap gap-1 pt-1 border-t border-slate-800/60">
              {toolsList.slice(0, 3).map((t: string) => (
                <span
                  key={t}
                  className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-950/80 text-emerald-300 border border-emerald-800/60 font-mono truncate max-w-[120px]"
                >
                  🔧 {t}
                </span>
              ))}
              {toolsList.length > 3 && (
                <span className="text-[9px] text-slate-400 font-mono">+{toolsList.length - 3}</span>
              )}
            </div>
          )}
        </div>
      )}

      {/* LLM Specific Node Inputs */}
      {nodeType === "llm" && (
        <div className="space-y-2 mb-2 text-xs">
          <div className="space-y-0.5">
            <div className="flex items-center justify-between text-[10px] text-slate-400">
              <span className="font-semibold text-slate-300">Model:</span>
            </div>
            <input
              type="text"
              value={config.model !== undefined ? config.model : "openai/gpt-4o-mini"}
              onChange={(e) => handleConfigChange("model", e.target.value)}
              placeholder="openai/gpt-4o-mini"
              className="nodrag nopan w-full bg-[#1e293b] border border-slate-700/80 rounded px-2 py-1 text-[11px] font-mono text-sky-300 focus:outline-none focus:border-sky-500"
            />
          </div>

          <div className="space-y-0.5">
            <div className="flex items-center justify-between text-[10px] text-slate-400">
              <span className="font-semibold text-slate-300">Base URL (endpoint):</span>
            </div>
            <input
              type="text"
              value={config.base_url !== undefined ? config.base_url : ""}
              onChange={(e) => handleConfigChange("base_url", e.target.value)}
              placeholder="http://localhost:9000/v1"
              className="nodrag nopan w-full bg-[#1e293b] border border-slate-700/80 rounded px-2 py-1 text-[11px] font-mono text-slate-200 focus:outline-none focus:border-sky-500"
            />
          </div>

          <div className="space-y-0.5">
            <div className="flex items-center justify-between text-[10px] text-slate-400">
              <span className="font-semibold text-slate-300">API Key:</span>
              <span className={`font-mono text-[9px] ${config.api_key ? "text-emerald-400" : "text-slate-500"}`}>
                {config.api_key ? "✓ Set" : "Optional"}
              </span>
            </div>
            <div className="relative">
              <input
                type={showApiKey ? "text" : "password"}
                value={config.api_key !== undefined ? config.api_key : ""}
                onChange={(e) => handleConfigChange("api_key", e.target.value)}
                placeholder="sk-..."
                className="nodrag nopan w-full bg-[#1e293b] border border-slate-700/80 rounded pl-2 pr-7 py-1 text-[11px] font-mono text-slate-100 focus:outline-none focus:border-sky-500"
              />
              <button
                type="button"
                onClick={() => setShowApiKey(!showApiKey)}
                className="nodrag nopan absolute right-1.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 focus:outline-none p-0.5"
                title={showApiKey ? "Hide API key" : "Show API key"}
              >
                {showApiKey ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Default Description for other nodes */}
      {nodeType !== "agent" && nodeType !== "llm" && (
        <div className="text-xs text-slate-400 line-clamp-2">
          {(data.description as string) || "Configure parameters in inspector."}
        </div>
      )}

      {/* Status Bar */}
      {status !== "idle" && (
        <div className="mt-2.5 pt-1.5 border-t border-slate-800/60 flex items-center justify-between text-[11px]">
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

      {/* Output Handles */}
      {outputs.map((outputName, idx) => {
        const topPercent = outputs.length === 1 ? 50 : ((idx + 1) / (outputs.length + 1)) * 100;
        return (
          <div key={`out-${outputName}-${idx}`}>
            <Handle
              type="source"
              position={Position.Right}
              id={outputName}
              style={{ top: `${topPercent}%` }}
              className="!bg-emerald-400 !w-3 !h-3 !border-2 !border-[#0f172a]"
            />
            {outputs.length > 1 && (
              <span
                style={{ top: `${topPercent}%` }}
                className="absolute right-3 -translate-y-1/2 text-[9px] font-mono uppercase text-slate-400 bg-slate-900/80 px-1 rounded border border-slate-700 pointer-events-none"
              >
                {outputName}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
});
