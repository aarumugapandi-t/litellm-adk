import React, { useEffect, useState } from "react";
import { X, Plus, Copy, Trash2, ArrowRight, Loader2, Workflow } from "lucide-react";
import { WorkflowDefinition } from "../types/workflow";
import { api } from "../api/client";

interface WorkflowListModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectWorkflow: (wf: WorkflowDefinition) => void;
  onCreateNew: () => void;
}

export const WorkflowListModal: React.FC<WorkflowListModalProps> = ({
  isOpen,
  onClose,
  onSelectWorkflow,
  onCreateNew,
}) => {
  const [workflows, setWorkflows] = useState<WorkflowDefinition[]>([]);
  const [loading, setLoading] = useState(false);

  const loadList = async () => {
    setLoading(true);
    try {
      const data = await api.getWorkflows();
      setWorkflows(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadList();
    }
  }, [isOpen]);

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("Are you sure you want to delete this workflow?")) return;
    try {
      await api.deleteWorkflow(id);
      setWorkflows((prev) => prev.filter((w) => w.id !== id));
    } catch (err) {
      console.error(err);
    }
  };

  const handleDuplicate = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const dup = await api.duplicateWorkflow(id);
      setWorkflows((prev) => [dup, ...prev]);
    } catch (err) {
      console.error(err);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-[#0f172a] border border-slate-800 rounded-2xl w-full max-w-2xl overflow-hidden shadow-2xl flex flex-col max-h-[85vh]">
        {/* Modal Header */}
        <div className="p-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Workflow className="w-5 h-5 text-sky-400" />
            <h3 className="font-semibold text-sm text-slate-100">Saved Workflows</h3>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={onCreateNew}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-500 hover:bg-sky-400 text-white font-medium text-xs shadow-md transition"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Create New</span>
            </button>
            <button onClick={onClose} className="text-slate-400 hover:text-slate-200 p-1">
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {loading ? (
            <div className="py-12 flex justify-center text-slate-500">
              <Loader2 className="w-6 h-6 animate-spin" />
            </div>
          ) : workflows.length === 0 ? (
            <div className="py-12 text-center text-slate-500 text-xs">
              No saved workflows found in SQLite database.
            </div>
          ) : (
            workflows.map((wf) => (
              <div
                key={wf.id}
                onClick={() => onSelectWorkflow(wf)}
                className="group p-3 rounded-xl border border-slate-800 bg-[#131b2e] hover:bg-[#1a243d] hover:border-slate-700 cursor-pointer flex items-center justify-between transition"
              >
                <div className="min-w-0 flex-1 pr-4">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm text-slate-100 group-hover:text-sky-400 transition truncate">
                      {wf.name}
                    </span>
                    <span
                      className={`text-[9px] uppercase font-bold px-1.5 py-0.5 rounded border ${
                        wf.active
                          ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                          : "bg-slate-800 text-slate-400 border-slate-700"
                      }`}
                    >
                      {wf.active ? "Active" : "Draft"}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 line-clamp-1 mt-0.5">
                    {wf.description || "No description provided."}
                  </p>
                  <span className="text-[10px] font-mono text-slate-500 mt-1 block">
                    ID: {wf.id} • {wf.nodes.length} nodes • v{wf.version}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={(e) => handleDuplicate(wf.id, e)}
                    className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition"
                    title="Duplicate workflow"
                  >
                    <Copy className="w-4 h-4" />
                  </button>

                  <button
                    onClick={(e) => handleDelete(wf.id, e)}
                    className="p-1.5 rounded-lg text-rose-400 hover:text-rose-300 hover:bg-rose-950/40 transition"
                    title="Delete workflow"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>

                  <ArrowRight className="w-4 h-4 text-slate-600 group-hover:text-sky-400 ml-1 transition" />
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
