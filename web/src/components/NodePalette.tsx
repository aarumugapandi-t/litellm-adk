import React, { useState } from "react";
import {
  PlayCircle,
  Sparkles,
  Bot,
  Wrench,
  Database,
  Search as SearchIcon,
  GitBranch,
  Binary,
  UserCheck,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Plus,
} from "lucide-react";
import { NodeDefinition } from "../types/workflow";

interface NodePaletteProps {
  availableNodes: NodeDefinition[];
  onAddNode: (def: NodeDefinition) => void;
}

const ICON_MAP: Record<string, React.ElementType> = {
  manual_trigger: PlayCircle,
  webhook_trigger: PlayCircle,
  llm: Sparkles,
  agent: Bot,
  tool: Wrench,
  memory: Database,
  vector_search: SearchIcon,
  condition: GitBranch,
  transform: Binary,
  human: UserCheck,
  output: CheckCircle2,
};

export const NodePalette: React.FC<NodePaletteProps> = ({ availableNodes, onAddNode }) => {
  const [search, setSearch] = useState("");
  const [collapsedCategories, setCollapsedCategories] = useState<Record<string, boolean>>({});

  const toggleCategory = (cat: string) => {
    setCollapsedCategories((prev) => ({ ...prev, [cat]: !prev[cat] }));
  };

  const filteredNodes = availableNodes.filter(
    (n) =>
      n.name.toLowerCase().includes(search.toLowerCase()) ||
      n.description.toLowerCase().includes(search.toLowerCase()) ||
      n.category.toLowerCase().includes(search.toLowerCase())
  );

  // Group by category
  const categories = Array.from(new Set(availableNodes.map((n) => n.category)));

  return (
    <aside className="w-64 border-r border-slate-800 bg-[#0f172a] flex flex-col h-full z-10 select-none">
      {/* Search Header */}
      <div className="p-3 border-b border-slate-800">
        <div className="relative">
          <SearchIcon className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search nodes..."
            className="w-full bg-[#1e293b] border border-slate-700/60 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-sky-500"
          />
        </div>
      </div>

      {/* Categories & Node Cards */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {categories.map((cat) => {
          const catNodes = filteredNodes.filter((n) => n.category === cat);
          if (catNodes.length === 0) return null;

          const isCollapsed = collapsedCategories[cat];

          return (
            <div key={cat} className="space-y-1.5">
              <button
                onClick={() => toggleCategory(cat)}
                className="w-full flex items-center justify-between text-[11px] font-bold uppercase tracking-wider text-slate-400 hover:text-slate-200 py-1"
              >
                <span>{cat}</span>
                {isCollapsed ? <ChevronRight className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              </button>

              {!isCollapsed && (
                <div className="space-y-1.5">
                  {catNodes.map((def) => {
                    const IconComp = ICON_MAP[def.type] || Bot;
                    return (
                      <div
                        key={def.type}
                        draggable
                        onDragStart={(e) => {
                          e.dataTransfer.setData("application/reactflow-type", def.type);
                          e.dataTransfer.effectAllowed = "move";
                        }}
                        onClick={() => onAddNode(def)}
                        className="group flex items-start gap-2.5 p-2 rounded-lg border border-slate-800/80 bg-[#131b2e] hover:bg-[#1a243d] hover:border-slate-700 cursor-grab active:cursor-grabbing transition shadow-sm"
                        title="Drag onto canvas or click to add"
                      >
                        <div className="p-1.5 rounded-md bg-slate-800 group-hover:bg-sky-500/20 text-slate-300 group-hover:text-sky-400 transition mt-0.5">
                          <IconComp className="w-3.5 h-3.5" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-medium text-slate-200 truncate">{def.name}</span>
                            <Plus className="w-3 h-3 text-slate-500 group-hover:text-sky-400 opacity-0 group-hover:opacity-100 transition" />
                          </div>
                          <p className="text-[10px] text-slate-400 line-clamp-2 leading-tight mt-0.5">
                            {def.description}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </aside>
  );
};
