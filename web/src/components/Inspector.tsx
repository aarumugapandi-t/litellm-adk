import React, { useState, useEffect } from "react";
import { Node } from "@xyflow/react";
import {
  Trash2,
  HelpCircle,
  Code,
  Play,
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
} from "lucide-react";
import { NodeDefinition, NodeExecutionRecord } from "../types/workflow";
import { api } from "../api/client";

interface InspectorProps {
  selectedNode: Node | null;
  availableNodes: NodeDefinition[];
  onUpdateNodeData: (nodeId: string, updatedData: any) => void;
  onDeleteNode: (nodeId: string) => void;
  executionRecord?: NodeExecutionRecord | null;
}

const MODEL_PRESETS = [
  { label: "Ministral 3B", value: "openrouter/mistralai/ministral-3b-2512" },
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
}) => {
  const [activeTab, setActiveTab] = useState<"config" | "execution">("config");
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({});
  const [availableTools, setAvailableTools] = useState<any[]>([]);
  const [customToolInput, setCustomToolInput] = useState("");

  useEffect(() => {
    api.getTools().then(setAvailableTools).catch(() => {});
  }, []);

  if (!selectedNode) {
    return (
      <aside className="w-80 border-l border-slate-800 bg-[#0f172a] flex flex-col items-center justify-center p-6 text-center text-slate-500 select-none">
        <HelpCircle className="w-8 h-8 mb-2 opacity-40" />
        <p className="text-xs">Select any node on the canvas to inspect its configuration schema and execution state.</p>
      </aside>
    );
  }

  const def = availableNodes.find((n) => n.type === selectedNode.data?.type);
  const config = (selectedNode.data?.config as Record<string, any>) || {};
  const schema = def?.config_schema?.properties || {};
  const requiredFields: string[] = def?.config_schema?.required || [];

  const handleConfigChange = (key: string, value: any) => {
    onUpdateNodeData(selectedNode.id, {
      ...selectedNode.data,
      config: {
        ...config,
        [key]: value,
      },
    });
  };

  const toggleShowSecret = (key: string) => {
    setShowSecrets((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  // Tools management helpers
  const currentTools: string[] = Array.isArray(config.tools)
    ? config.tools
    : typeof config.tools === "string" && config.tools
    ? config.tools.split(",").map((s: string) => s.trim()).filter(Boolean)
    : [];

  const handleToggleTool = (toolName: string) => {
    if (currentTools.includes(toolName)) {
      handleConfigChange("tools", currentTools.filter((t: string) => t !== toolName));
    } else {
      handleConfigChange("tools", [...currentTools, toolName]);
    }
  };

  const handleAddCustomTool = () => {
    const trimmed = customToolInput.trim();
    if (!trimmed) return;
    if (!currentTools.includes(trimmed)) {
      handleConfigChange("tools", [...currentTools, trimmed]);
    }
    setCustomToolInput("");
  };

  const handleRemoveTool = (toolName: string) => {
    handleConfigChange("tools", currentTools.filter((t: string) => t !== toolName));
  };

  const handleNameChange = (newName: string) => {
    onUpdateNodeData(selectedNode.id, {
      ...selectedNode.data,
      name: newName,
    });
  };

  const insertVariable = (fieldKey: string, variableExpr: string) => {
    const currentVal = config[fieldKey] || "";
    handleConfigChange(fieldKey, `${currentVal} ${variableExpr}`.trim());
  };

  return (
    <aside className="w-80 border-l border-slate-800 bg-[#0f172a] flex flex-col h-full z-10 select-none">
      {/* Inspector Header */}
      <div className="p-3 border-b border-slate-800 flex items-center justify-between">
        <div className="min-w-0">
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
          className="p-1.5 rounded-lg border border-rose-900/40 bg-rose-950/20 hover:bg-rose-900/40 text-rose-400 transition"
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

              // 1. Specialized Tools Selector
              if (key === "tools") {
                return (
                  <div key={key} className="space-y-2 pt-2 border-t border-slate-800/60">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-medium text-slate-200 flex items-center gap-1.5">
                        <Wrench className="w-3.5 h-3.5 text-emerald-400" />
                        <span>Tools & Capabilities</span>
                      </label>
                      <span className="text-[10px] text-slate-500 font-mono">{currentTools.length} enabled</span>
                    </div>

                    {/* Active Selected Tools Pills */}
                    <div className="flex flex-wrap gap-1.5 min-h-[32px] p-2 bg-[#1e293b]/70 border border-slate-700/60 rounded-lg">
                      {currentTools.length === 0 ? (
                        <span className="text-[11px] text-slate-500 italic">No tools assigned to this agent</span>
                      ) : (
                        currentTools.map((tName) => (
                          <span
                            key={tName}
                            className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded bg-emerald-950 border border-emerald-700/60 text-emerald-300 font-mono"
                          >
                            <span>{tName}</span>
                            <button
                              type="button"
                              onClick={() => handleRemoveTool(tName)}
                              className="hover:text-rose-400 focus:outline-none ml-0.5"
                            >
                              <X className="w-3 h-3" />
                            </button>
                          </span>
                        ))
                      )}
                    </div>

                    {/* Available Registered Tools Pickers */}
                    {availableTools.length > 0 && (
                      <div className="space-y-1">
                        <span className="text-[10px] text-slate-400 block font-medium">Registered Tools:</span>
                        <div className="flex flex-wrap gap-1">
                          {availableTools.map((t) => {
                            const isSelected = currentTools.includes(t.name);
                            return (
                              <button
                                key={t.name}
                                type="button"
                                onClick={() => handleToggleTool(t.name)}
                                className={`text-[10px] px-2 py-0.5 rounded border transition font-mono ${
                                  isSelected
                                    ? "bg-emerald-600/30 border-emerald-500 text-emerald-300"
                                    : "bg-slate-800/80 border-slate-700 text-slate-400 hover:text-slate-200"
                                }`}
                                title={t.description}
                              >
                                {isSelected ? "✓ " : "+ "}
                                {t.name}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {/* Add Custom Tool Input Box */}
                    <div className="flex gap-1 pt-1">
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
                        className="flex-1 bg-[#1e293b] border border-slate-700 rounded-lg px-2.5 py-1 text-xs font-mono text-slate-200 focus:outline-none focus:border-emerald-500"
                      />
                      <button
                        type="button"
                        onClick={handleAddCustomTool}
                        className="px-2.5 py-1 text-xs font-medium rounded-lg bg-emerald-950/80 border border-emerald-700/60 text-emerald-300 hover:bg-emerald-900/80 flex items-center gap-1 transition"
                      >
                        <Plus className="w-3 h-3" />
                        <span>Add</span>
                      </button>
                    </div>
                  </div>
                );
              }

              // 2. Specialized Model Input with Quick Presets
              if (key === "model") {
                return (
                  <div key={key} className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-medium text-slate-200 flex items-center gap-1.5">
                        <Bot className="w-3.5 h-3.5 text-sky-400" />
                        <span>Model Identifier</span>
                        {isRequired && <span className="text-rose-400 text-xs">*</span>}
                      </label>
                      <button
                        type="button"
                        onClick={() => insertVariable("model", "{{ variables.model }}")}
                        className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-violet-950/60 border border-violet-700/50 text-violet-400 hover:bg-violet-900/60"
                      >
                        +var
                      </button>
                    </div>

                    <input
                      type="text"
                      value={val}
                      onChange={(e) => handleConfigChange("model", e.target.value)}
                      placeholder="e.g. openrouter/mistralai/ministral-3b-2512"
                      className="w-full bg-[#1e293b] border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs font-mono text-slate-100 focus:outline-none focus:border-sky-500"
                    />

                    {/* Quick Model Presets */}
                    <div className="flex flex-wrap gap-1 pt-0.5">
                      {MODEL_PRESETS.map((p) => (
                        <button
                          key={p.value}
                          type="button"
                          onClick={() => handleConfigChange("model", p.value)}
                          className={`text-[9px] px-1.5 py-0.5 rounded border transition font-mono ${
                            val === p.value
                              ? "bg-sky-950 border-sky-500 text-sky-300"
                              : "bg-slate-800/60 border-slate-700/60 text-slate-400 hover:text-slate-200"
                          }`}
                        >
                          {p.label}
                        </button>
                      ))}
                    </div>
                  </div>
                );
              }

              // 3. Specialized Base URL Input with Presets
              if (key === "base_url") {
                return (
                  <div key={key} className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-medium text-slate-200 flex items-center gap-1.5">
                        <Globe className="w-3.5 h-3.5 text-sky-400" />
                        <span>API Base URL</span>
                        {isRequired && <span className="text-rose-400 text-xs">*</span>}
                      </label>
                      <button
                        type="button"
                        onClick={() => insertVariable("base_url", "{{ variables.base_url }}")}
                        className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-violet-950/60 border border-violet-700/50 text-violet-400 hover:bg-violet-900/60"
                      >
                        +var
                      </button>
                    </div>

                    <input
                      type="text"
                      value={val}
                      onChange={(e) => handleConfigChange("base_url", e.target.value)}
                      placeholder="http://localhost:9000/v1"
                      className="w-full bg-[#1e293b] border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs font-mono text-slate-100 focus:outline-none focus:border-sky-500"
                    />

                    {/* Quick Base URL Presets */}
                    <div className="flex flex-wrap gap-1 pt-0.5">
                      {BASE_URL_PRESETS.map((p) => (
                        <button
                          key={p.value}
                          type="button"
                          onClick={() => handleConfigChange("base_url", p.value)}
                          className={`text-[9px] px-1.5 py-0.5 rounded border transition font-mono ${
                            val === p.value
                              ? "bg-sky-950 border-sky-500 text-sky-300"
                              : "bg-slate-800/60 border-slate-700/60 text-slate-400 hover:text-slate-200"
                          }`}
                        >
                          {p.label}
                        </button>
                      ))}
                    </div>
                  </div>
                );
              }

              // 4. Specialized Password / API Key Input
              if (isPassword) {
                const isShowing = showSecrets[key] || false;
                return (
                  <div key={key} className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-medium text-slate-200 flex items-center gap-1.5">
                        <Key className="w-3.5 h-3.5 text-amber-400" />
                        <span className="capitalize">{key.replace(/_/g, " ")}</span>
                        {isRequired && <span className="text-rose-400 text-xs">*</span>}
                      </label>
                      <button
                        type="button"
                        onClick={() => insertVariable(key, `{{ variables.${key} }}`)}
                        className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-violet-950/60 border border-violet-700/50 text-violet-400 hover:bg-violet-900/60"
                      >
                        +var
                      </button>
                    </div>

                    <div className="relative">
                      <input
                        type={isShowing ? "text" : "password"}
                        value={val}
                        onChange={(e) => handleConfigChange(key, e.target.value)}
                        placeholder={prop.description || "sk-1234 or {{ variables.api_key }}"}
                        className="w-full bg-[#1e293b] border border-slate-700 rounded-lg pl-2.5 pr-8 py-1.5 text-xs font-mono text-slate-100 focus:outline-none focus:border-sky-500"
                      />
                      <button
                        type="button"
                        onClick={() => toggleShowSecret(key)}
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 focus:outline-none"
                        title={isShowing ? "Hide API key" : "Show API key"}
                      >
                        {isShowing ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                    <span className="text-[10px] text-slate-500 block leading-tight">
                      {prop.description || "Secure credential passed at runtime."}
                    </span>
                  </div>
                );
              }

              // 5. Enum Selector
              if (prop.enum) {
                return (
                  <div key={key} className="space-y-1">
                    <label className="text-xs font-medium text-slate-300 capitalize">
                      {key.replace(/_/g, " ")}
                      {isRequired && <span className="text-rose-400 text-xs ml-0.5">*</span>}
                    </label>
                    <select
                      value={val}
                      onChange={(e) => handleConfigChange(key, e.target.value)}
                      className="w-full bg-[#1e293b] border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
                    >
                      {prop.enum.map((opt: string) => (
                        <option key={opt} value={opt}>
                          {opt}
                        </option>
                      ))}
                    </select>
                  </div>
                );
              }

              // 6. Prompts / Multiline Textareas
              if (
                key === "prompt" ||
                key === "system_prompt" ||
                (prop.type === "string" && prop.description?.toLowerCase().includes("prompt"))
              ) {
                return (
                  <div key={key} className="space-y-1">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-medium text-slate-300 capitalize">
                        {key.replace(/_/g, " ")}
                        {isRequired && <span className="text-rose-400 text-xs ml-0.5">*</span>}
                      </label>
                      <div className="flex gap-1">
                        <button
                          type="button"
                          onClick={() => insertVariable(key, "{{ trigger.input }}")}
                          className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-sky-950/60 border border-sky-700/50 text-sky-400 hover:bg-sky-900/60"
                        >
                          +trigger
                        </button>
                        <button
                          type="button"
                          onClick={() => insertVariable(key, "{{ variables.user_id }}")}
                          className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-violet-950/60 border border-violet-700/50 text-violet-400 hover:bg-violet-900/60"
                        >
                          +var
                        </button>
                      </div>
                    </div>
                    <textarea
                      rows={key === "prompt" ? 4 : 3}
                      value={val}
                      onChange={(e) => handleConfigChange(key, e.target.value)}
                      placeholder={prop.description}
                      className="w-full bg-[#1e293b] border border-slate-700 rounded-lg p-2 text-xs font-mono text-slate-200 focus:outline-none focus:border-sky-500"
                    />
                  </div>
                );
              }

              // 7. Numbers (Temperature, Max Iterations, Tokens)
              if (prop.type === "number" || prop.type === "integer") {
                return (
                  <div key={key} className="space-y-1">
                    <div className="flex justify-between items-center text-xs">
                      <label className="font-medium text-slate-300 capitalize">{key.replace(/_/g, " ")}</label>
                      <span className="text-slate-500 font-mono">{val}</span>
                    </div>
                    <input
                      type="number"
                      step={prop.type === "integer" ? 1 : 0.1}
                      min={prop.minimum}
                      max={prop.maximum}
                      value={val}
                      onChange={(e) => handleConfigChange(key, parseFloat(e.target.value) || 0)}
                      className="w-full bg-[#1e293b] border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
                    />
                  </div>
                );
              }

              // 8. Generic Strings & Fallbacks
              return (
                <div key={key} className="space-y-1">
                  <label className="text-xs font-medium text-slate-300 capitalize">
                    {key.replace(/_/g, " ")}
                    {isRequired && <span className="text-rose-400 text-xs ml-0.5">*</span>}
                  </label>
                  <input
                    type="text"
                    value={typeof val === "object" ? JSON.stringify(val) : val}
                    onChange={(e) => {
                      let parsed = e.target.value;
                      if (prop.type === "object" || prop.type === "array") {
                        try {
                          parsed = JSON.parse(e.target.value);
                        } catch {}
                      }
                      handleConfigChange(key, parsed);
                    }}
                    placeholder={prop.description}
                    className="w-full bg-[#1e293b] border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
                  />
                  {prop.description && (
                    <span className="text-[10px] text-slate-500 block leading-tight">{prop.description}</span>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
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
