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
  FolderPlus,
  Cpu,
  Code2
} from "lucide-react";
import { type DragEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import { BridgeStatus } from "@/components/dashboard/bridge-status";
import { cn } from "@/lib/utils";
import { exportCodeConfig, exportComputerConfig, getInfrastructure, getNodeScript } from "@/lib/api";
import { QuickAddModal } from "@/components/dashboard/quick-add-modal";
import { CodeSetupModal } from "@/components/dashboard/code-setup-modal";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { GroupItem, ProcessItem, InfrastructureComputer, InfrastructureExportResponse } from "@/types/aiida";
import { DataImportModal } from "@/components/dashboard/data-import-modal";

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
const DATA_NODE_TYPES = new Set([
  "StructureData",
  "Dict",
  "ArrayData",
  "XyData",
  "BandsData",
  "RemoteData",
  "FolderData",
  "KpointsData",
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

type ManualCopyState = {
  title: string;
  description: string;
  text: string;
};

type InfrastructureContextMenuTarget = {
  x: number;
  y: number;
};

type MenuDimensions = {
  width: number;
  height: number;
};

type ContextMenuPosition = {
  x: number;
  y: number;
};

function normalizeState(state: string | null): string {
  return String(state || "unknown").trim().replace(/_/g, " ").toLowerCase();
}

function isStructureNode(process: ProcessItem): boolean {
  return process.node_type === "StructureData" || Boolean(process.formula);
}

function canInspectNode(process: ProcessItem): boolean {
  if (process.process_state !== null) {
    return true;
  }
  return PROCESS_LIKE_NODE_TYPES.has(process.node_type) || DATA_NODE_TYPES.has(process.node_type);
}

function canCloneNode(process: ProcessItem): boolean {
  const nodeType = String(process.node_type || "").trim();
  if (!nodeType) {
    return process.process_state !== null;
  }
  return nodeType === "ProcessNode" || nodeType === "WorkChainNode" || nodeType === "WorkflowNode";
}

function canCopyNodeAsScript(process: ProcessItem): boolean {
  const nodeType = String(process.node_type || "").trim();
  return nodeType === "StructureData" || nodeType === "Dict";
}

async function copyTextWithFallback(text: string): Promise<boolean> {
  const normalized = String(text ?? "");
  if (!normalized) {
    return false;
  }

  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(normalized);
      return true;
    } catch {
      // Fall through to legacy copy path.
    }
  }

  if (typeof document !== "undefined") {
    const textarea = document.createElement("textarea");
    textarea.value = normalized;
    textarea.setAttribute("readonly", "true");
    textarea.style.position = "fixed";
    textarea.style.top = "-9999px";
    textarea.style.left = "-9999px";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    textarea.setSelectionRange(0, normalized.length);
    try {
      if (document.execCommand("copy")) {
        document.body.removeChild(textarea);
        return true;
      }
    } catch {
      // Ignore and continue to manual fallback.
    }
    document.body.removeChild(textarea);
  }
  return false;
}

function downloadTextFile(filename: string, content: string, mimeType = "text/plain;charset=utf-8"): void {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

function clampMenuPosition(x: number, y: number, dimensions: MenuDimensions = { width: 196, height: 240 }): ContextMenuPosition {
  if (typeof window === "undefined") {
    return { x, y };
  }
  const margin = 12;
  const cursorOffset = 8;
  return {
    x: Math.max(margin, Math.min(x + cursorOffset, window.innerWidth - dimensions.width - margin)),
    y: Math.max(margin, Math.min(y + cursorOffset, window.innerHeight - dimensions.height - margin)),
  };
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
  const nodeType = process.node_type || "";
  const loType = nodeType.toLowerCase();

  if (loType.includes("structure")) {
    return { icon: "\uD83D\uDC8E", iconLabel: "Crystal" };
  }
  if (loType.includes("base") || loType.includes("log") || loType.includes("report")) {
    return { icon: "\u26A1", iconLabel: "Activity" };
  }
  if (loType.includes("bands") || loType.includes("xy") || loType.includes("trajectory")) {
    return { icon: "\uD83D\uDCC8", iconLabel: "Chart" };
  }
  if (loType.includes("dict") || loType.includes("array") || loType.includes("parameter")) {
    return { icon: "\uD83D\uDCD1", iconLabel: "Data" };
  }
  if (loType.includes("folder") || loType.includes("retrieved")) {
    return { icon: "\uD83D\uDCC1", iconLabel: "Folder" };
  }
  if (canInspectNode(process)) {
    return { icon: "\u26A1", iconLabel: "Activity" };
  }
  return { icon: "\uD83D\uDCE6", iconLabel: "Node" };
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
  if (canInspectNode(process)) {
    return getProcessSpecificLabel(process) || defaultTitle;
  }
  return defaultTitle;
}

function getProcessStatusTone(process: ProcessItem): ProcessStatusTone | null {
  if (!canInspectNode(process)) {
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
  const isStructure = isStructureNode(process);

  if (isStructure) {
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

  if (!isStructure && canInspectNode(process) && process.label.trim()) {
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
  selectedGroupLabel: string | null;
  isAllGroupsSelected: boolean;
  isCurrentContextSelected: boolean;
  currentContextGroupLabel: string | null;
  processLimit: number;
  contextNodeIds: number[];
  isUpdatingProcessLimit: boolean;
  isDarkMode: boolean;
  onToggleTheme: () => void;
  onSelectAllGroups: () => void;
  onSelectCurrentContext: () => void;
  onGroupChange: (groupLabel: string) => void;
  nodeTypeFilter: "all" | "structures" | "tasks" | "failed";
  onNodeTypeFilterChange: (type: "all" | "structures" | "tasks" | "failed") => void;
  onProcessLimitChange: (limit: number) => void;
  onAddContextNode: (process: ProcessItem) => void;
  onOpenProcessDetail: (process: ProcessItem) => void;
  onCreateGroup: (label: string) => void;
  onRenameGroup: (pk: number, label: string) => void;
  onDeleteGroup: (pk: number) => void;
  onAssignNodesToGroup: (groupPk: number, nodePks: number[]) => void;
  onSoftDeleteNode: (pk: number) => void;
  onExportGroup: (group: GroupItem) => void;
  onConsultFailedProcess: (process: ProcessItem) => void;
  onCloneProcess: (process: ProcessItem) => void;
};

export function Sidebar({
  processes,
  groups,
  selectedGroupLabel,
  isAllGroupsSelected,
  isCurrentContextSelected,
  currentContextGroupLabel,
  processLimit,
  contextNodeIds,
  isUpdatingProcessLimit,
  isDarkMode,
  onToggleTheme,
  onSelectAllGroups,
  onSelectCurrentContext,
  onGroupChange,
  nodeTypeFilter,
  onNodeTypeFilterChange,
  onProcessLimitChange,
  onAddContextNode,
  onOpenProcessDetail,
  onCreateGroup,
  onRenameGroup,
  onDeleteGroup,
  onAssignNodesToGroup,
  onSoftDeleteNode,
  onExportGroup,
  onConsultFailedProcess,
  onCloneProcess,
}: SidebarProps) {
  const [limitInput, setLimitInput] = useState(String(processLimit));
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedNodePks, setSelectedNodePks] = useState<Set<number>>(new Set());
  const [contextMenuNode, setContextMenuNode] = useState<{ pk: number; x: number; y: number } | null>(null);
  const [contextMenuGroup, setContextMenuGroup] = useState<{ pk: number; x: number; y: number } | null>(null);
  const [contextMenuComputer, setContextMenuComputer] = useState<({ pk: number; label: string } & InfrastructureContextMenuTarget) | null>(null);
  const [contextMenuCode, setContextMenuCode] = useState<({ pk: number; label: string; computerLabel: string } & InfrastructureContextMenuTarget) | null>(null);

  const [isSwitchingProfile, setIsSwitchingProfile] = useState(false);
  const switchTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const handleProfileSwitchStart = useCallback(() => {
    setIsSwitchingProfile(true);
    if (switchTimeoutRef.current) clearTimeout(switchTimeoutRef.current);
    // Timeout protection: 10 seconds
    switchTimeoutRef.current = setTimeout(() => {
      setIsSwitchingProfile(false);
      alert("Profile switch timed out or took too long.");
    }, 10000);
  }, []);

  const handleProfileSwitchEnd = useCallback(() => {
    if (switchTimeoutRef.current) clearTimeout(switchTimeoutRef.current);
    setIsSwitchingProfile(false);
  }, []);

  const [isGroupsExpanded, setIsGroupsExpanded] = useState(true);
  const [isInfraExpanded, setIsInfraExpanded] = useState(false);
  const [isQuickAddOpen, setIsQuickAddOpen] = useState(false);
  const [isCodeSetupOpen, setIsCodeSetupOpen] = useState(false);
  const [selectedComputerLabel, setSelectedComputerLabel] = useState("");
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set());
  const [expandedComputers, setExpandedComputers] = useState<Set<number>>(new Set());
  const [copyingScriptPk, setCopyingScriptPk] = useState<number | null>(null);
  const [manualCopyState, setManualCopyState] = useState<ManualCopyState | null>(null);
  const nodeMenuRef = useRef<HTMLDivElement | null>(null);
  const groupMenuRef = useRef<HTMLDivElement | null>(null);
  const computerMenuRef = useRef<HTMLDivElement | null>(null);
  const codeMenuRef = useRef<HTMLDivElement | null>(null);
  const manualCopyTextareaRef = useRef<HTMLTextAreaElement | null>(null);

  const [isDataImportOpen, setIsDataImportOpen] = useState(false);
  const [importGroupPk, setImportGroupPk] = useState<number | undefined>();
  const [importGroupLabel, setImportGroupLabel] = useState<string | undefined>();

  const queryClient = useQueryClient();
  const infraQuery = useQuery({
    queryKey: ["aiida-infrastructure"],
    queryFn: getInfrastructure,
    refetchInterval: 30000,
  });

  const infrastructure = infraQuery.data || [];

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
      if (nodeTypeFilter === "tasks" && !canInspectNode(proc)) return false;
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

  const openNodeContextMenuAt = useCallback((pk: number, x: number, y: number) => {
    const position = clampMenuPosition(x, y);
    setContextMenuNode({ pk, x: position.x, y: position.y });
  }, []);

  const openNodeContextMenu = useCallback((event: React.MouseEvent, pk: number) => {
    event.preventDefault();
    event.stopPropagation();
    openNodeContextMenuAt(pk, event.clientX, event.clientY);
  }, [openNodeContextMenuAt]);

  const openManualCopyDialog = useCallback((title: string, description: string, text: string) => {
    setManualCopyState({ title, description, text });
  }, []);

  const handleCopyPk = useCallback(async (pk: number) => {
    const copied = await copyTextWithFallback(String(pk));
    if (!copied) {
      openManualCopyDialog(
        `Copy node #${pk} PK`,
        "Clipboard access is blocked in this browser context. Copy the PK manually below.",
        String(pk),
      );
    }
  }, [openManualCopyDialog]);

  const handleCopyNodeScript = useCallback(async (process: ProcessItem) => {
    setCopyingScriptPk(process.pk);
    try {
      const payload = await getNodeScript(process.pk);
      const copied = await copyTextWithFallback(payload.script);
      if (!copied) {
        openManualCopyDialog(
          `Copy script for node #${process.pk}`,
          "Clipboard access is blocked in this browser context. Copy the script manually below.",
          payload.script,
        );
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : `Failed to copy script for node #${process.pk}.`;
      window.alert(message);
    } finally {
      setCopyingScriptPk(null);
    }
  }, [openManualCopyDialog]);

  const handleInfrastructureExport = useCallback(async (payload: InfrastructureExportResponse, title: string) => {
    try {
      downloadTextFile(payload.filename, payload.content, "application/x-yaml;charset=utf-8");
    } catch {
      openManualCopyDialog(
        title,
        "Automatic download failed in this browser context. Copy the exported configuration manually below.",
        payload.content,
      );
    }
  }, [openManualCopyDialog]);

  const handleExportComputer = useCallback(async (computerPk: number, computerLabel: string) => {
    try {
      const payload = await exportComputerConfig(computerPk);
      await handleInfrastructureExport(payload, `Export computer ${computerLabel}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : `Failed to export computer ${computerLabel}.`;
      window.alert(message);
    }
  }, [handleInfrastructureExport]);

  const handleExportCode = useCallback(async (codePk: number, codeLabel: string) => {
    try {
      const payload = await exportCodeConfig(codePk);
      await handleInfrastructureExport(payload, `Export code ${codeLabel}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : `Failed to export code ${codeLabel}.`;
      window.alert(message);
    }
  }, [handleInfrastructureExport]);

  useEffect(() => {
    if (!manualCopyState || !manualCopyTextareaRef.current) {
      return;
    }
    manualCopyTextareaRef.current.focus();
    manualCopyTextareaRef.current.select();
    manualCopyTextareaRef.current.setSelectionRange(0, manualCopyState.text.length);
  }, [manualCopyState]);

  // Close context menus on click outside
  useEffect(() => {
    const handlePointerDown = (event: MouseEvent) => {
      if (event.button !== 0) {
        return;
      }
      const target = event.target;
      if (
        (nodeMenuRef.current && target instanceof Node && nodeMenuRef.current.contains(target)) ||
        (groupMenuRef.current && target instanceof Node && groupMenuRef.current.contains(target)) ||
        (computerMenuRef.current && target instanceof Node && computerMenuRef.current.contains(target)) ||
        (codeMenuRef.current && target instanceof Node && codeMenuRef.current.contains(target))
      ) {
        return;
      }
      setContextMenuNode(null);
      setContextMenuGroup(null);
      setContextMenuComputer(null);
      setContextMenuCode(null);
    };
    window.addEventListener("mousedown", handlePointerDown);
    return () => window.removeEventListener("mousedown", handlePointerDown);
  }, []);

  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") {
        return;
      }
      setContextMenuNode(null);
      setContextMenuGroup(null);
      setContextMenuComputer(null);
      setContextMenuCode(null);
      setManualCopyState(null);
    };
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, []);

  const currentContextGroup = useMemo(
    () => groups.find((group) => group.label === currentContextGroupLabel) ?? null,
    [currentContextGroupLabel, groups],
  );

  const groupTree = useMemo(() => {
    const root: Record<string, any> = { children: {}, group: null, path: "" };
    for (const group of groups) {
      const parts = group.label.split("/");
      let current = root;
      let pathSoFar = "";
      for (let i = 0; i < parts.length; i++) {
        const part = parts[i];
        pathSoFar = pathSoFar ? `${pathSoFar}/${part}` : part;
        if (!current.children[part]) {
          current.children[part] = { children: {}, group: null, path: pathSoFar };
        }
        current = current.children[part];
        if (i === parts.length - 1) {
          current.group = group;
        }
      }
    }
    return root;
  }, [groups]);

  const toggleFolder = (path: string, event: React.MouseEvent) => {
    event.stopPropagation();
    setExpandedFolders((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  const renderGroupTree = (node: any, level = 0) => {
    return (
      <div className="flex flex-col gap-1">
        {Object.entries(node.children)
          .sort(([a], [b]) => a.localeCompare(b))
          .map(([name, child]: [string, any]) => {
            const isExpanded = expandedFolders.has(child.path);
            const hasChildren = Object.keys(child.children).length > 0;
            const group = child.group;
            const isSelected = group && selectedGroupLabel === group.label;

            return (
              <div key={child.path} className="flex flex-col">
                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => {
                    if (group) onGroupChange(group.label);
                    if (hasChildren) toggleFolder(child.path, { stopPropagation: () => { } } as any);
                  }}
                  onDragOver={(e) => {
                    if (group) {
                      e.preventDefault();
                      e.dataTransfer.dropEffect = "copy";
                    }
                  }}
                  onDrop={(e) => {
                    if (group) handleGroupDrop(e, group.pk);
                  }}
                  onContextMenu={(e) => {
                    if (group) {
                      e.preventDefault();
                      setContextMenuGroup({ pk: group.pk, ...clampMenuPosition(e.clientX, e.clientY, { width: 176, height: 120 }) });
                    }
                  }}
                  style={{ paddingLeft: `${level * 12 + 8}px` }}
                  className={cn(
                    "group flex items-center justify-between rounded-md py-1.5 pr-2 text-sm transition-colors",
                    isSelected
                      ? "bg-zinc-100 dark:bg-zinc-800/60 font-medium"
                      : "hover:bg-zinc-100/50 dark:hover:bg-zinc-800/30 text-zinc-600 dark:text-zinc-400"
                  )}
                >
                  <div className="flex items-center gap-1.5 overflow-hidden">
                    {hasChildren ? (
                      <ChevronRight className={cn("h-3.5 w-3.5 transition-transform shrink-0", isExpanded && "rotate-90")} />
                    ) : (
                      <div className="h-3.5 w-3.5 shrink-0" />
                    )}
                    <FolderOpen
                      className={cn(
                        "h-4 w-4 shrink-0 transition-opacity",
                        group ? "text-zinc-400 dark:text-zinc-500" : "text-zinc-400/40 dark:text-zinc-500/30"
                      )}
                    />
                    <span className="truncate">{name}</span>
                  </div>

                  <div className="flex items-center gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setImportGroupPk(group?.pk);
                        setImportGroupLabel(child.path);
                        setIsDataImportOpen(true);
                      }}
                      className="p-0.5 hover:bg-zinc-200 dark:hover:bg-zinc-700 rounded transition-colors"
                      title="Import Data"
                    >
                      <Plus className="h-3 w-3 text-zinc-500" />
                    </button>
                    {group && (
                      <span className="text-[10px] text-zinc-400 shrink-0">
                        {group.count}
                      </span>
                    )}
                  </div>
                </div>
                {hasChildren && isExpanded && renderGroupTree(child, level + 1)}
              </div>
            );
          })}
      </div>
    );
  };

  const toggleComputer = (pk: number, event: React.MouseEvent) => {
    event.stopPropagation();
    setExpandedComputers((prev) => {
      const next = new Set(prev);
      if (next.has(pk)) next.delete(pk);
      else next.add(pk);
      return next;
    });
  };

  const renderInfrastructureTree = () => {
    return (
      <div className="flex flex-col gap-1">
        {infrastructure.map((computer: InfrastructureComputer) => {
          const isExpanded = expandedComputers.has(computer.pk);
          return (
            <div key={computer.pk} className="flex flex-col">
              <div
                role="button"
                tabIndex={0}
                onClick={(e) => toggleComputer(computer.pk, e)}
                onContextMenu={(e) => {
                  e.preventDefault();
                  setContextMenuComputer({
                    pk: computer.pk,
                    label: computer.label,
                    ...clampMenuPosition(e.clientX, e.clientY, { width: 180, height: 96 }),
                  });
                  setContextMenuCode(null);
                }}
                className="group flex items-center justify-between rounded-md px-2 py-1.5 text-sm transition-colors hover:bg-zinc-100/50 dark:hover:bg-zinc-800/30 text-zinc-600 dark:text-zinc-400"
              >
                <div className="flex items-center gap-2 overflow-hidden">
                  <ChevronRight className={cn("h-3.5 w-3.5 transition-transform shrink-0", isExpanded && "rotate-90")} />
                  <div className={cn("h-2 w-2 rounded-full shrink-0", computer.is_enabled ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]" : "bg-rose-500 shadow-[0_0_8px_rgba(239,68,68,0.5)]")} title={computer.is_enabled ? "Online" : "Offline"} />
                  <Cpu className="h-4 w-4 shrink-0 text-zinc-400" />
                  <span className="truncate font-medium">{computer.label}</span>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedComputerLabel(computer.label);
                    setIsCodeSetupOpen(true);
                  }}
                  className="p-1 hover:bg-zinc-200 dark:hover:bg-zinc-800 rounded-md transition-colors opacity-0 group-hover:opacity-100"
                  title="Add Code"
                >
                  <Plus className="h-3.5 w-3.5 text-zinc-500" />
                </button>
              </div>
              {isExpanded && (
                <div className="flex flex-col gap-1 ml-4 mt-1">
                  {computer.codes.map((code) => (
                    <div
                      key={code.pk}
                      onContextMenu={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        setContextMenuComputer(null);
                        setContextMenuCode({
                          pk: code.pk,
                          label: code.label,
                          computerLabel: computer.label,
                          ...clampMenuPosition(e.clientX, e.clientY, { width: 180, height: 96 }),
                        });
                      }}
                      className="flex items-center gap-2 rounded-md px-3 py-1 text-xs text-zinc-500 dark:text-zinc-400 hover:bg-zinc-100/30 dark:hover:bg-zinc-800/20"
                    >
                      <Code2 className="h-3.5 w-3.5 shrink-0" />
                      <span className="truncate">{code.label}</span>
                    </div>
                  ))}
                  {computer.codes.length === 0 && (
                    <span className="text-[10px] text-zinc-400 ml-6 italic">No codes configured</span>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <aside className="relative flex h-full min-h-0 w-full shrink-0 flex-col gap-2 font-sans tracking-tight">
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

      <BridgeStatus
        onInfrastructureClick={() => setIsInfraExpanded(true)}
        onSwitchProfileStart={handleProfileSwitchStart}
        onSwitchProfileEnd={handleProfileSwitchEnd}
      />

      <Panel className="relative z-10 flex min-h-0 flex-1 flex-col gap-4 border-zinc-100/90 p-4 transition-opacity duration-300 dark:border-zinc-800/80">

        {isSwitchingProfile && (
          <div className="absolute inset-0 z-50 flex flex-col items-center justify-center rounded-2xl bg-black/10 backdrop-blur-[2px] dark:bg-black/30">
            <Loader2 className="h-6 w-6 animate-spin text-zinc-700 dark:text-zinc-300 drop-shadow-sm" />
            <p className="mt-2 text-[10px] font-medium tracking-wider text-zinc-700 dark:text-zinc-300 drop-shadow-sm">
              Switching AiiDA Environment...
            </p>
          </div>
        )}

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
                  onClick={() => onNodeTypeFilterChange(type)}
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

        <div className="flex flex-col gap-3 shrink-0">
          <div className="flex flex-col gap-1">
            <span className="pl-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-zinc-500 dark:text-zinc-400">
              Current Context
            </span>
            <button
              type="button"
              onClick={onSelectCurrentContext}
              disabled={!currentContextGroupLabel}
              className={cn(
                "flex items-center justify-between rounded-xl border px-3 py-2.5 text-left transition-all",
                currentContextGroupLabel
                  ? "border-zinc-200/75 bg-white/70 hover:border-zinc-300/85 hover:bg-white/85 dark:border-zinc-800/80 dark:bg-zinc-900/45 dark:hover:border-zinc-700/85 dark:hover:bg-zinc-900/60"
                  : "cursor-not-allowed border-dashed border-zinc-200/70 bg-zinc-50/50 text-zinc-400 dark:border-zinc-800/70 dark:bg-zinc-900/30 dark:text-zinc-500",
                isCurrentContextSelected && currentContextGroupLabel
                  ? "border-zinc-300 bg-zinc-100/80 shadow-[0_10px_24px_-20px_rgba(15,23,42,0.7)] dark:border-zinc-700 dark:bg-zinc-800/60"
                  : null,
              )}
            >
              <div className="flex min-w-0 items-center gap-2.5">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
                  <FolderOpen className="h-4 w-4" />
                </div>
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-zinc-900 dark:text-zinc-100">Current Context</p>
                  <p className="truncate text-[11px] text-zinc-500 dark:text-zinc-400">
                    {currentContextGroupLabel ?? "No active session"}
                  </p>
                </div>
              </div>
              {currentContextGroup ? (
                <span className="ml-3 shrink-0 rounded-full bg-zinc-100 px-2 py-0.5 text-[11px] font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
                  {currentContextGroup.count}
                </span>
              ) : null}
            </button>
          </div>

          <div className="flex flex-col gap-1">
            <div className="flex items-center justify-between group/groupbtn">
              <button
                onClick={() => setIsGroupsExpanded(!isGroupsExpanded)}
                className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400"
              >
                <ChevronRight className={cn("h-3.5 w-3.5 transition-transform", isGroupsExpanded && "rotate-90")} />
                Archive
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  const label = window.prompt("Enter new group name:");
                  if (label) onCreateGroup(label);
                }}
                className="p-1 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-md transition-colors opacity-0 group-hover/groupbtn:opacity-100"
              >
                <Plus className="h-3.5 w-3.5 text-zinc-400" />
              </button>
            </div>

            {isGroupsExpanded && (
              <div className="mt-1 flex max-h-[300px] flex-col gap-1 overflow-y-auto minimal-scrollbar">
                <div
                  role="button"
                  tabIndex={0}
                  onClick={onSelectAllGroups}
                  className={cn(
                    "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors",
                    isAllGroupsSelected
                      ? "bg-zinc-100 font-medium dark:bg-zinc-800/60"
                      : "text-zinc-600 hover:bg-zinc-100/50 dark:text-zinc-400 dark:hover:bg-zinc-800/30",
                  )}
                >
                  <FolderOpen className="h-4 w-4" />
                  <span>All Groups</span>
                </div>
                {renderGroupTree(groupTree)}
              </div>
            )}
          </div>
        </div>

        <hr className="border-zinc-200/60 dark:border-zinc-800/60 shrink-0" />

        {/* Nodes Section */}
        <div className="flex min-h-0 flex-1 flex-col gap-2 relative">
          <div className="flex items-center justify-between shrink-0">
            <span className="text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 pl-[18px]">
              Nodes {isCurrentContextSelected ? (
                "in Current Context"
              ) : selectedGroupLabel ? (
                <>
                  in <span title={selectedGroupLabel}>
                    {selectedGroupLabel.split('/').pop()!.length > 20
                      ? `${selectedGroupLabel.split('/').pop()?.slice(0, 17)}...`
                      : selectedGroupLabel.split('/').pop()}
                  </span>
                </>
              ) : isAllGroupsSelected ? (
                "Across Archive"
              ) : "Recent"}
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
                const canOpenDetail = canInspectNode(process);
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
                    onClick={() => onOpenProcessDetail(process)}
                    onContextMenuCapture={(e) => {
                      openNodeContextMenu(e, process.pk);
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
                        <div className="flex items-center gap-1 shrink-0">
                          {metadata.processStatus && (
                            <p className={cn("text-[11px] font-semibold tracking-tight", metadata.processStatus.className)}>
                              {metadata.processStatus.label}
                            </p>
                          )}
                          <button
                            type="button"
                            draggable={false}
                            data-node-menu-trigger="true"
                            className="rounded-md p-1 text-zinc-400 opacity-0 transition-opacity hover:bg-zinc-100 hover:text-zinc-700 group-hover/card:opacity-100 dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
                            onMouseDown={(e) => {
                              e.preventDefault();
                              e.stopPropagation();
                            }}
                            onClick={(e) => {
                              e.preventDefault();
                              e.stopPropagation();
                              const rect = e.currentTarget.getBoundingClientRect();
                              openNodeContextMenuAt(process.pk, rect.right - 188, rect.bottom + 6);
                            }}
                            title="Node actions"
                            aria-label={`Open menu for node ${process.pk}`}
                          >
                            <MoreVertical className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </div>

                      <div className="min-w-0">
                        <div className="flex flex-col">
                          {metadata.lines.map((line, idx) => (
                            <p key={idx} className={cn("truncate text-[11px] tracking-tight", idx === 0 ? "text-zinc-700 dark:text-zinc-300" : "text-zinc-500 dark:text-zinc-400")}>
                              {line}
                            </p>
                          ))}
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
            </div>
          )}
        </div>

        <hr className="border-zinc-200/60 dark:border-zinc-800/60 shrink-0" />

        {/* Infrastructure Section */}
        <div className="flex flex-col gap-1 shrink-0">
          <div className="flex items-center justify-between group/infra">
            <button
              onClick={() => setIsInfraExpanded(!isInfraExpanded)}
              className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400"
            >
              <ChevronRight className={cn("h-3.5 w-3.5 transition-transform", isInfraExpanded && "rotate-90")} />
              Infrastructure
            </button>
            <button
              onClick={() => setIsQuickAddOpen(true)}
              className="p-1 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-md transition-colors opacity-0 group-hover/infra:opacity-100"
            >
              <Plus className="h-3.5 w-3.5 text-zinc-500" />
            </button>
          </div>

          {isInfraExpanded && (
            <div className="flex flex-col gap-1 mt-1 max-h-[300px] overflow-y-auto minimal-scrollbar">
              {infrastructure.length === 0 ? (
                <p className="px-2 py-2 text-[11px] text-zinc-400 italic">No computers configured</p>
              ) : renderInfrastructureTree()}
            </div>
          )}
        </div>
      </Panel>

      {/* Context Menus */}
      {contextMenuNode && typeof document !== "undefined" && createPortal((() => {
        const process = processes.find((item) => item.pk === contextMenuNode.pk);
        const isFailed = process ? FAILED_PROCESS_STATES.has(normalizeState(process.process_state || process.state)) : false;
        return (
          <div
            ref={nodeMenuRef}
            className="fixed z-[110] min-w-44 rounded-md border border-zinc-200 bg-white p-1 shadow-xl dark:border-zinc-800 dark:bg-zinc-900 animate-in fade-in"
            style={{ top: contextMenuNode.y, left: contextMenuNode.x }}
            onClick={(e) => e.stopPropagation()}
          >
            {process && canCopyNodeAsScript(process) && (
              <button
                className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-xs text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
                disabled={copyingScriptPk === process.pk}
                onClick={() => {
                  void handleCopyNodeScript(process);
                  setContextMenuNode(null);
                }}
              >
                <Code2 className="h-3.5 w-3.5" /> {copyingScriptPk === process.pk ? "Copying..." : "Copy as Script"}
              </button>
            )}
            {process && canCloneNode(process) && (
              <button
                className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-xs text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
                onClick={() => {
                  onCloneProcess(process);
                  setContextMenuNode(null);
                }}
              >
                <Copy className="h-3.5 w-3.5" /> Clone & Edit
              </button>
            )}
            <button
              className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-xs text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
              onClick={() => {
                void handleCopyPk(contextMenuNode.pk);
                setContextMenuNode(null);
              }}
            >
              <Copy className="h-3.5 w-3.5" /> Copy PK
            </button>
            {process && (
              <button
                className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-xs text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
                onClick={() => {
                  onAddContextNode(process);
                  setContextMenuNode(null);
                }}
              >
                <ListPlus className="h-3.5 w-3.5" /> Add to Context
              </button>
            )}
            {process && isFailed && (
              <button
                className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-xs text-rose-600 hover:bg-rose-50 dark:text-rose-400 dark:hover:bg-rose-950/30"
                onClick={() => {
                  onConsultFailedProcess(process);
                  setContextMenuNode(null);
                }}
              >
                <Wand2 className="h-3.5 w-3.5" /> AI Diagnose
              </button>
            )}
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
        );
      })(), document.body)}

      {contextMenuGroup && typeof document !== "undefined" && createPortal(
        <div
          ref={groupMenuRef}
          className="fixed z-[110] min-w-40 rounded-md border border-zinc-200 bg-white p-1 shadow-xl dark:border-zinc-800 dark:bg-zinc-900 animate-in fade-in"
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
        </div>,
        document.body,
      )}

      {contextMenuComputer && typeof document !== "undefined" && createPortal(
        <div
          ref={computerMenuRef}
          className="fixed z-[110] min-w-44 rounded-md border border-zinc-200 bg-white p-1 shadow-xl dark:border-zinc-800 dark:bg-zinc-900 animate-in fade-in"
          style={{ top: contextMenuComputer.y, left: contextMenuComputer.x }}
          onClick={(e) => e.stopPropagation()}
        >
          <button
            className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-xs text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
            onClick={() => {
                  void handleExportComputer(contextMenuComputer.pk, contextMenuComputer.label);
                  setContextMenuComputer(null);
                }}
          >
            <Download className="h-3.5 w-3.5" /> Export Computer Config
          </button>
          <button
            className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-xs text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
            onClick={() => {
              setSelectedComputerLabel(contextMenuComputer.label);
              setIsCodeSetupOpen(true);
              setContextMenuComputer(null);
            }}
          >
            <Plus className="h-3.5 w-3.5" /> Add Code
          </button>
        </div>,
        document.body,
      )}

      {contextMenuCode && typeof document !== "undefined" && createPortal(
        <div
          ref={codeMenuRef}
          className="fixed z-[110] min-w-44 rounded-md border border-zinc-200 bg-white p-1 shadow-xl dark:border-zinc-800 dark:bg-zinc-900 animate-in fade-in"
          style={{ top: contextMenuCode.y, left: contextMenuCode.x }}
          onClick={(e) => e.stopPropagation()}
        >
          <button
            className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-xs text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
            onClick={() => {
              void handleExportCode(contextMenuCode.pk, contextMenuCode.label);
              setContextMenuCode(null);
            }}
          >
            <Download className="h-3.5 w-3.5" /> Export Code Config
          </button>
          <button
            className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-xs text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
            onClick={() => {
              setSelectedComputerLabel(contextMenuCode.computerLabel);
              setIsCodeSetupOpen(true);
              setContextMenuCode(null);
            }}
          >
            <Pencil className="h-3.5 w-3.5" /> Edit on Computer
          </button>
        </div>,
        document.body,
      )}

      {manualCopyState && (
        <div
          className="fixed inset-0 z-[70] flex items-center justify-center bg-zinc-950/45 px-4"
          onClick={() => setManualCopyState(null)}
        >
          <div
            className="w-full max-w-3xl rounded-2xl border border-zinc-200 bg-white p-4 shadow-2xl dark:border-zinc-800 dark:bg-zinc-900"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-3 flex items-start justify-between gap-3">
              <div className="min-w-0">
                <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{manualCopyState.title}</h3>
                <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{manualCopyState.description}</p>
              </div>
              <button
                type="button"
                className="rounded-md px-2 py-1 text-xs text-zinc-500 hover:bg-zinc-100 hover:text-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
                onClick={() => setManualCopyState(null)}
              >
                Close
              </button>
            </div>
            <textarea
              ref={manualCopyTextareaRef}
              readOnly
              value={manualCopyState.text}
              className="h-72 w-full rounded-xl border border-zinc-200 bg-zinc-50 px-3 py-2 font-mono text-xs text-zinc-700 outline-none focus:ring-2 focus:ring-blue-200 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-200 dark:focus:ring-blue-900"
            />
            <div className="mt-3 flex items-center justify-end gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  if (!manualCopyTextareaRef.current) {
                    return;
                  }
                  manualCopyTextareaRef.current.focus();
                  manualCopyTextareaRef.current.select();
                  manualCopyTextareaRef.current.setSelectionRange(0, manualCopyState.text.length);
                }}
              >
                Select All
              </Button>
              <Button
                size="sm"
                onClick={() => {
                  void (async () => {
                    const copied = await copyTextWithFallback(manualCopyState.text);
                    if (copied) {
                      setManualCopyState(null);
                    }
                  })();
                }}
              >
                Try Copy Again
              </Button>
            </div>
          </div>
        </div>
      )}

      <QuickAddModal
        isOpen={isQuickAddOpen}
        onClose={() => setIsQuickAddOpen(false)}
        onSuccess={() => {
          void queryClient.invalidateQueries({ queryKey: ["aiida-infrastructure"] });
        }}
      />

      <CodeSetupModal
        isOpen={isCodeSetupOpen}
        onClose={() => setIsCodeSetupOpen(false)}
        computerLabel={selectedComputerLabel}
        onSuccess={() => {
          void queryClient.invalidateQueries({ queryKey: ["aiida-infrastructure"] });
        }}
      />
      <DataImportModal
        isOpen={isDataImportOpen}
        onClose={() => setIsDataImportOpen(false)}
        onSuccess={() => {
          queryClient.invalidateQueries({ queryKey: ["processes"] });
          queryClient.invalidateQueries({ queryKey: ["groups"] });
        }}
        groupPk={importGroupPk}
        groupLabel={importGroupLabel}
      />
    </aside>
  );
}
