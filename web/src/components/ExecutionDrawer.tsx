import React, { useState } from "react";
import {
  ChevronUp,
  ChevronDown,
  Play,
  CheckCircle2,
  AlertCircle,
  Clock,
  Coins,
  Cpu,
  UserCheck,
  Check,
  X,
  Send,
} from "lucide-react";
import { ExecutionState } from "../types/workflow";

interface ExecutionDrawerProps {
  executionState: ExecutionState | null;
  isOpen: boolean;
  onToggle: () => void;
  onApprove: (approved: boolean, userInput?: string, selectedOption?: string) => Promise<void>;
  isSubmittingApproval: boolean;
}

export const ExecutionDrawer: React.FC<ExecutionDrawerProps> = ({
  executionState,
  isOpen,
  onToggle,
  onApprove,
  isSubmittingApproval,
}) => {
  const [approvalComment, setApprovalComment] = useState("");

  if (!executionState) return null;

  const isPaused = executionState.status === "waiting_for_human";
  const approval = executionState.pending_approval;

  const handleDecision = async (approved: boolean) => {
    await onApprove(approved, approvalComment);
    setApprovalComment("");
  };

  return (
    <div
      className={`fixed bottom-0 left-64 right-80 bg-[#0f172a] border-t border-slate-800 shadow-2xl z-30 transition-all duration-300 ${
        isOpen ? "h-72" : "h-10"
      }`}
    >
      {/* Header Bar */}
      <div
        onClick={onToggle}
        className="h-10 px-4 flex items-center justify-between cursor-pointer border-b border-slate-800/80 bg-[#131b2e] hover:bg-[#18223a] transition select-none"
      >
        <div className="flex items-center gap-3">
          <span className="text-xs font-semibold text-slate-300">Execution Monitor</span>
          <span className="text-[10px] font-mono text-slate-500">{executionState.execution_id}</span>

          <span
            className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-full border ${
              executionState.status === "completed"
                ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                : executionState.status === "running"
                ? "bg-blue-500/10 text-blue-400 border-blue-500/30 animate-pulse"
                : executionState.status === "waiting_for_human"
                ? "bg-amber-500/20 text-amber-400 border-amber-500/50"
                : "bg-rose-500/10 text-rose-400 border-rose-500/30"
            }`}
          >
            {executionState.status.replace(/_/g, " ")}
          </span>
        </div>

        <div className="flex items-center gap-4 text-xs text-slate-400">
          <div className="flex items-center gap-1 font-mono text-[11px]">
            <Clock className="w-3.5 h-3.5 text-slate-500" />
            <span>{executionState.total_duration ? executionState.total_duration.toFixed(2) : "0.00"}s</span>
          </div>

          <button className="text-slate-400 hover:text-slate-200">
            {isOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Drawer Body */}
      {isOpen && (
        <div className="h-[calc(100%-40px)] flex divide-x divide-slate-800 text-xs">
          {/* Left: Event Stepper Logs */}
          <div className="flex-1 overflow-y-auto p-3 space-y-2">
            <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-2">Step Trail</h4>
            {Object.values(executionState.node_records).length === 0 ? (
              <p className="text-slate-500 text-xs">Initializing execution runner...</p>
            ) : (
              Object.values(executionState.node_records).map((rec) => (
                <div
                  key={rec.id}
                  className="flex items-center justify-between p-2 rounded bg-slate-900 border border-slate-800"
                >
                  <div className="flex items-center gap-2">
                    {rec.status === "completed" && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />}
                    {rec.status === "running" && <Play className="w-3.5 h-3.5 text-blue-400 animate-pulse" />}
                    {rec.status === "waiting_for_human" && <UserCheck className="w-3.5 h-3.5 text-amber-400" />}
                    {rec.status === "failed" && <AlertCircle className="w-3.5 h-3.5 text-rose-400" />}
                    <span className="font-medium text-slate-200">{rec.node_id}</span>
                    <span className="text-[10px] text-slate-500 font-mono">({rec.node_type})</span>
                  </div>

                  <div className="flex items-center gap-3 font-mono text-[10px] text-slate-400">
                    {rec.duration !== undefined && <span>{rec.duration.toFixed(3)}s</span>}
                    <span className="uppercase">{rec.status}</span>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Right: Human Approval Dialog or Output Summary */}
          <div className="w-96 p-3 overflow-y-auto bg-[#111827]">
            {isPaused && approval ? (
              <div className="space-y-3 bg-amber-950/20 border border-amber-500/40 rounded-xl p-3.5">
                <div className="flex items-center gap-2 text-amber-400 font-semibold text-xs">
                  <UserCheck className="w-4 h-4" />
                  <span>Human Approval Required</span>
                </div>

                <p className="text-slate-200 text-xs leading-relaxed font-medium">
                  {approval.message || "Please review and confirm whether to proceed."}
                </p>

                <div className="space-y-1">
                  <label className="text-[10px] font-medium text-slate-400">Decision Notes (Optional):</label>
                  <input
                    type="text"
                    value={approvalComment}
                    onChange={(e) => setApprovalComment(e.target.value)}
                    placeholder="Enter remarks or approval reason..."
                    className="w-full bg-[#1e293b] border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-amber-500"
                  />
                </div>

                <div className="flex gap-2 pt-1">
                  <button
                    onClick={() => handleDecision(true)}
                    disabled={isSubmittingApproval}
                    className="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs transition shadow-md shadow-emerald-600/20 disabled:opacity-50"
                  >
                    <Check className="w-3.5 h-3.5" />
                    <span>Approve</span>
                  </button>

                  <button
                    onClick={() => handleDecision(false)}
                    disabled={isSubmittingApproval}
                    className="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-semibold text-xs transition shadow-md shadow-rose-600/20 disabled:opacity-50"
                  >
                    <X className="w-3.5 h-3.5" />
                    <span>Reject</span>
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Execution Outputs</h4>
                {Object.keys(executionState.node_outputs).length === 0 ? (
                  <p className="text-slate-500 text-xs">No output records captured yet.</p>
                ) : (
                  <pre className="p-2.5 rounded bg-slate-950 border border-slate-800 text-[10px] font-mono text-slate-300 overflow-x-auto max-h-52">
                    {JSON.stringify(executionState.node_outputs, null, 2)}
                  </pre>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
