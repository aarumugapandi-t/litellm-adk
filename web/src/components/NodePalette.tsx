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
  Globe,
  Calculator,
  ExternalLink,
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
  web_search_tool: Globe,
  calculator_tool: Calculator,
  http_tool: ExternalLink,
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
            placeholder="Search nodes (e.g. tool, agent)..."
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

          let categoryBadge = "";
          if (cat === "Triggers") categoryBadge = "Starts Workflow";
          else if (cat === "AI & Agents") categoryBadge = "Accepts Tools";
          else if (cat === "Tools") categoryBadge = "Attach to Agent";
          else if (cat === "Logic & Control") categoryBadge = "Branching";
          else if (cat === "Input & Output") categoryBadge = "Result";

          return (
            <div key={cat} className="space-y-1.5">
              <button
                onClick={() => toggleCategory(cat)}
                className="w-full flex items-center justify-between text-[11px] font-bold uppercase tracking-wider text-slate-400 hover:text-slate-200 py-1"
              >
                <span className="flex items-center gap-1.5">
                  <span>{cat}</span>
                  {categoryBadge && (
                    <span className="text-[9px] lowercase font-normal px-1.5 py-0.2 rounded bg-slate-800 text-slate-400 font-mono">
                      {categoryBadge}
                    </span>
                  )}
                </span>
                {isCollapsed ? <ChevronRight className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              </button>

              {!isCollapsed && (
                <div className="space-y-1.5">
                  {cat === "Tools" && (
                    <div className="p-2 rounded-lg bg-emerald-950/40 border border-emerald-800/50 text-[10px] space-y-0.5 mb-1">
                      <div className="font-semibold text-emerald-300 flex items-center gap-1">
                        <Wrench className="w-3 h-3 text-emerald-400" />
                        <span>Attachable Agent Tools</span>
                      </div>
                      <div className="text-slate-400 text-[9px] leading-tight">
                        Wire tool's <b className="text-emerald-300">[🧩 Tool Out]</b> to Agent's <b className="text-emerald-300">[🧩 Tools In]</b> socket.
                      </div>
                    </div>
                  )}

                  {catNodes.map((def) => {
                    const IconComp = ICON_MAP[def.type] || (cat === "Tools" ? Wrench : Bot);
                    const isTool = cat === "Tools" || def.type.includes("tool");
                    const isAgent = def.type === "agent";

                    return (
                      <div
                        key={def.type}
                        draggable
                        onDragStart={(e) => {
                          e.dataTransfer.setData("application/reactflow-type", def.type);
                          e.dataTransfer.effectAllowed = "move";
                        }}
                        onClick={() => onAddNode(def)}
                        className={`group flex items-start gap-2.5 p-2 rounded-lg border bg-[#131b2e] hover:bg-[#1a243d] cursor-grab active:cursor-grabbing transition shadow-sm ${
                          isTool
                            ? "border-emerald-900/50 hover:border-emerald-700/70"
                            : isAgent
                            ? "border-blue-900/50 hover:border-blue-700/70"
                            : "border-slate-800/80 hover:border-slate-700"
                        }`}
                        title="Drag onto canvas or click to add"
                      >
                        <div
                          className={`p-1.5 rounded-md transition mt-0.5 ${
                            isTool
                              ? "bg-emerald-950 text-emerald-400 group-hover:bg-emerald-500/20"
                              : isAgent
                              ? "bg-blue-950 text-blue-400 group-hover:bg-blue-500/20"
                              : "bg-slate-800 text-slate-300 group-hover:bg-sky-500/20 group-hover:text-sky-400"
                          }`}
                        >
                          <IconComp className="w-3.5 h-3.5" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-medium text-slate-200 truncate">{def.name}</span>
                            <div className="flex items-center gap-1">
                              {isTool && (
                                <span className="text-[9px] px-1 py-0.2 rounded bg-emerald-950 text-emerald-400 border border-emerald-800/40 font-mono">
                                  tool
                                </span>
                              )}
                              <Plus className="w-3 h-3 text-slate-500 group-hover:text-sky-400 opacity-0 group-hover:opacity-100 transition" />
                            </div>
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
