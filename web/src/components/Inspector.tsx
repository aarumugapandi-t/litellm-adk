import React, { useState, useEffect } from "react";
import { Node, Edge } from "@xyflow/react";
import {
  Trash2,
  HelpCircle,
  Code,
  CheckCircle,
  AlertCircle,
  Eye,
  EyeOff,
  Wrench,
  Plus,
  X,
  Bot,
  Key,
  Globe,
  Sparkles,
  ChevronDown,
  ChevronRight,
  ShieldCheck,
  Zap,
} from "lucide-react";
import { NodeDefinition, NodeExecutionRecord } from "../types/workflow";
import { api } from "../api/client";
import { getAvailableVariables } from "../utils/variables";
import { VariablePicker } from "./VariablePicker";

interface InspectorProps {
  selectedNode: Node | null;
  availableNodes: NodeDefinition[];
  onUpdateNodeData: (nodeId: string, updatedData: any) => void;
  onDeleteNode: (nodeId: string) => void;
  executionRecord?: NodeExecutionRecord | null;
  allNodes?: Node[];
  allEdges?: Edge[];
  workflowVariables?: Record<string, any>;
  onAttachToolToAgent?: (toolType: string, agentNodeId: string) => void;
  onDetachToolFromAgent?: (toolNodeId: string, agentNodeId: string) => void;
}

const MODEL_PRESETS = [
  { label: "Ministral 3B", value: "openrouter/mistralai/ministral-3b-2512" },
  { label: "GPT-4o Mini", value: "openai/gpt-4o-mini" },
  { label: "GPT-4o", value: "openai/gpt-4o" },
  { label: "Claude 3.5 Sonnet", value: "anthropic/claude-3-5-sonnet" },
  { label: "Llama 3.2 (Ollama)", value: "ollama/llama3.2" },
];

const BASE_URL_PRESETS = [
  { label: "Local (9000)", value: "http://localhost:9000/v1" },
  { label: "OpenRouter", value: "https://openrouter.ai/api/v1" },
  { label: "Ollama (11434)", value: "http://localhost:11434/v1" },
];

export const Inspector: React.FC<InspectorProps> = ({
  selectedNode,
  availableNodes,
  onUpdateNodeData,
  onDeleteNode,
  executionRecord,
  allNodes = [],
  allEdges = [],
  workflowVariables = {},
  onAttachToolToAgent,
  onDetachToolFromAgent,
}) => {
  const [activeTab, setActiveTab] = useState<"config" | "execution">("config");
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({});
  const [availableTools, setAvailableTools] = useState<any[]>([]);
  const [customToolInput, setCustomToolInput] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);

  useEffect(() => {
    api.getTools().then(setAvailableTools).catch(() => {});
  }, []);

  if (!selectedNode) {
    return (
      <aside className="w-80 border-l border-slate-800 bg-[#0f172a] flex flex-col items-center justify-center p-6 text-center text-slate-500 select-none">
        <HelpCircle className="w-8 h-8 mb-2 opacity-40" />
        <p className="text-xs">Select any node on the canvas to inspect its configuration and execution state.</p>
      </aside>
    );
  }

  const def = availableNodes.find((n) => n.type === selectedNode.data?.type);
  const config = (selectedNode.data?.config as Record<string, any>) || {};
  const schema = def?.config_schema?.properties || {};
  const requiredFields: string[] = def?.config_schema?.required || [];
  const nodeType = (selectedNode.data?.type as string) || "agent";

  const handleConfigChange = (key: string, value: any) => {
    onUpdateNodeData(selectedNode.id, {
      ...selectedNode.data,
      config: {
        ...config,
        [key]: value,
      },
    });
  };

  const handleNameChange = (newName: string) => {
    onUpdateNodeData(selectedNode.id, {
      ...selectedNode.data,
      name: newName,
    });
  };

  const toggleShowSecret = (key: string) => {
    setShowSecrets((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  // Compile available variables from upstream DAG and workflow settings
  const availableVariables = getAvailableVariables(
    selectedNode.id,
    allNodes,
    allEdges,
    workflowVariables
  );

  // Discover connected tools from canvas
  const connectedToolNodes = allEdges
    .filter((e) => e.target === selectedNode.id && (e.targetHandle === "tools" || !e.targetHandle))
    .map((e) => allNodes.find((n) => n.id === e.source))
    .filter((n): n is NonNullable<typeof n> =>
      Boolean(n && (n.data?.type?.toString().includes("tool") || n.data?.category === "Tools"))
    );

  // Statically configured tools
  const staticTools: string[] = Array.isArray(config.tools)
    ? config.tools
    : typeof config.tools === "string" && config.tools
    ? config.tools.split(",").map((s: string) => s.trim()).filter(Boolean)
    : [];

  const handleToggleTool = (toolName: string) => {
    if (staticTools.includes(toolName)) {
      handleConfigChange("tools", staticTools.filter((t: string) => t !== toolName));
    } else {
      handleConfigChange("tools", [...staticTools, toolName]);
    }
  };

  const handleAddCustomTool = () => {
    const trimmed = customToolInput.trim();
    if (!trimmed) return;
    if (!staticTools.includes(trimmed)) {
      handleConfigChange("tools", [...staticTools, trimmed]);
    }
    setCustomToolInput("");
  };

  const handleRemoveTool = (toolName: string) => {
    handleConfigChange("tools", staticTools.filter((t: string) => t !== toolName));
  };

  const useWorkflowCredentials =
    config.use_workflow_credentials !== undefined ? config.use_workflow_credentials : !config.api_key;

  return (
    <aside className="w-84 border-l border-slate-800 bg-[#0f172a] flex flex-col h-full z-10 select-none">
      {/* Inspector Header */}
      <div className="p-3 border-b border-slate-800 flex items-center justify-between">
        <div className="min-w-0 flex-1 mr-2">
          <input
            type="text"
            value={(selectedNode.data?.name as string) || ""}
            onChange={(e) => handleNameChange(e.target.value)}
            className="bg-transparent border-b border-transparent hover:border-slate-700 focus:border-sky-500 focus:outline-none text-sm font-semibold text-slate-100 w-full truncate"
          />
          <span className="text-[10px] font-mono text-slate-500 block truncate">
            ID: {selectedNode.id} • {selectedNode.data?.type as string}
          </span>
        </div>

        <button
          onClick={() => onDeleteNode(selectedNode.id)}
          className="p-1.5 rounded-lg border border-rose-900/40 bg-rose-950/20 hover:bg-rose-900/40 text-rose-400 transition shrink-0"
          title="Delete node"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-800 text-xs">
        <button
          onClick={() => setActiveTab("config")}
          className={`flex-1 py-2 font-medium transition ${
            activeTab === "config"
              ? "text-sky-400 border-b-2 border-sky-400 bg-slate-800/30"
              : "text-slate-400 hover:text-slate-200"
          }`}
        >
          Configuration
        </button>
        <button
          onClick={() => setActiveTab("execution")}
          className={`flex-1 py-2 font-medium transition ${
            activeTab === "execution"
              ? "text-sky-400 border-b-2 border-sky-400 bg-slate-800/30"
              : "text-slate-400 hover:text-slate-200"
          }`}
        >
          Execution Data
        </button>
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {activeTab === "config" ? (
          <div className="space-y-4">
            {/* AGENT SPECIALIZED STREAMLINED CONFIGURATION */}
            {nodeType === "agent" ? (
              <div className="space-y-4">
                {/* 1. Model Selector */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
                      <Bot className="w-3.5 h-3.5 text-sky-400" />
                      <span>Model Identifier</span>
                      <span className="text-rose-400 text-xs">*</span>
                    </label>
                    <VariablePicker
                      variables={availableVariables}
                      currentValue={config.model}
                      onInsertVariable={(varExpr) => handleConfigChange("model", varExpr)}
                    />
                  </div>

                  <input
                    type="text"
                    value={config.model !== undefined ? config.model : "openrouter/mistralai/ministral-3b-2512"}
                    onChange={(e) => handleConfigChange("model", e.target.value)}
                    placeholder="e.g. openrouter/mistralai/ministral-3b-2512"
                    className="w-full bg-[#1e293b] border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs font-mono text-slate-100 focus:outline-none focus:border-sky-500"
                  />

                  {/* Model Presets */}
                  <div className="flex flex-wrap gap-1 pt-0.5">
                    {MODEL_PRESETS.map((p) => (
                      <button
                        key={p.value}
                        type="button"
                        onClick={() => handleConfigChange("model", p.value)}
                        className={`text-[9px] px-1.5 py-0.5 rounded border transition font-mono ${
                          config.model === p.value
                            ? "bg-sky-950 border-sky-500 text-sky-300 font-semibold"
                            : "bg-slate-800/60 border-slate-700/60 text-slate-400 hover:text-slate-200"
                        }`}
                      >
                        {p.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* 2. Credentials Inheritance Toggle */}
                <div className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800 space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-slate-200 flex items-center gap-1.5 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={useWorkflowCredentials}
                        onChange={(e) => {
                          handleConfigChange("use_workflow_credentials", e.target.checked);
                          if (e.target.checked) {
                            handleConfigChange("api_key", "");
                            handleConfigChange("base_url", "");
                          }
                        }}
                        className="rounded border-slate-700 bg-[#1e293b] text-sky-500 focus:ring-0 focus:ring-offset-0"
                      />
                      <span className="flex items-center gap-1 text-slate-300">
                        <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                        <span>Use Workflow Default Credentials</span>
                      </span>
                    </label>
                  </div>

                  {useWorkflowCredentials ? (
                    <div className="text-[11px] text-slate-400 bg-slate-950/60 p-2 rounded border border-slate-800/80 font-mono">
                      <div className="flex items-center gap-1 text-emerald-400 font-sans mb-1">
                        <Key className="w-3 h-3" />
                        <span className="font-semibold">Workflow Defaults Active</span>
                      </div>
                      <div className="text-[10px] text-slate-500">
                        API Key: <span className="text-slate-300">{workflowVariables.api_key ? "••••••••" : "env(API_KEY)"}</span>
                      </div>
                      <div className="text-[10px] text-slate-500">
                        Base URL: <span className="text-slate-300">{workflowVariables.base_url || "http://localhost:9000/v1"}</span>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-2 pt-1 border-t border-slate-800">
                      {/* API Key */}
                      <div className="space-y-1">
                        <div className="flex items-center justify-between text-[11px]">
                          <span className="text-slate-300 font-medium">Custom API Key:</span>
                          <VariablePicker
                            variables={availableVariables}
                            currentValue={config.api_key}
                            onInsertVariable={(varExpr) => handleConfigChange("api_key", varExpr)}
                          />
                        </div>
                        <div className="relative">
                          <input
                            type={showSecrets["api_key"] ? "text" : "password"}
                            value={config.api_key !== undefined ? config.api_key : ""}
                            onChange={(e) => handleConfigChange("api_key", e.target.value)}
                            placeholder="sk-1234 or {{ variables.api_key }}"
                            className="w-full bg-[#1e293b] border border-slate-700 rounded-lg pl-2.5 pr-8 py-1 text-xs font-mono text-slate-100 focus:outline-none focus:border-sky-500"
                          />
                          <button
                            type="button"
                            onClick={() => toggleShowSecret("api_key")}
                            className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 focus:outline-none"
                          >
                            {showSecrets["api_key"] ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                          </button>
                        </div>
                      </div>

                      {/* Base URL */}
                      <div className="space-y-1">
                        <div className="flex items-center justify-between text-[11px]">
                          <span className="text-slate-300 font-medium">Custom Base URL:</span>
                          <VariablePicker
                            variables={availableVariables}
                            currentValue={config.base_url}
                            onInsertVariable={(varExpr) => handleConfigChange("base_url", varExpr)}
                          />
                        </div>
                        <input
                          type="text"
                          value={config.base_url !== undefined ? config.base_url : ""}
                          onChange={(e) => handleConfigChange("base_url", e.target.value)}
                          placeholder="http://localhost:9000/v1"
                          className="w-full bg-[#1e293b] border border-slate-700 rounded-lg px-2.5 py-1 text-xs font-mono text-slate-100 focus:outline-none focus:border-sky-500"
                        />
                        <div className="flex flex-wrap gap-1">
                          {BASE_URL_PRESETS.map((p) => (
                            <button
                              key={p.value}
                              type="button"
                              onClick={() => handleConfigChange("base_url", p.value)}
                              className="text-[9px] px-1.5 py-0.5 rounded border border-slate-700 bg-slate-800/60 text-slate-400 hover:text-slate-200 font-mono"
                            >
                              {p.label}
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* 3. Task Prompt with Variable Autocompletion */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-slate-200">
                      Task Prompt
                    </label>
                    <VariablePicker
                      variables={availableVariables}
                      currentValue={config.prompt}
                      onInsertVariable={(varExpr) => {
                        const cur = config.prompt || "";
                        handleConfigChange("prompt", `${cur ? cur + " " : ""}${varExpr}`);
                      }}
                    />
                  </div>

                  <textarea
                    rows={4}
                    value={config.prompt !== undefined ? config.prompt : ""}
                    onChange={(e) => handleConfigChange("prompt", e.target.value)}
                    placeholder="Describe what the agent should do. Type {{ or use +Variable to inject context."
                    className="w-full bg-[#1e293b] border border-slate-700 rounded-lg p-2 text-xs font-mono text-slate-100 focus:outline-none focus:border-sky-500 placeholder-slate-500"
                  />

                  {/* Abstracted variable chips in current prompt */}
                  {config.prompt && /\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}/.test(config.prompt) && (
                    <div className="flex flex-wrap items-center gap-1 pt-1">
                      <span className="text-[10px] text-slate-500 font-medium">Injected variables:</span>
                      {Array.from(new Set(Array.from(config.prompt.matchAll(/\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}/g)).map((m: any) => m[1]))).map((vKey: any) => (
                        <span
                          key={vKey}
                          className="text-[9px] px-1.5 py-0.2 rounded bg-sky-950/80 text-sky-300 border border-sky-700/50 font-mono"
                        >
                          {`{{ ${vKey} }}`}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* 4. Visual Tool Attachment on Canvas Panel */}
                <div className="space-y-2.5 p-3 rounded-xl bg-slate-900/60 border border-slate-800">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
                      <Wrench className="w-3.5 h-3.5 text-emerald-400" />
                      <span>Agent Tools Socket</span>
                    </span>
                    <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/80 px-1.5 py-0.5 rounded border border-emerald-800/40">
                      {connectedToolNodes.length} connected
                    </span>
                  </div>

                  {/* Visual Connection Diagram */}
                  <div className="p-2 rounded-lg bg-emerald-950/20 border border-emerald-800/40 text-[10px] space-y-1">
                    <div className="text-emerald-300 font-semibold flex items-center justify-between">
                      <span>How Tools Connect:</span>
                      <span className="text-[9px] font-mono text-emerald-400 bg-emerald-950 px-1 rounded">Auto or Drag</span>
                    </div>
                    <div className="flex items-center justify-between text-[9px] text-slate-300 bg-slate-950/70 p-1.5 rounded border border-slate-800 font-mono">
                      <span className="text-emerald-300 font-semibold">[🧩 Tool Out]</span>
                      <span className="text-emerald-400 font-bold">──(Green Wire)──►</span>
                      <span className="text-sky-300 font-semibold">[🧩 Tools In]</span>
                    </div>
                  </div>

                  {/* 1-Click Quick Attach Prebuilt Tools */}
                  <div className="space-y-1.5">
                    <div className="text-[11px] font-semibold text-slate-300">Quick Attach Prebuilt Tools:</div>
                    {[
                      { type: "web_search_tool", name: "Web Search", desc: "Live web search engine" },
                      { type: "calculator_tool", name: "Calculator", desc: "Safe mathematical evaluator" },
                      { type: "http_tool", name: "HTTP Request", desc: "Query custom REST APIs" },
                    ].map((tool) => {
                      const attached = connectedToolNodes.find((n) => n.data?.type === tool.type);

                      return (
                        <div
                          key={tool.type}
                          className={`flex items-center justify-between p-2 rounded-lg border text-xs transition ${
                            attached
                              ? "bg-emerald-950/30 border-emerald-700/50 text-emerald-300"
                              : "bg-slate-950/40 border-slate-800 text-slate-300"
                          }`}
                        >
                          <div>
                            <div className="font-medium text-[11px] flex items-center gap-1.5">
                              {attached && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />}
                              <span>{tool.name}</span>
                            </div>
                            <div className="text-[9px] text-slate-400">{tool.desc}</div>
                          </div>

                          {attached ? (
                            <div className="flex items-center gap-1.5">
                              <span className="text-[9px] font-mono text-emerald-400 bg-emerald-950 px-1.5 py-0.5 rounded border border-emerald-800/40">
                                ✓ Wired
                              </span>
                              {onDetachToolFromAgent && (
                                <button
                                  type="button"
                                  onClick={() => onDetachToolFromAgent(attached.id, selectedNode.id)}
                                  className="text-[9px] px-1.5 py-0.5 rounded bg-rose-950/60 hover:bg-rose-900 text-rose-300 border border-rose-800/50 transition"
                                  title="Unlink tool from this agent"
                                >
                                  Unlink
                                </button>
                              )}
                            </div>
                          ) : (
                            onAttachToolToAgent && (
                              <button
                                type="button"
                                onClick={() => onAttachToolToAgent(tool.type, selectedNode.id)}
                                className="flex items-center gap-1 px-2 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-white text-[10px] font-semibold transition shadow-sm shadow-emerald-600/30"
                              >
                                <Plus className="w-3 h-3" />
                                <span>Attach</span>
                              </button>
                            )
                          )}
                        </div>
                      );
                    })}
                  </div>

                  {connectedToolNodes.length === 0 && (
                    <p className="text-[10px] text-slate-500 italic leading-relaxed pt-1">
                      You can also drag any tool from the left palette and wire its <b>[Tool Out]</b> handle to this Agent's <b>[Tools In]</b> handle.
                    </p>
                  )}
                </div>

                {/* 5. Advanced Settings Accordion */}
                <div className="border border-slate-800 rounded-lg overflow-hidden">
                  <button
                    type="button"
                    onClick={() => setShowAdvanced(!showAdvanced)}
                    className="w-full p-2.5 bg-slate-900/40 hover:bg-slate-900/80 flex items-center justify-between text-xs font-semibold text-slate-300 transition"
                  >
                    <span>Advanced Agent Settings</span>
                    {showAdvanced ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                  </button>

                  {showAdvanced && (
                    <div className="p-3 space-y-3 bg-[#0d1424] border-t border-slate-800">
                      {/* System Prompt */}
                      <div className="space-y-1">
                        <div className="flex items-center justify-between">
                          <label className="text-[11px] font-medium text-slate-300">System Prompt</label>
                          <VariablePicker
                            variables={availableVariables}
                            currentValue={config.system_prompt}
                            onInsertVariable={(varExpr) => {
                              const cur = config.system_prompt || "";
                              handleConfigChange("system_prompt", `${cur ? cur + " " : ""}${varExpr}`);
                            }}
                          />
                        </div>
                        <textarea
                          rows={3}
                          value={config.system_prompt !== undefined ? config.system_prompt : ""}
                          onChange={(e) => handleConfigChange("system_prompt", e.target.value)}
                          placeholder="You are an autonomous AI research agent..."
                          className="w-full bg-[#1e293b] border border-slate-700 rounded-lg p-2 text-xs font-mono text-slate-200 focus:outline-none focus:border-sky-500"
                        />
                      </div>

                      {/* Temperature */}
                      <div className="space-y-1">
                        <div className="flex justify-between text-[11px]">
                          <span className="text-slate-300">Temperature</span>
                          <span className="font-mono text-slate-400">{config.temperature ?? 0.7}</span>
                        </div>
                        <input
                          type="range"
                          min="0"
                          max="2"
                          step="0.05"
                          value={config.temperature ?? 0.7}
                          onChange={(e) => handleConfigChange("temperature", parseFloat(e.target.value))}
                          className="w-full accent-sky-500"
                        />
                      </div>

                      {/* Max Iterations */}
                      <div className="space-y-1">
                        <div className="flex justify-between text-[11px]">
                          <span className="text-slate-300">Max ReAct Iterations</span>
                          <span className="font-mono text-slate-400">{config.max_iterations ?? 10}</span>
                        </div>
                        <input
                          type="number"
                          min="1"
                          max="50"
                          value={config.max_iterations ?? 10}
                          onChange={(e) => handleConfigChange("max_iterations", parseInt(e.target.value, 10))}
                          className="w-full bg-[#1e293b] border border-slate-700 rounded-lg px-2.5 py-1 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
                        />
                      </div>

                      {/* Static Custom Tools */}
                      <div className="space-y-2 pt-2 border-t border-slate-800">
                        <div className="flex items-center justify-between text-[11px]">
                          <span className="text-slate-300 font-medium">SDK Python Function Tools:</span>
                        </div>

                        {staticTools.length > 0 && (
                          <div className="flex flex-wrap gap-1">
                            {staticTools.map((tName) => (
                              <span
                                key={tName}
                                className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-200 font-mono"
                              >
                                <span>{tName}</span>
                                <button
                                  type="button"
                                  onClick={() => handleRemoveTool(tName)}
                                  className="hover:text-rose-400 focus:outline-none"
                                >
                                  <X className="w-2.5 h-2.5" />
                                </button>
                              </span>
                            ))}
                          </div>
                        )}

                        <div className="flex gap-1">
                          <input
                            type="text"
                            value={customToolInput}
                            onChange={(e) => setCustomToolInput(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") {
                                e.preventDefault();
                                handleAddCustomTool();
                              }
                            }}
                            placeholder="e.g. fetch_stock_price"
                            className="flex-1 bg-[#1e293b] border border-slate-700 rounded px-2 py-1 text-[11px] font-mono text-slate-200 focus:outline-none focus:border-sky-500"
                          />
                          <button
                            type="button"
                            onClick={handleAddCustomTool}
                            className="px-2 py-1 text-[11px] rounded bg-slate-800 hover:bg-slate-700 text-slate-200"
                          >
                            Add
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              /* DYNAMIC CONFIGURATION FOR ALL OTHER NODES */
              <div className="space-y-4">
                {Object.keys(schema).length === 0 && (
                  <p className="text-xs text-slate-500">This node does not require configuration.</p>
                )}

                {Object.entries(schema).map(([key, prop]: [string, any]) => {
                  const val = config[key] !== undefined ? config[key] : prop.default || "";
                  const isRequired = requiredFields.includes(key);
                  const isPassword =
                    prop.format === "password" ||
                    key.toLowerCase().includes("key") ||
                    key.toLowerCase().includes("secret") ||
                    key.toLowerCase().includes("token");

                  // Multiline Prompts or Text fields
                  if (
                    key === "prompt" ||
                    key === "system_prompt" ||
                    key === "query" ||
                    key === "default_query" ||
                    key === "default_expression" ||
                    key === "message" ||
                    key === "response" ||
                    (prop.type === "string" && prop.description?.toLowerCase().includes("prompt"))
                  ) {
                    return (
                      <div key={key} className="space-y-1">
                        <div className="flex items-center justify-between">
                          <label className="text-xs font-semibold text-slate-300 capitalize">
                            {key.replace(/_/g, " ")}
                            {isRequired && <span className="text-rose-400 text-xs ml-0.5">*</span>}
                          </label>
                          <VariablePicker
                            variables={availableVariables}
                            currentValue={val}
                            onInsertVariable={(varExpr) => {
                              const cur = val || "";
                              handleConfigChange(key, `${cur ? cur + " " : ""}${varExpr}`);
                            }}
                          />
                        </div>
                        <textarea
                          rows={3}
                          value={val}
                          onChange={(e) => handleConfigChange(key, e.target.value)}
                          placeholder={prop.description}
                          className="w-full bg-[#1e293b] border border-slate-700 rounded-lg p-2 text-xs font-mono text-slate-200 focus:outline-none focus:border-sky-500"
                        />
                      </div>
                    );
                  }

                  // Model identifier with presets
                  if (key === "model") {
                    return (
                      <div key={key} className="space-y-1.5">
                        <div className="flex items-center justify-between">
                          <label className="text-xs font-semibold text-slate-300 capitalize">
                            {key.replace(/_/g, " ")}
                            {isRequired && <span className="text-rose-400 text-xs ml-0.5">*</span>}
                          </label>
                          <VariablePicker
                            variables={availableVariables}
                            currentValue={val}
                            onInsertVariable={(varExpr) => handleConfigChange(key, varExpr)}
                          />
                        </div>
                        <input
                          type="text"
                          value={val}
                          onChange={(e) => handleConfigChange(key, e.target.value)}
                          className="w-full bg-[#1e293b] border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs font-mono text-slate-100 focus:outline-none focus:border-sky-500"
                        />
                        <div className="flex flex-wrap gap-1">
                          {MODEL_PRESETS.map((p) => (
                            <button
                              key={p.value}
                              type="button"
                              onClick={() => handleConfigChange(key, p.value)}
                              className="text-[9px] px-1.5 py-0.5 rounded border border-slate-700 bg-slate-800/60 text-slate-400 hover:text-slate-200 font-mono"
                            >
                              {p.label}
                            </button>
                          ))}
                        </div>
                      </div>
                    );
                  }

                  // Password / secret
                  if (isPassword) {
                    const isShowing = showSecrets[key] || false;
                    return (
                      <div key={key} className="space-y-1.5">
                        <div className="flex items-center justify-between">
                          <label className="text-xs font-semibold text-slate-300 capitalize flex items-center gap-1.5">
                            <Key className="w-3.5 h-3.5 text-amber-400" />
                            <span>{key.replace(/_/g, " ")}</span>
                            {isRequired && <span className="text-rose-400 text-xs">*</span>}
                          </label>
                          <VariablePicker
                            variables={availableVariables}
                            currentValue={val}
                            onInsertVariable={(varExpr) => handleConfigChange(key, varExpr)}
                          />
                        </div>
                        <div className="relative">
                          <input
                            type={isShowing ? "text" : "password"}
                            value={val}
                            onChange={(e) => handleConfigChange(key, e.target.value)}
                            placeholder={prop.description || "sk-..."}
                            className="w-full bg-[#1e293b] border border-slate-700 rounded-lg pl-2.5 pr-8 py-1.5 text-xs font-mono text-slate-100 focus:outline-none focus:border-sky-500"
                          />
                          <button
                            type="button"
                            onClick={() => toggleShowSecret(key)}
                            className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 focus:outline-none"
                          >
                            {isShowing ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                          </button>
                        </div>
                      </div>
                    );
                  }

                  // Fallback string / number inputs
                  return (
                    <div key={key} className="space-y-1">
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-semibold text-slate-300 capitalize">
                          {key.replace(/_/g, " ")}
                          {isRequired && <span className="text-rose-400 text-xs ml-0.5">*</span>}
                        </label>
                        {prop.type === "string" && (
                          <VariablePicker
                            variables={availableVariables}
                            currentValue={val}
                            onInsertVariable={(varExpr) => {
                              const cur = val || "";
                              handleConfigChange(key, `${cur ? cur + " " : ""}${varExpr}`);
                            }}
                          />
                        )}
                      </div>
                      <input
                        type={prop.type === "number" || prop.type === "integer" ? "number" : "text"}
                        value={typeof val === "object" ? JSON.stringify(val) : val}
                        onChange={(e) => {
                          let parsed: any = e.target.value;
                          if (prop.type === "number" || prop.type === "integer") {
                            parsed = parseFloat(e.target.value) || 0;
                          }
                          handleConfigChange(key, parsed);
                        }}
                        placeholder={prop.description}
                        className="w-full bg-[#1e293b] border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
                      />
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        ) : (
          /* EXECUTION DATA TAB */
          <div className="space-y-3">
            {!executionRecord ? (
              <p className="text-xs text-slate-500">No execution record available for this node yet.</p>
            ) : (
              <>
                <div className="flex items-center justify-between text-xs pb-2 border-b border-slate-800">
                  <span className="text-slate-400">Status:</span>
                  <span className="font-semibold uppercase tracking-wider text-[11px] px-2 py-0.5 rounded bg-slate-800 text-slate-200">
                    {executionRecord.status}
                  </span>
                </div>
                {executionRecord.duration !== undefined && (
                  <div className="flex items-center justify-between text-xs pb-2 border-b border-slate-800">
                    <span className="text-slate-400">Duration:</span>
                    <span className="font-mono text-slate-300">{executionRecord.duration.toFixed(3)}s</span>
                  </div>
                )}
                <div className="space-y-1">
                  <label className="text-[11px] font-medium text-slate-400">Input Data:</label>
                  <pre className="p-2 rounded bg-slate-950 border border-slate-800 text-[10px] font-mono text-slate-300 overflow-x-auto max-h-36">
                    {JSON.stringify(executionRecord.input_data, null, 2) || "{}"}
                  </pre>
                </div>
                <div className="space-y-1">
                  <label className="text-[11px] font-medium text-slate-400">Output Data:</label>
                  <pre className="p-2 rounded bg-slate-950 border border-slate-800 text-[10px] font-mono text-slate-300 overflow-x-auto max-h-36">
                    {JSON.stringify(executionRecord.output_data, null, 2) || "{}"}
                  </pre>
                </div>
                {executionRecord.error && (
                  <div className="p-2 rounded bg-rose-950/40 border border-rose-800/50 text-rose-300 text-xs">
                    {executionRecord.error}
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </aside>
  );
};
