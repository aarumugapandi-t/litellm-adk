import React, { useState, useRef, useEffect } from "react";
import { Sparkles, Search, ChevronRight, Check, X, Tag } from "lucide-react";
import { VariableItem } from "../utils/variables";

interface VariablePickerProps {
  variables: VariableItem[];
  onInsertVariable: (varKey: string) => void;
  currentValue?: string;
}

export const VariablePicker: React.FC<VariablePickerProps> = ({
  variables,
  onInsertVariable,
  currentValue = "",
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState("");
  const popoverRef = useRef<HTMLDivElement>(null);

  // Close when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (popoverRef.current && !popoverRef.current.contains(event.target as HTMLElement)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  const filtered = variables.filter(
    (v) =>
      v.key.toLowerCase().includes(search.toLowerCase()) ||
      v.label.toLowerCase().includes(search.toLowerCase()) ||
      v.description.toLowerCase().includes(search.toLowerCase())
  );

  // Extract referenced variables from currentValue for abstracted pill display
  const referencedVars: string[] = [];
  const matches = currentValue.matchAll(/\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}/g);
  for (const m of matches) {
    if (!referencedVars.includes(m[1])) {
      referencedVars.push(m[1]);
    }
  }

  const handleSelect = (key: string) => {
    onInsertVariable(`{{ ${key} }}`);
    setIsOpen(false);
    setSearch("");
  };

  return (
    <div className="relative inline-block" ref={popoverRef}>
      {/* Insert Variable Trigger Button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-md bg-sky-950/70 border border-sky-600/50 text-sky-300 hover:bg-sky-900/80 transition"
        title="Insert an upstream output or workflow variable"
      >
        <Sparkles className="w-3 h-3 text-sky-400" />
        <span>+ Variable</span>
      </button>

      {/* Popover Menu */}
      {isOpen && (
        <div className="absolute right-0 mt-1 w-72 bg-[#0f172a] border border-slate-700/80 rounded-xl shadow-2xl z-50 overflow-hidden select-none animate-in fade-in duration-100">
          {/* Search Header */}
          <div className="p-2 border-b border-slate-800 bg-slate-900/60">
            <div className="relative">
              <Search className="w-3 h-3 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                autoFocus
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search variables (e.g. output, query)..."
                className="w-full bg-[#1e293b] border border-slate-700 rounded-lg pl-7 pr-2 py-1 text-xs text-slate-100 focus:outline-none focus:border-sky-500"
              />
            </div>
          </div>

          {/* Variables List */}
          <div className="max-h-64 overflow-y-auto p-1.5 space-y-1">
            {filtered.length === 0 ? (
              <div className="p-3 text-center text-xs text-slate-500">
                No variables matching "{search}"
              </div>
            ) : (
              filtered.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => handleSelect(item.key)}
                  className="w-full text-left p-2 rounded-lg hover:bg-slate-800/80 transition group flex flex-col gap-0.5"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-200 group-hover:text-sky-300 font-mono">
                      {item.key}
                    </span>
                    <span
                      className={`text-[9px] px-1.5 py-0.2 rounded font-medium ${
                        item.category === "Trigger"
                          ? "bg-amber-950/60 text-amber-300 border border-amber-800/40"
                          : item.category === "Workflow Variable"
                          ? "bg-violet-950/60 text-violet-300 border border-violet-800/40"
                          : "bg-emerald-950/60 text-emerald-300 border border-emerald-800/40"
                      }`}
                    >
                      {item.category}
                    </span>
                  </div>
                  <span className="text-[10px] text-slate-400 line-clamp-1">
                    {item.description || item.label}
                  </span>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
};
