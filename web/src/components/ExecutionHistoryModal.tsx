import React, { useEffect, useState } from "react";
import { X, History, CheckCircle2, AlertCircle, Clock, Loader2, ArrowRight } from "lucide-react";
import { api } from "../api/client";
import { ExecutionState } from "../types/workflow";

interface ExecutionHistoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  workflowId?: string;
  onSelectExecution: (exec: ExecutionState) => void;
}

export const ExecutionHistoryModal: React.FC<ExecutionHistoryModalProps> = ({
  isOpen,
  onClose,
  workflowId,
  onSelectExecution,
}) => {
  const [executions, setExecutions] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const loadExecutions = async () => {
    setLoading(true);
    try {
      const data = await api.getExecutions(workflowId);
      setExecutions(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadExecutions();
    }
  }, [isOpen, workflowId]);

  const handleRowClick = async (id: string) => {
    try {
      const exec = await api.getExecution(id);
      onSelectExecution(exec);
      onClose();
    } catch (err) {
      console.error(err);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-[#0f172a] border border-slate-800 rounded-2xl w-full max-w-3xl overflow-hidden shadow-2xl flex flex-col max-h-[85vh]">
        {/* Modal Header */}
        <div className="p-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <History className="w-5 h-5 text-sky-400" />
            <h3 className="font-semibold text-sm text-slate-100">Execution History</h3>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-200 p-1">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {loading ? (
            <div className="py-12 flex justify-center text-slate-500">
              <Loader2 className="w-6 h-6 animate-spin" />
            </div>
          ) : executions.length === 0 ? (
            <div className="py-12 text-center text-slate-500 text-xs">
              No executions recorded in database yet.
            </div>
          ) : (
            executions.map((ex) => (
              <div
                key={ex.id}
                onClick={() => handleRowClick(ex.id)}
                className="p-3 rounded-xl border border-slate-800 bg-[#131b2e] hover:bg-[#1a243d] hover:border-slate-700 cursor-pointer flex items-center justify-between transition group"
              >
                <div className="min-w-0 flex-1 pr-4">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-semibold text-slate-200 group-hover:text-sky-400 transition">
                      {ex.id}
                    </span>
                    <span
                      className={`text-[9px] uppercase font-bold px-1.5 py-0.5 rounded border ${
                        ex.status === "completed"
                          ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                          : ex.status === "running"
                          ? "bg-blue-500/10 text-blue-400 border-blue-500/30"
                          : ex.status === "waiting_for_human"
                          ? "bg-amber-500/10 text-amber-400 border-amber-500/30"
                          : "bg-rose-500/10 text-rose-400 border-rose-500/30"
                      }`}
                    >
                      {ex.status.replace(/_/g, " ")}
                    </span>
                  </div>
                  <span className="text-[10px] font-mono text-slate-500 mt-1 block">
                    Workflow: {ex.workflow_id} • Started: {new Date(ex.started_at).toLocaleString()}
                  </span>
                </div>

                <div className="flex items-center gap-4 text-xs font-mono text-slate-400">
                  <div className="flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5 text-slate-500" />
                    <span>{ex.duration_seconds ? ex.duration_seconds.toFixed(2) : "0.00"}s</span>
                  </div>
                  <ArrowRight className="w-4 h-4 text-slate-600 group-hover:text-sky-400 transition" />
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
