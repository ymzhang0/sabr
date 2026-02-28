import { ChevronDown, Loader2, Moon, Sun } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import { BridgeStatus } from "@/components/dashboard/bridge-status";
import { cn } from "@/lib/utils";
import type { ProcessItem } from "@/types/aiida";

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
  groupOptions: string[];
  selectedGroup: string;
  selectedType: string;
  processLimit: number;
  contextNodeIds: number[];
  isUpdatingProcessLimit: boolean;
  isDarkMode: boolean;
  onToggleTheme: () => void;
  onGroupChange: (groupLabel: string) => void;
  onTypeChange: (nodeType: string) => void;
  onProcessLimitChange: (limit: number) => void;
  onAddContextNode: (process: ProcessItem) => void;
  onOpenProcessDetail: (process: ProcessItem) => void;
};

const NODE_TYPE_OPTIONS = [
  "ProcessNode",
  "WorkChainNode",
  "CalcJobNode",
  "CalcFunctionNode",
  "StructureData",
  "BandsData",
  "ArrayData",
  "XyData",
  "Dict",
  "KpointsData",
  "UpfData",
  "RemoteData",
  "FolderData",
] as const;

export function Sidebar({
  processes,
  groupOptions,
  selectedGroup,
  selectedType,
  processLimit,
  contextNodeIds,
  isUpdatingProcessLimit,
  isDarkMode,
  onToggleTheme,
  onGroupChange,
  onTypeChange,
  onProcessLimitChange,
  onAddContextNode,
  onOpenProcessDetail,
}: SidebarProps) {
  const groupMenuRef = useRef<HTMLDivElement | null>(null);
  const typeMenuRef = useRef<HTMLDivElement | null>(null);
  const [isGroupMenuOpen, setIsGroupMenuOpen] = useState(false);
  const [isTypeMenuOpen, setIsTypeMenuOpen] = useState(false);
  const [limitInput, setLimitInput] = useState(String(processLimit));

  useEffect(() => {
    setLimitInput(String(processLimit));
  }, [processLimit]);

  const sortedGroups = useMemo(
    () => [...groupOptions].sort((a, b) => a.localeCompare(b)),
    [groupOptions],
  );
  const contextNodeIdSet = useMemo(
    () => new Set(contextNodeIds),
    [contextNodeIds],
  );

  useEffect(() => {
    const handleOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      if (groupMenuRef.current && !groupMenuRef.current.contains(target)) {
        setIsGroupMenuOpen(false);
      }
      if (typeMenuRef.current && !typeMenuRef.current.contains(target)) {
        setIsTypeMenuOpen(false);
      }
    };

    window.addEventListener("mousedown", handleOutside);
    return () => window.removeEventListener("mousedown", handleOutside);
  }, []);

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

  return (
    <aside className="flex h-full min-h-0 w-full shrink-0 flex-col gap-2 font-sans tracking-tight lg:w-[360px]">
      <header className="flex items-center justify-between">
        <h1 className="text-lg font-semibold tracking-tight text-zinc-900 dark:text-zinc-100">
          AiiDA Agent
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

      <Panel
        className="relative z-10 flex min-h-0 flex-1 flex-col border-zinc-100/90 p-4 transition-opacity duration-300 dark:border-zinc-800/80"
      >
        <div className="mx-auto flex h-full min-h-0 w-[90%] flex-col">
          <div className="mb-3 flex items-center justify-between gap-2">
            <p className="text-[11px] uppercase tracking-[0.18em] text-zinc-500 dark:text-zinc-400">
              AiiDA Explorer
            </p>
            <div className="flex items-center gap-2">
              {isUpdatingProcessLimit ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin text-zinc-400 dark:text-zinc-500" />
              ) : null}
              <input
                type="number"
                min={1}
                max={100}
                value={limitInput}
                inputMode="numeric"
                className="h-5 w-10 border-0 border-b border-zinc-300/80 bg-transparent px-0 text-right text-xs text-zinc-700 outline-none transition-colors duration-200 focus:border-zinc-500 dark:border-zinc-700 dark:text-zinc-300 dark:focus:border-zinc-500"
                aria-label="Process monitor recent node limit"
                onChange={(event) => {
                  const sanitized = event.target.value.replace(/[^\d]/g, "");
                  setLimitInput(sanitized);
                  if (!sanitized) {
                    return;
                  }
                  const parsed = Number.parseInt(sanitized, 10);
                  if (Number.isNaN(parsed)) {
                    return;
                  }
                  onProcessLimitChange(clampRecentLimit(parsed));
                }}
                onBlur={() => commitProcessLimit(limitInput)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    commitProcessLimit(limitInput);
                    (event.currentTarget as HTMLInputElement).blur();
                  }
                }}
              />
              <span className="text-xs text-zinc-500 dark:text-zinc-400">recent</span>
            </div>
          </div>

          <div className="flex min-h-0 flex-1 flex-col gap-4">
            <div className="flex items-center gap-4">
              <div ref={groupMenuRef} className="relative min-w-0 flex-1">
                <button
                  type="button"
                  className="inline-flex h-9 w-full items-center gap-2 rounded-lg border border-zinc-200/65 bg-zinc-50/70 px-3 text-sm text-zinc-700 transition-all duration-200 hover:border-zinc-300 hover:bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900/45 dark:text-zinc-200 dark:hover:border-zinc-700 dark:hover:bg-zinc-900/60"
                  onClick={() => {
                    setIsTypeMenuOpen(false);
                    setIsGroupMenuOpen((open) => !open);
                  }}
                >
                  <span className="truncate text-left">{selectedGroup || "All Groups"}</span>
                  <ChevronDown
                    className={cn("h-4 w-4 shrink-0 transition-transform duration-200", isGroupMenuOpen && "rotate-180")}
                  />
                </button>

                {isGroupMenuOpen ? (
                  <div className="absolute left-0 top-full z-20 mt-2 w-full overflow-hidden rounded-lg border border-zinc-200/70 bg-zinc-50/95 shadow-lg backdrop-blur dark:border-zinc-800 dark:bg-zinc-900/95">
                    <div className="minimal-scrollbar max-h-60 overflow-y-auto p-1">
                      <button
                        type="button"
                        className={cn(
                          "flex w-full items-center rounded-md px-2.5 py-2 text-left text-sm transition-colors duration-200",
                          !selectedGroup
                            ? "bg-zinc-200/70 text-zinc-900 dark:bg-zinc-800 dark:text-zinc-100"
                            : "text-zinc-700 hover:bg-zinc-200/50 dark:text-zinc-300 dark:hover:bg-zinc-800/80",
                        )}
                        onClick={() => {
                          onGroupChange("");
                          setIsGroupMenuOpen(false);
                        }}
                      >
                        <span className="truncate">All Groups</span>
                      </button>
                      {sortedGroups.map((groupLabel) => (
                        <button
                          key={groupLabel}
                          type="button"
                          className={cn(
                            "flex w-full items-center rounded-md px-2.5 py-2 text-left text-sm transition-colors duration-200",
                            groupLabel === selectedGroup
                              ? "bg-zinc-200/70 text-zinc-900 dark:bg-zinc-800 dark:text-zinc-100"
                              : "text-zinc-700 hover:bg-zinc-200/50 dark:text-zinc-300 dark:hover:bg-zinc-800/80",
                          )}
                          onClick={() => {
                            onGroupChange(groupLabel);
                            setIsGroupMenuOpen(false);
                          }}
                        >
                          <span className="truncate">{groupLabel}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>

              <div ref={typeMenuRef} className="relative min-w-0 flex-1">
                <button
                  type="button"
                  className="inline-flex h-9 w-full items-center gap-2 rounded-lg border border-zinc-200/65 bg-zinc-50/70 px-3 text-sm text-zinc-700 transition-all duration-200 hover:border-zinc-300 hover:bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900/45 dark:text-zinc-200 dark:hover:border-zinc-700 dark:hover:bg-zinc-900/60"
                  onClick={() => {
                    setIsGroupMenuOpen(false);
                    setIsTypeMenuOpen((open) => !open);
                  }}
                >
                  <span className="truncate text-left">{selectedType || "All Types"}</span>
                  <ChevronDown
                    className={cn("h-4 w-4 shrink-0 transition-transform duration-200", isTypeMenuOpen && "rotate-180")}
                  />
                </button>

                {isTypeMenuOpen ? (
                  <div className="absolute left-0 top-full z-20 mt-2 w-full overflow-hidden rounded-lg border border-zinc-200/70 bg-zinc-50/95 shadow-lg backdrop-blur dark:border-zinc-800 dark:bg-zinc-900/95">
                    <div className="minimal-scrollbar max-h-60 overflow-y-auto p-1">
                      <button
                        type="button"
                        className={cn(
                          "flex w-full items-center rounded-md px-2.5 py-2 text-left text-sm transition-colors duration-200",
                          !selectedType
                            ? "bg-zinc-200/70 text-zinc-900 dark:bg-zinc-800 dark:text-zinc-100"
                            : "text-zinc-700 hover:bg-zinc-200/50 dark:text-zinc-300 dark:hover:bg-zinc-800/80",
                        )}
                        onClick={() => {
                          onTypeChange("");
                          setIsTypeMenuOpen(false);
                        }}
                      >
                        <span className="truncate">All Types</span>
                      </button>
                      {NODE_TYPE_OPTIONS.map((nodeType) => (
                        <button
                          key={nodeType}
                          type="button"
                          className={cn(
                            "flex w-full items-center rounded-md px-2.5 py-2 text-left text-sm transition-colors duration-200",
                            nodeType === selectedType
                              ? "bg-zinc-200/70 text-zinc-900 dark:bg-zinc-800 dark:text-zinc-100"
                              : "text-zinc-700 hover:bg-zinc-200/50 dark:text-zinc-300 dark:hover:bg-zinc-800/80",
                          )}
                          onClick={() => {
                            onTypeChange(nodeType);
                            setIsTypeMenuOpen(false);
                          }}
                        >
                          <span className="truncate">{nodeType}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            </div>

            <div
              className={cn(
                "minimal-scrollbar min-h-0 flex-1 space-y-2 overflow-y-auto pr-1 transition-opacity duration-200",
                isUpdatingProcessLimit && "opacity-70",
              )}
            >
              {processes.length === 0 ? (
                <p className="rounded-xl border border-dashed border-zinc-300/60 bg-zinc-50/40 p-3 text-sm text-zinc-500 dark:border-white/10 dark:bg-zinc-900/30 dark:text-zinc-400">
                  No matching nodes found.
                </p>
              ) : (
                processes.map((process) => {
                  const isSelected = contextNodeIdSet.has(process.pk);
                  const canOpenDetail = isProcessLikeNode(process);
                  const typeIndicator = getNodeTypeIndicator(process);
                  const titleText = getNodeTitleText(process);
                  const metadata = getNodeMetadata(process);
                  const activateCard = () => {
                    onAddContextNode(process);
                  };
                  return (
                    <div
                      key={`${process.pk}-${process.state}-${process.formula ?? ""}`}
                      role="button"
                      tabIndex={0}
                      onClick={activateCard}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          activateCard();
                        }
                      }}
                      className={cn(
                        "rounded-xl border px-3 py-2.5 transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-300 dark:focus-visible:ring-zinc-700",
                        "cursor-pointer border-zinc-200/75 bg-white/60 hover:border-zinc-300/85 hover:bg-white/75 dark:border-zinc-800/80 dark:bg-zinc-900/45 dark:hover:border-zinc-700/85 dark:hover:bg-zinc-900/55",
                        isSelected
                          ? "border-zinc-300/90 bg-zinc-100/70 shadow-[0_10px_22px_-20px_rgba(15,23,42,0.65)] dark:border-zinc-700/90 dark:bg-zinc-800/55"
                          : null,
                      )}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="min-w-0">
                          <p className="flex items-center gap-1.5 truncate font-sans text-sm font-semibold tracking-tight text-zinc-900 dark:text-zinc-100">
                            <span role="img" aria-label={typeIndicator.iconLabel} className="shrink-0">
                              {typeIndicator.icon}
                            </span>
                            <span className="truncate">
                              {titleText}{" "}
                              <span className="font-mono text-[11px] text-zinc-500 dark:text-zinc-400">({process.pk})</span>
                            </span>
                          </p>
                        </div>

                        <div className="min-w-0 text-right">
                          {metadata.processStatus ? (
                            <p className={cn("text-[11px] font-semibold tracking-tight", metadata.processStatus.className)}>
                              {metadata.processStatus.label}
                            </p>
                          ) : null}
                          {metadata.lines.map((line, index) => (
                            <p
                              key={`${process.pk}-meta-${index}`}
                              className={cn(
                                "truncate text-[11px] tracking-tight text-zinc-500 dark:text-zinc-400",
                                index === 0 && "text-zinc-700 dark:text-zinc-300",
                              )}
                            >
                              {line}
                            </p>
                          ))}
                          <div className="mt-0.5 flex items-center justify-end gap-2">
                            {canOpenDetail ? (
                              <button
                                type="button"
                                className="text-[10px] uppercase tracking-[0.08em] text-zinc-500 underline decoration-zinc-300 underline-offset-2 transition-colors duration-150 hover:text-zinc-800 dark:text-zinc-400 dark:decoration-zinc-700 dark:hover:text-zinc-200"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  onOpenProcessDetail(process);
                                }}
                              >
                                Inspect
                              </button>
                            ) : null}
                            {isSelected ? <p className="text-[10px] uppercase tracking-[0.08em] text-zinc-500 dark:text-zinc-400">Selected</p> : null}
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      </Panel>
    </aside>
  );
}
