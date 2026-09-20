import React, { useState, useEffect } from "react";
import {
  Sparkles,
  X,
  Zap,
  CheckCircle2,
  AlertCircle,
  Code2,
  Cpu,
  Key,
  ChevronDown,
  ChevronUp,
  Settings,
  ArrowRight,
  ShieldCheck,
  Layers,
  Wrench,
  Lock,
} from "lucide-react";
import { api } from "../api/client";
import {
  AgentSynthesisResult,
  ManagerStatus,
  ManagerTemplate,
  WorkflowDefinition,
} from "../types/workflow";

interface AgentSynthesizerModalProps {
  isOpen: boolean;
  onClose: () => void;
  onApplyGraph: (synthesizedGraph: { nodes: any[]; edges: any[] }, agentSpec: any) => void;
  currentWorkflow: WorkflowDefinition;
}

export const AgentSynthesizerModal: React.FC<AgentSynthesizerModalProps> = ({
  isOpen,
  onClose,
  onApplyGraph,
  currentWorkflow,
}) => {
  const [status, setStatus] = useState<ManagerStatus>({
    ready: false,
    model: "gpt-4o",
    has_key: false,
  });
  const [showConfig, setShowConfig] = useState(false);
  const [modelInput, setModelInput] = useState("gpt-4o");
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [apiBaseInput, setApiBaseInput] = useState("");
  const [isConfiguring, setIsConfiguring] = useState(false);
  const [configMessage, setConfigMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const [prompt, setPrompt] = useState("");
  const [templates, setTemplates] = useState<ManagerTemplate[]>([]);
  const [isSynthesizing, setIsSynthesizing] = useState(false);
  const [synthesisStage, setSynthesisStage] = useState<number>(0);
  const [result, setResult] = useState<AgentSynthesisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedCodeTool, setExpandedCodeTool] = useState<string | null>(null);

  // Load status and templates
  useEffect(() => {
    if (!isOpen) return;
    async function loadInitial() {
      try {
        const s = await api.getManagerStatus();
        setStatus(s);
        setModelInput(s.model || "gpt-4o");
        if (s.api_base) setApiBaseInput(s.api_base);
        if (!s.ready) setShowConfig(true);

        const tmpls = await api.getManagerTemplates();
        setTemplates(tmpls);
      } catch (err: any) {
        console.warn("Failed to load manager status:", err);
      }
    }
    loadInitial();
  }, [isOpen]);

  const handleSaveConfig = async () => {
    setIsConfiguring(true);
    setConfigMessage(null);
    try {
      const updated = await api.configureManager(
        modelInput.trim(),
        apiKeyInput.trim() || undefined,
        apiBaseInput.trim() || undefined
      );
      setStatus((prev) => ({
        ...prev,
        ready: true,
        model: updated.model,
        has_key: updated.has_key,
        api_base: updated.api_base,
      }));
      setConfigMessage({ type: "success", text: `Master Agent configured for ${updated.model}!` });
      setTimeout(() => setShowConfig(false), 1200);
    } catch (err: any) {
      setConfigMessage({ type: "error", text: err.message || "Configuration failed" });
    } finally {
      setIsConfiguring(false);
    }
  };

  const handleSynthesize = async (promptToUse?: string) => {
    const textToSynthesize = promptToUse || prompt;
    if (!textToSynthesize.trim()) {
      setError("Please provide a prompt describing what you want your agent to accomplish.");
      return;
    }

    setError(null);
    setIsSynthesizing(true);
    setResult(null);
    setSynthesisStage(1);

    const timer1 = setTimeout(() => setSynthesisStage(2), 700);
    const timer2 = setTimeout(() => setSynthesisStage(3), 1500);

    try {
      const data: AgentSynthesisResult = await api.synthesizeAgent(textToSynthesize.trim(), currentWorkflow);
      setResult(data);
      setSynthesisStage(4);
    } catch (err: any) {
      setError(err.message || "Synthesis failed. Check backend configuration.");
    } finally {
      clearTimeout(timer1);
      clearTimeout(timer2);
      setIsSynthesizing(false);
    }
  };

  const handleApplyToCanvas = () => {
    if (!result) return;
    onApplyGraph(result.graph, result.agent_spec);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 animate-in fade-in duration-200 select-none">
      <div className="bg-[#0f172a] border border-sky-500/30 rounded-2xl w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl shadow-sky-950/50 overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-gradient-to-r from-slate-900 via-sky-950/40 to-slate-900">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-sky-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-sky-500/25">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                Prompt-to-Agent Studio
                <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-sky-500/10 text-sky-400 border border-sky-500/30">
                  Autonomous Agent & Dynamic Tooling
                </span>
              </h2>
              <p className="text-xs text-slate-400">
                Describe desired behaviors in natural language. The Master Agent synthesizes agent architecture and dynamic tools.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Status Pill */}
            <button
              onClick={() => setShowConfig((prev) => !prev)}
              className={`flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full border transition-all ${
                status.ready
                  ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/30 hover:bg-emerald-500/20"
                  : "bg-amber-500/10 text-amber-300 border-amber-500/30 hover:bg-amber-500/20 animate-pulse"
              }`}
              title="Click to configure Master Agent model & API key"
            >
              {status.ready ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> : <AlertCircle className="w-3.5 h-3.5 text-amber-400" />}
              <span>{status.ready ? `Ready (${status.model})` : "Setup Master Agent"}</span>
              <Settings className="w-3 h-3 text-slate-400 ml-1" />
            </button>

            <button
              onClick={onClose}
              className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Master Agent Configuration Drawer (Collapsible) */}
        {showConfig && (
          <div className="p-4 bg-slate-900/90 border-b border-slate-800 animate-in slide-in-from-top-2 duration-200">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2 text-xs font-bold text-sky-400">
                <Key className="w-3.5 h-3.5" />
                <span>Master Agent LLM Configuration</span>
              </div>
              <span className="text-[11px] text-slate-400">
                Keys are stored securely in backend runtime and never leaked in agent definitions.
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
              <div>
                <label className="text-slate-300 font-medium mb-1 block">Model Name</label>
                <input
                  type="text"
                  value={modelInput}
                  onChange={(e) => setModelInput(e.target.value)}
                  placeholder="gpt-4o, claude-3-5-sonnet, ollama/..."
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-sky-500"
                />
              </div>
              <div>
                <label className="text-slate-300 font-medium mb-1 block">API Key (Masked)</label>
                <input
                  type="password"
                  value={apiKeyInput}
                  onChange={(e) => setApiKeyInput(e.target.value)}
                  placeholder={status.has_key ? "••••••••••••••••••••" : "sk-..."}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-sky-500"
                />
              </div>
              <div>
                <label className="text-slate-300 font-medium mb-1 block">API Base URL (Optional)</label>
                <input
                  type="text"
                  value={apiBaseInput}
                  onChange={(e) => setApiBaseInput(e.target.value)}
                  placeholder="http://localhost:4000/v1"
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-sky-500"
                />
              </div>
            </div>

            {configMessage && (
              <div
                className={`mt-2 text-xs px-2.5 py-1 rounded border flex items-center gap-2 ${
                  configMessage.type === "success"
                    ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/30"
                    : "bg-rose-500/10 text-rose-300 border-rose-500/30"
                }`}
              >
                {configMessage.type === "success" ? <CheckCircle2 className="w-3.5 h-3.5" /> : <AlertCircle className="w-3.5 h-3.5" />}
                <span>{configMessage.text}</span>
              </div>
            )}

            <div className="mt-3 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowConfig(false)}
                className="px-3 py-1 text-xs text-slate-400 hover:text-white"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSaveConfig}
                disabled={isConfiguring}
                className="bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs px-4 py-1.5 rounded-lg flex items-center gap-1.5 shadow-md shadow-sky-600/20"
              >
                {isConfiguring ? "Validating..." : "Save & Verify"}
              </button>
            </div>
          </div>
        )}

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Natural Language Prompt Area */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
                <Cpu className="w-3.5 h-3.5 text-sky-400" />
                Describe Your Agent's Goal & Capabilities
              </label>
              <span className="text-[11px] text-slate-400">Natural language intent</span>
            </div>

            <div className="relative">
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="e.g. Create a Customer Support Agent that queries PostgreSQL database for order status, searches policy docs, and sends an email alert with human approval when escalation is required."
                rows={3}
                className="w-full bg-slate-950 border border-slate-700 hover:border-slate-600 focus:border-sky-500 rounded-xl p-3.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none shadow-inner leading-relaxed transition-colors"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                    handleSynthesize();
                  }
                }}
              />

              <div className="flex items-center justify-between mt-2">
                <span className="text-[11px] text-slate-500">
                  Tip: Mention databases, APIs, documents, or alerts to automatically synthesize tools.
                </span>

                <button
                  type="button"
                  onClick={() => handleSynthesize()}
                  disabled={isSynthesizing || !prompt.trim()}
                  className={`flex items-center gap-2 font-bold text-xs px-5 py-2 rounded-xl shadow-lg transition-all ${
                    isSynthesizing || !prompt.trim()
                      ? "bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700"
                      : "bg-gradient-to-r from-sky-500 to-blue-600 hover:from-sky-400 hover:to-blue-500 text-white shadow-sky-500/25 hover:scale-[1.02] active:scale-[0.98]"
                  }`}
                >
                  <Sparkles className={`w-4 h-4 ${isSynthesizing ? "animate-spin" : ""}`} />
                  <span>{isSynthesizing ? "Synthesizing Agent..." : "Generate Agent & Tools"}</span>
                </button>
              </div>
            </div>
          </div>

          {/* Quick Starter Templates */}
          {templates.length > 0 && (
            <div className="space-y-2">
              <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">
                Quick-Start Agent Templates
              </span>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                {templates.map((tmpl) => (
                  <div
                    key={tmpl.id}
                    onClick={() => {
                      setPrompt(tmpl.prompt);
                      handleSynthesize(tmpl.prompt);
                    }}
                    className="group p-3 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-sky-500/50 hover:bg-slate-850 cursor-pointer transition-all flex flex-col justify-between"
                  >
                    <div className="flex items-start justify-between gap-2 mb-1">
                      <h4 className="text-xs font-bold text-slate-200 group-hover:text-sky-300 transition-colors">
                        {tmpl.title}
                      </h4>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 font-medium">
                        {tmpl.category}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-400 line-clamp-2 mb-2 leading-relaxed">
                      {tmpl.prompt}
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {tmpl.tags.map((t, idx) => (
                        <span key={idx} className="text-[9px] px-1.5 py-0.5 rounded bg-sky-950/40 text-sky-400/90 border border-sky-500/20 font-mono">
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Synthesis Multi-Stage Progress */}
          {isSynthesizing && (
            <div className="p-4 rounded-xl bg-slate-900 border border-sky-500/30 space-y-3 animate-in fade-in duration-200">
              <div className="flex items-center gap-2 text-xs font-bold text-sky-400">
                <Zap className="w-4 h-4 animate-bounce text-sky-400" />
                <span>Master Agent Synthesis in Progress</span>
              </div>

              <div className="space-y-2 text-xs">
                <div className={`flex items-center gap-2 transition-colors ${synthesisStage >= 1 ? "text-slate-200" : "text-slate-600"}`}>
                  <div className={`w-2 h-2 rounded-full ${synthesisStage >= 1 ? "bg-emerald-400 animate-ping" : "bg-slate-700"}`} />
                  <span>Analyzing requirements and generating Agent persona & instructions...</span>
                </div>
                <div className={`flex items-center gap-2 transition-colors ${synthesisStage >= 2 ? "text-slate-200" : "text-slate-600"}`}>
                  <div className={`w-2 h-2 rounded-full ${synthesisStage >= 2 ? "bg-emerald-400 animate-ping" : "bg-slate-700"}`} />
                  <span>Discovering matching tools and compiling secure Dynamic Python skills...</span>
                </div>
                <div className={`flex items-center gap-2 transition-colors ${synthesisStage >= 3 ? "text-slate-200" : "text-slate-600"}`}>
                  <div className={`w-2 h-2 rounded-full ${synthesisStage >= 3 ? "bg-emerald-400 animate-ping" : "bg-slate-700"}`} />
                  <span>Validating AST safety checks and compiling React Flow graph wiring...</span>
                </div>
              </div>
            </div>
          )}

          {/* Error Banner */}
          {error && (
            <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2.5">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Synthesis Results Preview */}
          {result && (
            <div className="space-y-4 animate-in fade-in-50 duration-300">
              <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <span className="text-xs font-bold text-emerald-400 uppercase tracking-wider">
                    Synthesis Complete
                  </span>
                </div>
                <span className="text-xs text-slate-400 font-medium">
                  {result.summary}
                </span>
              </div>

              {/* Agent Spec Summary Card */}
              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-lg bg-sky-500/20 text-sky-400 flex items-center justify-center font-bold text-sm">
                      🤖
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-white">{result.agent_spec.name}</h3>
                      <p className="text-xs text-slate-400">{result.agent_spec.role}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] px-2 py-0.5 rounded-md bg-slate-800 text-slate-300 font-mono">
                      Model: {result.agent_spec.recommended_model}
                    </span>
                    <span className="text-[10px] px-2 py-0.5 rounded-md bg-slate-800 text-slate-300 font-mono">
                      Temp: {result.agent_spec.temperature}
                    </span>
                  </div>
                </div>

                {/* Instructions preview */}
                <div className="bg-slate-950 p-3 rounded-lg border border-slate-800/80">
                  <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">
                    System Instructions
                  </span>
                  <p className="text-xs text-slate-300 line-clamp-3 font-mono leading-relaxed whitespace-pre-wrap">
                    {result.agent_spec.system_prompt}
                  </p>
                </div>
              </div>

              {/* Synthesized Tools Grid */}
              <div className="space-y-2">
                <span className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                  <Wrench className="w-3.5 h-3.5 text-emerald-400" />
                  Attached Tools ({result.prebuilt_tools.length + result.dynamic_tools.length})
                </span>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {/* Prebuilt Tools */}
                  {result.prebuilt_tools.map((pt, idx) => (
                    <div
                      key={idx}
                      className="p-3 rounded-xl bg-slate-900 border border-emerald-500/20 flex items-start gap-2.5"
                    >
                      <div className="w-7 h-7 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center shrink-0">
                        🧩
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-1 mb-0.5">
                          <h4 className="text-xs font-bold text-slate-200 truncate capitalize">
                            {pt.replace(/_/g, " ")}
                          </h4>
                          <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-950/40 text-emerald-400 border border-emerald-500/30 uppercase font-mono">
                            Prebuilt
                          </span>
                        </div>

                        <p className="text-[11px] text-slate-400">
                          Equips agent with native verified capability.
                        </p>
                      </div>
                    </div>
                  ))}

                  {/* Dynamic Synthesized Tools */}
                  {result.dynamic_tools.map((dt, idx) => (
                    <div
                      key={idx}
                      className="p-3 rounded-xl bg-slate-900 border border-violet-500/30 flex flex-col justify-between space-y-2"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <div className="w-7 h-7 rounded-lg bg-violet-500/10 text-violet-400 flex items-center justify-center shrink-0">
                            <Zap className="w-4 h-4 text-violet-400" />
                          </div>
                          <div>
                            <h4 className="text-xs font-bold text-white truncate">{dt.name}</h4>
                            <span className="text-[9px] px-1.5 py-0.5 rounded bg-violet-950/40 text-violet-400 border border-violet-500/30 uppercase font-mono font-semibold">
                              ⚡ Dynamic Tool
                            </span>
                          </div>
                        </div>

                        {dt.approval_required && (
                          <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/30 flex items-center gap-1 font-semibold">
                            <Lock className="w-2.5 h-2.5" /> Approval
                          </span>
                        )}
                      </div>

                      <p className="text-[11px] text-slate-400 line-clamp-2">
                        {dt.description}
                      </p>

                      {/* Code preview toggle */}
                      <button
                        type="button"
                        onClick={() =>
                          setExpandedCodeTool((prev) => (prev === dt.name ? null : dt.name))
                        }
                        className="text-[10px] text-sky-400 hover:text-sky-300 flex items-center gap-1 font-mono pt-1"
                      >
                        <Code2 className="w-3 h-3" />
                        <span>{expandedCodeTool === dt.name ? "Hide Python Code" : "Inspect Python Source"}</span>
                        {expandedCodeTool === dt.name ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                      </button>

                      {expandedCodeTool === dt.name && (
                        <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-800 text-[11px] font-mono text-emerald-300 overflow-x-auto whitespace-pre leading-snug animate-in fade-in-50">
                          {dt.code}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3.5 border-t border-slate-800 bg-slate-900/60 flex items-center justify-between">
          <div className="text-xs text-slate-400 flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>AST Security Verified • Graph Patch Protocol Ready</span>
          </div>

          <div className="flex items-center gap-2.5">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-semibold text-slate-300 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
            >
              Close
            </button>

            {result && (
              <button
                type="button"
                onClick={handleApplyToCanvas}
                className="bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white font-bold text-xs px-5 py-2 rounded-xl shadow-lg shadow-emerald-500/20 flex items-center gap-2 transition-all hover:scale-[1.02] active:scale-[0.98]"
              >
                <span>Apply to Canvas & Wire</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
