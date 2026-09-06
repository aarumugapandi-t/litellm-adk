import React, { useState } from "react";
import {
  Play,
  Save,
  FolderOpen,
  History,
  Download,
  Upload,
  Check,
  Zap,
  RotateCcw,
} from "lucide-react";
import { WorkflowDefinition } from "../types/workflow";

interface HeaderProps {
  workflow: WorkflowDefinition;
  onUpdateWorkflow: (updated: Partial<WorkflowDefinition>) => void;
  onSave: () => Promise<void>;
  onTestRun: () => void;
  onOpenWorkflowsList: () => void;
  onOpenHistory: () => void;
  onExport: () => void;
  onImport: () => void;
  isSaving: boolean;
  isRunning: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  workflow,
  onUpdateWorkflow,
  onSave,
  onTestRun,
  onOpenWorkflowsList,
  onOpenHistory,
  onExport,
  onImport,
  isSaving,
  isRunning,
}) => {
  const [isEditingName, setIsEditingName] = useState(false);
  const [nameInput, setNameInput] = useState(workflow.name);

  const handleNameBlur = () => {
    setIsEditingName(false);
    if (nameInput.trim()) {
      onUpdateWorkflow({ name: nameInput.trim() });
    } else {
      setNameInput(workflow.name);
    }
  };

  return (
    <header className="h-14 border-b border-slate-800 bg-[#0f172a] px-4 flex items-center justify-between z-20 select-none">
      {/* Left: Brand & Workflow Name */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 bg-gradient-to-r from-sky-500 to-blue-600 px-2.5 py-1 rounded-lg text-white font-bold text-sm shadow-md shadow-sky-500/20">
          <Zap className="w-4 h-4 fill-white" />
          <span>LiteLLM ADK</span>
        </div>

        <div className="h-5 w-px bg-slate-700 mx-1" />

        {/* Workflow Title */}
        {isEditingName ? (
          <input
            type="text"
            value={nameInput}
            onChange={(e) => setNameInput(e.target.value)}
            onBlur={handleNameBlur}
            onKeyDown={(e) => e.key === "Enter" && handleNameBlur()}
            autoFocus
            className="bg-slate-800 border border-sky-500 rounded px-2 py-0.5 text-sm font-semibold text-white focus:outline-none"
          />
        ) : (
          <div
            onClick={() => {
              setNameInput(workflow.name);
              setIsEditingName(true);
            }}
            className="cursor-pointer font-semibold text-sm text-slate-200 hover:text-sky-400 transition-colors flex items-center gap-1.5"
            title="Click to rename workflow"
          >
            <span>{workflow.name}</span>
            <span className="text-xs text-slate-500 font-mono">v{workflow.version}</span>
          </div>
        )}

        {/* Status Badge */}
        <span
          className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full border ${
            workflow.active
              ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
              : "bg-amber-500/10 text-amber-400 border-amber-500/30"
          }`}
        >
          {workflow.active ? "Active" : "Draft"}
        </span>
      </div>

      {/* Right: Actions */}
      <div className="flex items-center gap-2">
        <button
          onClick={onOpenWorkflowsList}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-800/80 hover:bg-slate-700 text-xs font-medium text-slate-200 transition"
          title="Manage and switch workflows"
        >
          <FolderOpen className="w-3.5 h-3.5 text-slate-400" />
          <span>Workflows</span>
        </button>

        <button
          onClick={onOpenHistory}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-800/80 hover:bg-slate-700 text-xs font-medium text-slate-200 transition"
          title="View past execution history"
        >
          <History className="w-3.5 h-3.5 text-slate-400" />
          <span>History</span>
        </button>

        <div className="h-4 w-px bg-slate-800 mx-1" />

        <button
          onClick={onImport}
          className="p-1.5 rounded-lg border border-slate-700 bg-slate-800/80 hover:bg-slate-700 text-slate-300 transition"
          title="Import workflow JSON"
        >
          <Upload className="w-3.5 h-3.5" />
        </button>

        <button
          onClick={onExport}
          className="p-1.5 rounded-lg border border-slate-700 bg-slate-800/80 hover:bg-slate-700 text-slate-300 transition"
          title="Export workflow JSON"
        >
          <Download className="w-3.5 h-3.5" />
        </button>

        <div className="h-4 w-px bg-slate-800 mx-1" />

        <button
          onClick={onSave}
          disabled={isSaving}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 transition disabled:opacity-50"
        >
          <Save className="w-3.5 h-3.5 text-sky-400" />
          <span>{isSaving ? "Saving..." : "Save"}</span>
        </button>

        <button
          onClick={onTestRun}
          disabled={isRunning}
          className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-sky-500 hover:bg-sky-400 text-white text-xs font-semibold shadow-lg shadow-sky-500/25 transition disabled:opacity-50"
        >
          <Play className="w-3.5 h-3.5 fill-white" />
          <span>{isRunning ? "Running..." : "Test Run"}</span>
        </button>
      </div>
    </header>
  );
};
