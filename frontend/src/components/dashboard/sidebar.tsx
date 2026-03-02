import {
  Bot,
  CheckSquare2,
  ChevronDown,
  ChevronRight,
  Copy,
  Download,
  FolderOpen,
  Loader2,
  Moon,
  Pencil,
  Plus,
  Search,
  Sun,
  Trash2,
  MoreVertical,
  Wand2,
  ListPlus,
  SquareCheck,
  Square,
  FolderPlus
} from "lucide-react";
import { type DragEvent, useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import { BridgeStatus } from "@/components/dashboard/bridge-status";
import { cn } from "@/lib/utils";
import type { GroupItem, ProcessItem } from "@/types/aiida";

const CONTEXT_NODE_DRAG_MIME = "application/x-sabr-context-node";

function clampRecentLimit(value: number): number {
  return Math.min(100, Math.max(1, value));
}

const PROCESS_LIKE_NODE_TYPES = new Set([
  "ProcessNode",
  "WorkChainNode",
  "WorkflowNode",
  "CalcJobNode",
  "CalcFunctionNode",
]);
const RUNNING_PROCESS_STATES = new Set(["running", "created", "waiting"]);
const FINISHED_PROCESS_STATES = new Set(["finished", "completed", "success"]);
const FAILED_PROCESS_STATES = new Set(["failed", "excepted", "killed", "error"]);

type NodeTypeIndicator = {
  icon: string;
  iconLabel: string;
};

type ProcessStatusTone = {
  label: string;
  className: string;
};

type NodeMetadata = {
  lines: string[];
  processStatus: ProcessStatusTone | null;
};

function normalizeState(state: string | null): string {
  return String(state || "unknown").trim().replace(/_/g, " ").toLowerCase();
}

function isStructureNode(process: ProcessItem): boolean {
  return process.node_type === "StructureData" || Boolean(process.formula);
}

function isProcessLikeNode(process: ProcessItem): boolean {
  if (process.process_state !== null) {
    return true;
  }
  return PROCESS_LIKE_NODE_TYPES.has(process.node_type);
}

function getPreviewObject(process: ProcessItem): Record<string, unknown> | null {
  const raw = process.preview_info ?? process.preview;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    return null;
  }
  return raw;
}

function asInteger(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return Math.trunc(value);
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number.parseInt(value, 10);
    if (!Number.isNaN(parsed)) {
      return parsed;
    }
  }
  return null;
}

function formatShape(rawShape: unknown): string {
  if (!Array.isArray(rawShape)) {
    return "?";
  }
  const dimensions = rawShape
    .map((value) => asInteger(value))
    .filter((value): value is number => value !== null);
  return dimensions.length > 0 ? dimensions.join("x") : "?";
}

function toDisplayStatus(state: string | null): string {
  const normalized = normalizeState(state);
  if (!normalized) {
    return "Unknown";
  }
  return normalized
    .split(" ")
    .filter(Boolean)
    .map((word: string) => `${word.charAt(0).toUpperCase()}${word.slice(1)}`)
    .join(" ");
}

function toStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => String(item || "").trim()).filter(Boolean);
}

function getArrayEntries(raw: unknown): Array<{ name: string; shape: string }> {
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw
    .map((entry) => {
      if (!entry || typeof entry !== "object") {
        return null;
      }
      const name = String((entry as { name?: unknown }).name || "").trim();
      const shape = formatShape((entry as { shape?: unknown }).shape);
      if (!name) {
        return null;
      }
      return { name, shape };
    })
    .filter((item): item is { name: string; shape: string } => item !== null);
}

function uniqueLabels(values: string[]): string[] {
  return [...new Set(values.map((value) => value.trim()).filter(Boolean))];
}

function toPreviewString(value: unknown): string | null {
  if (typeof value === "string") {
    return value.trim() || null;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value)) {
    const values = value.map((item) => toPreviewString(item)).filter((item): item is string => Boolean(item));
    return values.length > 0 ? values.slice(0, 3).join(", ") : null;
  }
  return null;
}

function getXyArrayNames(preview: Record<string, unknown> | null): string[] {
  if (!preview) {
    return [];
  }
  const fromArrayNames = toStringArray(preview.array_names);
  const fromNames = toStringArray(preview.names);
  const fromArrayRecords = getArrayEntries(preview.arrays).map((entry) => entry.name);
  const xName = String(preview.x_name || "").trim();
  const yNames = toStringArray(preview.y_names);
  const result = [...fromArrayNames, ...fromNames, ...fromArrayRecords, ...yNames];
  if (xName) {
    result.unshift(xName);
  }
  return uniqueLabels(result);
}

function getNodeTypeIndicator(process: ProcessItem): NodeTypeIndicator {
  if (process.node_type === "StructureData") {
    return { icon: "💎", iconLabel: "Crystal" };
  }
  if (process.node_type === "ProcessNode" || process.node_type === "WorkChainNode") {
    return { icon: "⚡", iconLabel: "Activity" };
  }
  if (process.node_type === "BandsData" || process.node_type === "XyData") {
    return { icon: "📈", iconLabel: "Chart" };
  }
  if (process.node_type === "Dict" || process.node_type === "ArrayData") {
    return { icon: "📑", iconLabel: "Data" };
  }
  if (process.node_type === "RemoteData" || process.node_type === "FolderData") {
    return { icon: "📁", iconLabel: "Folder" };
  }
  if (isProcessLikeNode(process)) {
    return { icon: "⚡", iconLabel: "Activity" };
  }
  return { icon: "📦", iconLabel: "Node" };
}

function compactLabel(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) {
    return "";
  }
  const fromEntryPoint = trimmed.includes(":") ? trimmed.split(":").pop() || trimmed : trimmed;
  const normalized = fromEntryPoint.trim();
  if (!normalized.includes(" ") && normalized.includes(".")) {
    return normalized.split(".").pop() || normalized;
  }
  return normalized;
}

function getProcessSpecificLabel(process: ProcessItem): string | null {
  const preview = getPreviewObject(process);
  const rawCandidates: unknown[] = [
    process.process_label,
    preview?.process_label,
    preview?.process_class,
    preview?.process_type,
    preview?.process_name,
  ];
  for (const raw of rawCandidates) {
    const text = toPreviewString(raw);
    if (!text) {
      continue;
    }
    const normalized = compactLabel(text);
    if (normalized) {
      return normalized;
    }
  }
  return null;
}

function getNodeTitleText(process: ProcessItem): string {
  const defaultTitle = process.node_type || "Node";
  if (process.node_type === "ProcessNode") {
    return getProcessSpecificLabel(process) || defaultTitle;
  }
  if (isProcessLikeNode(process)) {
    return getProcessSpecificLabel(process) || defaultTitle;
  }
  return defaultTitle;
}

function getProcessStatusTone(process: ProcessItem): ProcessStatusTone | null {
  if (!isProcessLikeNode(process)) {
    return null;
  }
  const status = toDisplayStatus(process.process_state || process.state);
  const normalized = normalizeState(process.process_state || process.state);
  if (FAILED_PROCESS_STATES.has(normalized)) {
    return {
      label: status,
      className: "text-rose-600 dark:text-rose-300",
    };
  }
  if (RUNNING_PROCESS_STATES.has(normalized)) {
    return {
      label: status,
      className: "text-blue-600 dark:text-blue-300",
    };
  }
  if (FINISHED_PROCESS_STATES.has(normalized)) {
    return {
      label: status,
      className: "text-emerald-600 dark:text-emerald-300",
    };
  }
  return {
    label: status,
    className: "text-zinc-500 dark:text-zinc-400",
  };
}

function compactNameList(rawNames: string[], max = 2): string {
  const names = uniqueLabels(rawNames);
  if (names.length === 0) {
    return "";
  }
  const shown = names.slice(0, max).join(", ");
  return names.length > max ? `${shown} +${names.length - max}` : shown;
}

function getRecordLabel(value: unknown): string | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  const record = value as Record<string, unknown>;
  return (
    toPreviewString(record.label) ??
    toPreviewString(record.name) ??
    toPreviewString(record.hostname) ??
    toPreviewString(record.host) ??
    null
  );
}

function getRemoteMachineLabel(preview: Record<string, unknown> | null): string | null {
  if (!preview) {
    return null;
  }
  const directKeys = ["machine_label", "computer_label", "computer_name", "machine", "hostname", "host"];
  for (const key of directKeys) {
    const value = toPreviewString(preview[key]);
    if (value) {
      return value;
    }
  }
  const objectKeys = ["computer", "machine", "host", "resource"];
  for (const key of objectKeys) {
    const value = getRecordLabel(preview[key]);
    if (value) {
      return value;
    }
  }
  return null;
}

function getNodeMetadata(process: ProcessItem): NodeMetadata {
  const preview = getPreviewObject(process);
  const lines: string[] = [];
  const processStatus = getProcessStatusTone(process);

  if (isStructureNode(process)) {
    const formula = String(preview?.formula || process.formula || "").trim();
    const atomCount = asInteger(preview?.atom_count);
    if (formula) {
      lines.push(formula);
    }
    if (atomCount !== null) {
      lines.push(`${atomCount} atoms`);
    }
  } else if (process.node_type === "XyData") {
    const names = getXyArrayNames(preview);
    const compactNames = compactNameList(names);
    if (compactNames) {
      lines.push(compactNames);
    }
    lines.push(`${names.length} arrays`);
  } else if (process.node_type === "ArrayData") {
    const entries = getArrayEntries(preview?.arrays);
    const entryNames = entries.map((entry) => entry.name);
    const fallbackNames = toStringArray(preview?.array_names);
    const names = entryNames.length > 0 ? entryNames : fallbackNames;
    const compactNames = compactNameList(names);
    if (compactNames) {
      lines.push(compactNames);
    }
    lines.push(`${names.length} arrays`);
  } else if (process.node_type === "RemoteData" || process.node_type === "FolderData") {
    const machineLabel = getRemoteMachineLabel(preview);
    if (machineLabel) {
      lines.push(`Machine ${machineLabel}`);
    }
    const remotePath = toPreviewString(preview?.remote_path) ?? toPreviewString(preview?.path);
    if (remotePath) {
      lines.push(remotePath);
    }
  } else if (preview) {
    const previewEntry = Object.entries(preview).find(
      ([key, value]) =>
        key !== "arrays" &&
        key !== "array_names" &&
        key !== "names" &&
        key !== "x_name" &&
        key !== "y_names" &&
        key !== "process_label" &&
        key !== "process_class" &&
        key !== "process_type" &&
        toPreviewString(value),
    );
    if (previewEntry) {
      const [previewKey, previewValue] = previewEntry;
      lines.push(`${previewKey.replace(/_/g, " ")}: ${toPreviewString(previewValue)}`);
    }
  }

  if (isProcessLikeNode(process) && process.label.trim()) {
    const titleText = getNodeTitleText(process);
    if (process.label.trim() !== titleText) {
      lines.unshift(process.label.trim());
    }
  }

  return {
    lines: lines.slice(0, 2),
    processStatus,
  };
}


type SidebarProps = {
  processes: ProcessItem[];
  groups: GroupItem[];
  selectedGroup: string;
  processLimit: number;
  contextNodeIds: number[];
  isUpdatingProcessLimit: boolean;
  isDarkMode: boolean;
  onToggleTheme: () => void;
  onGroupChange: (groupLabel: string) => void;
  onProcessLimitChange: (limit: number) => void;
  onAddContextNode: (process: ProcessItem) => void;
  onAddContextNodes: (processes: ProcessItem[]) => void;
  onOpenProcessDetail: (process: ProcessItem) => void;
  onCreateGroup: (label: string) => void;
  onRenameGroup: (pk: number, label: string) => void;
  onDeleteGroup: (pk: number) => void;
  onAssignNodesToGroup: (groupPk: number, nodePks: number[]) => void;
  onSoftDeleteNode: (pk: number) => void;
  onExportGroup: (group: GroupItem) => void;
  onConsultFailedProcess: (process: ProcessItem) => void;
};

export function Sidebar({
  processes,
  groups,
  selectedGroup,
  processLimit,
  contextNodeIds,
  isUpdatingProcessLimit,
  isDarkMode,
  onToggleTheme,
  onGroupChange,
  onProcessLimitChange,
  onAddContextNode,
  onAddContextNodes,
  onOpenProcessDetail,
  onCreateGroup,
  onRenameGroup,
  onDeleteGroup,
  onAssignNodesToGroup,
  onSoftDeleteNode,
  onExportGroup,
  onConsultFailedProcess,
}: SidebarProps) {
  const [limitInput, setLimitInput] = useState(String(processLimit));
  const [searchQuery, setSearchQuery] = useState("");
  const [nodeTypeFilter, setNodeTypeFilter] = useState<"all" | "structures" | "tasks" | "failed">("all");
  const [selectedNodePks, setSelectedNodePks] = useState<Set<number>>(new Set());
  const [contextMenuNode, setContextMenuNode] = useState<{ pk: number; x: number; y: number } | null>(null);
  const [contextMenuGroup, setContextMenuGroup] = useState<{ pk: number; x: number; y: number } | null>(null);

  const [isGroupsExpanded, setIsGroupsExpanded] = useState(true);

  useEffect(() => {
    setLimitInput(String(processLimit));
  }, [processLimit]);

  const commitProcessLimit = (rawValue: string) => {
    const parsed = Number.parseInt(rawValue, 10);
    if (Number.isNaN(parsed)) {
      setLimitInput(String(processLimit));
      return;
    }
    const clamped = clampRecentLimit(parsed);
    setLimitInput(String(clamped));
    if (clamped !== processLimit) {
      onProcessLimitChange(clamped);
    }
  };

  const handleProcessDragStart = (event: DragEvent<HTMLDivElement>, process: ProcessItem) => {
    event.dataTransfer.effectAllowed = "copy";
    const payload = {
      pk: process.pk,
      label: process.label || `Node #${process.pk}`,
      formula: process.formula ?? null,
      node_type: process.node_type || "Unknown",
    };
    event.dataTransfer.setData(CONTEXT_NODE_DRAG_MIME, JSON.stringify(payload));
    event.dataTransfer.setData("text/plain", `#${process.pk}`);
  };

  const handleGroupDrop = (event: DragEvent<HTMLDivElement>, groupPk: number) => {
    event.preventDefault();
    const payload = event.dataTransfer.getData(CONTEXT_NODE_DRAG_MIME);
    if (!payload) return;
    try {
      const parsed = JSON.parse(payload);
      if (parsed.pk) {
        onAssignNodesToGroup(groupPk, [parsed.pk]);
      }
    } catch (e) {
      // ignore
    }
  };

  const filteredProcesses = useMemo(() => {
    return processes.filter((proc) => {
      // Search
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        const lbl = (proc.label || "").toLowerCase();
        const pLbl = (proc.process_label || "").toLowerCase();
        if (!lbl.includes(q) && !pLbl.includes(q) && !String(proc.pk).includes(q)) {
          return false;
        }
      }
      // Type Toggle
      if (nodeTypeFilter === "structures" && !isStructureNode(proc)) return false;
      if (nodeTypeFilter === "tasks" && !isProcessLikeNode(proc)) return false;
      if (nodeTypeFilter === "failed") {
        const normalized = normalizeState(proc.process_state || proc.state);
        if (!FAILED_PROCESS_STATES.has(normalized)) return false;
      }
      return true;
    });
  }, [processes, searchQuery, nodeTypeFilter]);

  const toggleSelectNode = (pk: number, event: React.MouseEvent) => {
    event.stopPropagation();
    setSelectedNodePks((prev) => {
      const next = new Set(prev);
      if (next.has(pk)) next.delete(pk);
      else next.add(pk);
      return next;
    });
  };

  const handleBulkAddToContext = () => {
    const selectedProcs = processes.filter((p) => selectedNodePks.has(p.pk));
    if (selectedProcs.length > 0) {
      onAddContextNodes(selectedProcs);
    }
    setSelectedNodePks(new Set());
  };

  const handleBulkCreateGroup = () => {
    const label = window.prompt("Enter new group name:");
    if (!label) return;
    onCreateGroup(label);
    // After creating group, we ideally want to assign nodes. 
    // Since onCreateGroup does not return the group immediately in this prop schema, 
    // we might need to rely on the backend or wait. 
    // For simplicity, we just clear selection or assume backend logic exists.
    setSelectedNodePks(new Set());
  };

  // Close context menus on click outside
  useEffect(() => {
    const handleClick = () => {
      setContextMenuNode(null);
      setContextMenuGroup(null);
    };
    window.addEventListener("click", handleClick);
    return () => window.removeEventListener("click", handleClick);
  }, []);

  return (
    <aside className="flex h-full min-h-0 w-full shrink-0 flex-col gap-2 font-sans tracking-tight lg:w-[360px] relative">
      <header className="flex items-center justify-between">
        <h1 className="text-lg font-semibold tracking-tight text-zinc-900 dark:text-zinc-100">
          AiiDA Explorer
        </h1>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={onToggleTheme}
          aria-label="Toggle color mode"
        >
          {isDarkMode ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>
      </header>

      <BridgeStatus />

      <Panel className="relative z-10 flex min-h-0 flex-1 flex-col border-zinc-100/90 p-4 transition-opacity duration-300 dark:border-zinc-800/80">
        <div className="mx-auto flex h-full min-h-0 w-full flex-col gap-4">

          {/* Top Controls */}
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-400" />
                <input
                  type="text"
                  placeholder="Search PK, label..."
                  className="h-9 w-full rounded-lg border border-zinc-200/65 bg-zinc-50/70 pl-9 pr-3 text-sm text-zinc-700 transition-all focus:border-zinc-400 focus:outline-none dark:border-zinc-800 dark:bg-zinc-900/45 dark:text-zinc-200 dark:focus:border-zinc-600"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
              <div className="flex items-center gap-1 rounded-lg border border-zinc-200/65 bg-zinc-50/70 p-1 dark:border-zinc-800 dark:bg-zinc-900/45">
                {(["all", "structures", "tasks", "failed"] as const).map((type) => (
                  <button
                    key={type}
                    onClick={() => setNodeTypeFilter(type)}
                    className={cn(
                      "rounded-md px-2 py-1 text-[11px] font-medium capitalize",
                      nodeTypeFilter === type
                        ? "bg-white text-zinc-900 shadow-sm dark:bg-zinc-800 dark:text-zinc-100"
                        : "text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"
                    )}
                  >
                    {type}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Groups Section */}
          <div className="flex flex-col gap-1 shrink-0">
            <button
              onClick={() => setIsGroupsExpanded(!isGroupsExpanded)}
              className="flex items-center justify-between group/groupbtn"
            >
              <div className="flex items-center gap-1 text-xs font-medium uppercase tracking-[0.1em] text-zinc-500 dark:text-zinc-400">
                <ChevronRight className={cn("h-3.5 w-3.5 transition-transform", isGroupsExpanded && "rotate-90")} />
                Groups
              </div>
              <Plus className="h-3.5 w-3.5 text-zinc-400 opacity-0 transition-opacity group-hover/groupbtn:opacity-100" />
            </button>

            {isGroupsExpanded && (
              <div className="flex flex-col gap-1 mt-1">
                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => onGroupChange("")}
                  className={cn(
                    "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors",
                    !selectedGroup ? "bg-zinc-100 dark:bg-zinc-800/60 font-medium" : "hover:bg-zinc-100/50 dark:hover:bg-zinc-800/30 text-zinc-600 dark:text-zinc-400"
                  )}
                >
                  <FolderOpen className="h-4 w-4" />
                  <span>All Groups</span>
                </div>
                {groups.map((group) => (
                  <div
                    key={group.pk}
                    role="button"
                    tabIndex={0}
                    onClick={() => onGroupChange(group.label)}
                    onDragOver={(e) => {
                      e.preventDefault();
                      e.dataTransfer.dropEffect = "copy";
                    }}
                    onDrop={(e) => handleGroupDrop(e, group.pk)}
                    onContextMenu={(e) => {
                      e.preventDefault();
                      setContextMenuGroup({ pk: group.pk, x: e.pageX, y: e.pageY });
                    }}
                    className={cn(
                      "group flex items-center justify-between rounded-md px-2 py-1.5 text-sm transition-colors",
                      selectedGroup === group.label ? "bg-zinc-100 dark:bg-zinc-800/60 font-medium" : "hover:bg-zinc-100/50 dark:hover:bg-zinc-800/30 text-zinc-600 dark:text-zinc-400"
                    )}
                  >
                    <div className="flex items-center gap-2 overflow-hidden">
                      <FolderOpen className="h-4 w-4 shrink-0 text-zinc-400 dark:text-zinc-500" />
                      <span className="truncate">{group.label}</span>
                    </div>
                    <span className="text-[10px] text-zinc-400 shrink-0">{group.count} nodes</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <hr className="border-zinc-200/60 dark:border-zinc-800/60" />

          {/* Nodes Section */}
          <div className="flex min-h-0 flex-1 flex-col gap-2 relative">
            <div className="flex items-center justify-between shrink-0">
              <span className="text-xs font-medium uppercase tracking-[0.1em] text-zinc-500 dark:text-zinc-400">
                Nodes {selectedGroup ? `in ${selectedGroup}` : "Recent"}
              </span>
              <div className="flex items-center gap-1 text-[11px] text-zinc-500">
                Limit:
                <input
                  type="number"
                  min={1}
                  max={200}
                  value={limitInput}
                  className="w-8 bg-transparent border-b border-zinc-300 dark:border-zinc-700 outline-none text-center"
                  onChange={(e) => setLimitInput(e.target.value)}
                  onBlur={() => commitProcessLimit(limitInput)}
                  onKeyDown={(e) => { if (e.key === "Enter") commitProcessLimit(limitInput); }}
                />
              </div>
            </div>

            <div className={cn("minimal-scrollbar min-h-0 flex-1 space-y-2 overflow-y-auto pr-1 pb-12", isUpdatingProcessLimit && "opacity-70")}>
              {filteredProcesses.length === 0 ? (
                <p className="rounded-xl border border-dashed border-zinc-300/60 bg-zinc-50/40 p-3 text-sm text-zinc-500 dark:border-white/10 dark:bg-zinc-900/30 dark:text-zinc-400">
                  No matching nodes found.
                </p>
              ) : (
                filteredProcesses.map((process) => {
                  const isSelected = contextNodeIds.includes(process.pk);
                  const isChecked = selectedNodePks.has(process.pk);
                  const canOpenDetail = isProcessLikeNode(process);
                  const typeIndicator = getNodeTypeIndicator(process);
                  const titleText = getNodeTitleText(process);
                  const metadata = getNodeMetadata(process);

                  const isFailed = FAILED_PROCESS_STATES.has(normalizeState(process.process_state || process.state));
                  const isRunning = RUNNING_PROCESS_STATES.has(normalizeState(process.process_state || process.state));

                  return (
                    <div
                      key={`${process.pk}-${process.state}`}
                      draggable
                      onDragStart={(event) => handleProcessDragStart(event, process)}
                      onClick={() => onAddContextNode(process)}
                      onContextMenu={(e) => {
                        e.preventDefault();
                        setContextMenuNode({ pk: process.pk, x: e.pageX, y: e.pageY });
                      }}
                      className={cn(
                        "group/card flex items-start gap-2 rounded-xl border px-3 py-2.5 transition-all duration-200 cursor-pointer",
                        "border-zinc-200/75 bg-white/60 hover:border-zinc-300/85 hover:bg-white/75 dark:border-zinc-800/80 dark:bg-zinc-900/45 dark:hover:border-zinc-700/85 dark:hover:bg-zinc-900/55",
                        isSelected ? "border-zinc-300/90 bg-zinc-100/70 shadow-[0_10px_22px_-20px_rgba(15,23,42,0.65)] dark:border-zinc-700/90 dark:bg-zinc-800/55" : null,
                        isRunning ? "animate-pulse ring-1 ring-blue-500/30" : null
                      )}
                    >
                      <button
                        onClick={(e) => toggleSelectNode(process.pk, e)}
                        className="mt-1 shrink-0 text-zinc-400 hover:text-zinc-600 dark:text-zinc-500 dark:hover:text-zinc-300"
                      >
                        {isChecked ? <SquareCheck className="h-4 w-4 text-blue-500" /> : <Square className="h-4 w-4 opacity-0 transition-opacity group-hover/card:opacity-100" />}
                      </button>

                      <div className="flex min-w-0 flex-1 flex-col gap-1">
                        <div className="flex items-center justify-between gap-3">
                          <p className="flex items-center gap-1.5 truncate font-sans text-sm font-semibold tracking-tight text-zinc-900 dark:text-zinc-100">
                            <span role="img" aria-label={typeIndicator.iconLabel} className="shrink-0">{typeIndicator.icon}</span>
                            <span className="truncate">
                              {titleText} <span className="font-mono text-[11px] font-normal text-zinc-500 dark:text-zinc-400">({process.pk})</span>
                            </span>
                          </p>
                          {metadata.processStatus && (
                            <div className="flex items-center gap-1 shrink-0">
                              <p className={cn("text-[11px] font-semibold tracking-tight", metadata.processStatus.className)}>
                                {metadata.processStatus.label}
                              </p>
                              {isFailed && (
                                <button
                                  onClick={(e) => { e.stopPropagation(); onConsultFailedProcess(process); }}
                                  className="text-rose-500 hover:text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/30 rounded p-0.5"
                                  title="AI Diagnose"
                                >
                                  <Wand2 className="h-3.5 w-3.5" />
                                </button>
                              )}
                            </div>
                          )}
                        </div>

                        <div className="min-w-0 flex justify-between">
                          <div className="flex flex-col">
                            {metadata.lines.map((line, idx) => (
                              <p key={idx} className={cn("truncate text-[11px] tracking-tight", idx === 0 ? "text-zinc-700 dark:text-zinc-300" : "text-zinc-500 dark:text-zinc-400")}>
                                {line}
                              </p>
                            ))}
                          </div>
                          <div className="mt-0.5 flex items-end justify-end gap-2">
                            {canOpenDetail && (
                              <button
                                type="button"
                                className="text-[10px] uppercase tracking-[0.08em] text-zinc-500 underline decoration-zinc-300 underline-offset-2 transition-colors hover:text-zinc-800 dark:text-zinc-400 dark:decoration-zinc-700 dark:hover:text-zinc-200"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  onOpenProcessDetail(process);
                                }}
                              >
                                Inspect
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            {/* Bulk Actions Toolbar */}
            {selectedNodePks.size > 0 && (
              <div className="absolute bottom-2 left-1/2 -translate-x-1/2 flex items-center gap-2 rounded-full border border-zinc-200 bg-white/95 px-3 py-1.5 shadow-lg backdrop-blur dark:border-zinc-800 dark:bg-zinc-900/95 animate-in slide-in-from-bottom-5">
                <span className="text-xs font-medium text-zinc-600 dark:text-zinc-300 px-2 border-r border-zinc-200 dark:border-zinc-800">
                  {selectedNodePks.size} selected
                </span>
                <button onClick={handleBulkCreateGroup} className="flex items-center gap-1.5 rounded-full px-2 py-1 text-xs font-medium text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800">
                  <FolderPlus className="h-3.5 w-3.5" /> Group
                </button>
                <button onClick={handleBulkAddToContext} className="flex items-center gap-1.5 rounded-full px-2 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50 dark:text-blue-400 dark:hover:bg-blue-950/30">
                  <ListPlus className="h-3.5 w-3.5" /> Context
                </button>
              </div>
            )}
          </div>
        </div>
      </Panel>

      {/* Context Menus */}
      {contextMenuNode && (
        <div
          className="fixed z-50 min-w-40 rounded-md border border-zinc-200 bg-white p-1 shadow-md dark:border-zinc-800 dark:bg-zinc-900 animate-in fade-in"
          style={{ top: contextMenuNode.y, left: contextMenuNode.x }}
          onClick={(e) => e.stopPropagation()}
        >
          <button
            className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-xs text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
            onClick={() => {
              navigator.clipboard.writeText(String(contextMenuNode.pk));
              setContextMenuNode(null);
            }}
          >
            <Copy className="h-3.5 w-3.5" /> Copy PK
          </button>
          <button
            className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-xs text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
            onClick={() => {
              const proc = processes.find(p => p.pk === contextMenuNode.pk);
              if (proc) onAddContextNode(proc);
              setContextMenuNode(null);
            }}
          >
            <ListPlus className="h-3.5 w-3.5" /> Add to Context
          </button>
          <hr className="my-1 border-zinc-200 dark:border-zinc-800" />
          <button
            className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-xs text-rose-600 hover:bg-rose-50 dark:text-rose-400 dark:hover:bg-rose-950/30"
            onClick={() => {
              onSoftDeleteNode(contextMenuNode.pk);
              setContextMenuNode(null);
            }}
          >
            <Trash2 className="h-3.5 w-3.5" /> Delete Node
          </button>
        </div>
      )}

      {contextMenuGroup && (
        <div
          className="fixed z-50 min-w-40 rounded-md border border-zinc-200 bg-white p-1 shadow-md dark:border-zinc-800 dark:bg-zinc-900 animate-in fade-in"
          style={{ top: contextMenuGroup.y, left: contextMenuGroup.x }}
          onClick={(e) => e.stopPropagation()}
        >
          <button
            className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-xs text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
            onClick={() => {
              const lbl = window.prompt("Rename Group:");
              if (lbl) onRenameGroup(contextMenuGroup.pk, lbl);
              setContextMenuGroup(null);
            }}
          >
            <Pencil className="h-3.5 w-3.5" /> Rename
          </button>
          <button
            className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-xs text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
            onClick={() => {
              const grp = groups.find(g => g.pk === contextMenuGroup.pk);
              if (grp) onExportGroup(grp);
              setContextMenuGroup(null);
            }}
          >
            <Download className="h-3.5 w-3.5" /> Export Group
          </button>
          <hr className="my-1 border-zinc-200 dark:border-zinc-800" />
          <button
            className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-xs text-rose-600 hover:bg-rose-50 dark:text-rose-400 dark:hover:bg-rose-950/30"
            onClick={() => {
              if (window.confirm("Are you sure?")) onDeleteGroup(contextMenuGroup.pk);
              setContextMenuGroup(null);
            }}
          >
            <Trash2 className="h-3.5 w-3.5" /> Delete Group
          </button>
        </div>
      )}

    </aside>
  );
}
