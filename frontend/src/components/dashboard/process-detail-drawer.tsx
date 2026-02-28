import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, CircleDot, GitBranch, Loader2, X } from "lucide-react";

import { getProcessDetail, getProcessLogs } from "@/lib/api";
import { cn } from "@/lib/utils";
import type {
  FocusNode,
  ProcessDetailResponse,
  ProcessItem,
  ProcessLogsResponse,
  ProcessNodeLink,
  ProcessTreeNode,
} from "@/types/aiida";

type ProcessDetailDrawerProps = {
  process: ProcessItem | null;
  onClose: () => void;
  onAddContextNode: (node: FocusNode) => void;
};

type ProcessTreeNodeViewProps = {
  label: string;
  node: ProcessTreeNode;
  depth?: number;
  onAddContextNode: (node: FocusNode) => void;
};

type NodeLinksBlockProps = {
  title: string;
  links: ProcessNodeLink[];
  onAddContextNode: (node: FocusNode) => void;
  emptyText: string;
  compact?: boolean;
  showTitle?: boolean;
};

type NodeLinksAccordionProps = NodeLinksBlockProps & {
  defaultOpen?: boolean;
};

const LOG_SNIPPET_LINE_LIMIT = 80;
const RUNNING_STATES = new Set(["running", "created", "waiting"]);
const FINISHED_STATES = new Set(["finished", "success", "completed", "ok"]);
const FAILED_STATES = new Set(["failed", "excepted", "killed", "error"]);
const WORKCHAIN_NODE_HINTS = ["workchain", "workflow"];

type StatusTone = {
  dotClassName: string;
  textClassName: string;
};

function normalizeState(state: string | null | undefined): string {
  return String(state || "unknown").trim().replace(/_/g, " ").toLowerCase();
}

function toDisplayStatus(state: string | null | undefined): string {
  const normalized = normalizeState(state);
  if (!normalized) {
    return "Unknown";
  }
  return normalized
    .split(" ")
    .filter(Boolean)
    .map((word) => `${word.charAt(0).toUpperCase()}${word.slice(1)}`)
    .join(" ");
}

function getStatusTone(state: string | null | undefined): StatusTone {
  const normalized = normalizeState(state);
  if (FAILED_STATES.has(normalized)) {
    return {
      dotClassName: "bg-rose-500",
      textClassName: "text-rose-600 dark:text-rose-300",
    };
  }
  if (RUNNING_STATES.has(normalized)) {
    return {
      dotClassName: "bg-blue-500",
      textClassName: "text-blue-600 dark:text-blue-300",
    };
  }
  if (FINISHED_STATES.has(normalized)) {
    return {
      dotClassName: "bg-emerald-500",
      textClassName: "text-emerald-600 dark:text-emerald-300",
    };
  }
  return {
    dotClassName: "bg-zinc-400 dark:bg-zinc-500",
    textClassName: "text-zinc-500 dark:text-zinc-400",
  };
}

function parseDate(value: unknown): Date | null {
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value;
  }
  if (typeof value === "string" || typeof value === "number") {
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }
  return null;
}

function formatSeconds(totalSeconds: number): string {
  const safeSeconds = Math.max(0, Math.round(totalSeconds));
  const hours = Math.floor(safeSeconds / 3600);
  const minutes = Math.floor((safeSeconds % 3600) / 60);
  const seconds = safeSeconds % 60;

  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  if (minutes > 0) {
    return `${minutes}m ${seconds}s`;
  }
  return `${seconds}s`;
}

function durationFromValue(raw: unknown): string | null {
  if (typeof raw === "number" && Number.isFinite(raw)) {
    return formatSeconds(raw);
  }
  if (typeof raw === "string" && raw.trim()) {
    return raw.trim();
  }
  return null;
}

function getDurationLabel(node: ProcessTreeNode): string {
  const payload = node as Record<string, unknown>;
  const directDuration = durationFromValue(payload.duration ?? payload.elapsed ?? payload.runtime ?? payload.wall_time ?? payload.wallclock);
  if (directDuration) {
    return directDuration;
  }

  const start = parseDate(payload.ctime ?? payload.created_at ?? payload.started_at ?? payload.start_time);
  const end = parseDate(payload.mtime ?? payload.updated_at ?? payload.finished_at ?? payload.end_time);
  if (start && end && end.getTime() >= start.getTime()) {
    return formatSeconds((end.getTime() - start.getTime()) / 1000);
  }
  if (start && RUNNING_STATES.has(normalizeState(node.state))) {
    return `${formatSeconds((Date.now() - start.getTime()) / 1000)}+`;
  }
  return "—";
}

function isWorkChainType(nodeType: string | null | undefined): boolean {
  const normalized = String(nodeType || "").trim().toLowerCase();
  if (!normalized) {
    return false;
  }
  return WORKCHAIN_NODE_HINTS.some((hint) => normalized.includes(hint));
}

function linkToContextNode(link: ProcessNodeLink): FocusNode {
  const baseLabel = String(link.link_label || "").trim();
  return {
    pk: link.pk,
    label: baseLabel || `${link.node_type} #${link.pk}`,
    formula: null,
    node_type: link.node_type || "Node",
  };
}

function iconForNodeType(nodeType: string): { icon: string; ariaLabel: string } {
  if (nodeType === "StructureData") {
    return { icon: "💎", ariaLabel: "Crystal" };
  }
  if (nodeType === "ProcessNode" || nodeType === "WorkChainNode" || nodeType === "CalcJobNode" || nodeType === "CalcFunctionNode") {
    return { icon: "⚡", ariaLabel: "Activity" };
  }
  if (nodeType === "BandsData" || nodeType === "XyData") {
    return { icon: "📈", ariaLabel: "Chart" };
  }
  if (nodeType === "Dict" || nodeType === "ArrayData") {
    return { icon: "📑", ariaLabel: "Data" };
  }
  if (nodeType === "RemoteData" || nodeType === "FolderData") {
    return { icon: "📁", ariaLabel: "Folder" };
  }
  return { icon: "📦", ariaLabel: "Node" };
}

function formatLinkPreview(link: ProcessNodeLink): string | null {
  const preview = link.preview;
  if (!preview) {
    return null;
  }
  if (preview.remote_path || preview.computer_name) {
    const pieces = [preview.remote_path, preview.computer_name].filter(Boolean);
    return pieces.join(" · ");
  }
  if (preview.filenames && preview.filenames.length > 0) {
    return preview.filenames.slice(0, 5).join(", ");
  }
  if (preview.x_label || (preview.y_arrays && preview.y_arrays.length > 0)) {
    const yText = (preview.y_arrays || [])
      .slice(0, 3)
      .map((entry) => `${entry.label}${entry.length !== null ? `(${entry.length})` : ""}`)
      .join(", ");
    const xText = preview.x_label ? `${preview.x_label}${preview.x_length !== null ? `(${preview.x_length})` : ""}` : null;
    return [xText ? `x:${xText}` : null, yText ? `y:${yText}` : null].filter(Boolean).join(" · ") || null;
  }
  return null;
}

function NodeLinkRow({ link, onAddContextNode, compact = false }: { link: ProcessNodeLink; onAddContextNode: (node: FocusNode) => void; compact?: boolean }) {
  const previewText = formatLinkPreview(link);
  const nodeType = String(link.node_type || "Node");
  const typeIndicator = iconForNodeType(nodeType);
  const linkLabel = String(link.link_label || "").trim() || `link_${link.pk}`;
  return (
    <div
      className={cn(
        "group flex w-full items-start justify-between gap-3 rounded-md px-2 py-1.5 text-left font-sans tracking-tight transition-colors duration-150 hover:bg-zinc-100/85 dark:hover:bg-zinc-900/70",
        compact && "py-1",
      )}
    >
      <div className="min-w-0 flex items-start gap-1.5">
        <span role="img" aria-label={typeIndicator.ariaLabel} className="mt-[1px] shrink-0">
          {typeIndicator.icon}
        </span>
        <p className={cn("min-w-0 truncate text-xs text-zinc-700 dark:text-zinc-300", compact && "text-[11px]")}>
          <span className="font-medium">{linkLabel}</span>
          <span>: {nodeType}</span>
          <span className="text-zinc-500 dark:text-zinc-400"> (</span>
          <button
            type="button"
            className="font-mono text-zinc-500 underline decoration-zinc-300 underline-offset-2 transition-colors duration-150 hover:text-zinc-700 dark:text-zinc-400 dark:decoration-zinc-700 dark:hover:text-zinc-200"
            onClick={() => onAddContextNode(linkToContextNode(link))}
            aria-label={`Add node ${link.pk} to context`}
          >
            #{link.pk}
          </button>
          <span className="text-zinc-500 dark:text-zinc-400">)</span>
        </p>
      </div>
      {previewText ? (
        <span className={cn("max-w-[52%] truncate text-zinc-500 dark:text-zinc-400", compact ? "text-[10px]" : "text-[11px]")}>{previewText}</span>
      ) : null}
    </div>
  );
}

function NodeLinksBlock({
  title,
  links,
  onAddContextNode,
  emptyText,
  compact = false,
  showTitle = true,
}: NodeLinksBlockProps) {
  return (
    <section className="font-sans tracking-tight">
      {showTitle ? (
        <h4 className={cn("mb-1 text-xs font-semibold tracking-tight text-zinc-700 dark:text-zinc-300", compact && "text-[10px] uppercase tracking-[0.08em] text-zinc-500 dark:text-zinc-400")}>
          {title}
        </h4>
      ) : null}
      {links.length === 0 ? (
        <p className={cn("px-2 py-1 text-xs text-zinc-500 dark:text-zinc-400", compact && "text-[11px]")}>{emptyText}</p>
      ) : (
        <div className="space-y-0.5">
          {links.map((link, index) => (
            <NodeLinkRow
              key={`${title}-${link.pk}-${link.link_label}-${index}`}
              link={link}
              onAddContextNode={onAddContextNode}
              compact={compact}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function NodeLinksAccordion({
  title,
  links,
  onAddContextNode,
  emptyText,
  compact = false,
  defaultOpen = false,
}: NodeLinksAccordionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <section className="font-sans tracking-tight">
      <button
        type="button"
        className="group flex w-full items-center justify-between rounded-md px-1.5 py-1 text-left transition-colors duration-150 hover:bg-zinc-100/85 dark:hover:bg-zinc-900/70"
        onClick={() => setIsOpen((open) => !open)}
        aria-label={`${isOpen ? "Collapse" : "Expand"} ${title.toLowerCase()}`}
      >
        <span className={cn("text-sm font-semibold tracking-tight text-zinc-900 dark:text-zinc-100", compact && "text-xs")}>
          {title}
        </span>
        <ChevronDown
          className={cn(
            "h-3.5 w-3.5 text-zinc-500 transition-transform duration-200 group-hover:text-zinc-700 dark:text-zinc-400 dark:group-hover:text-zinc-200",
            isOpen ? "rotate-180" : "rotate-90",
          )}
        />
      </button>

      {isOpen ? (
        <div className="ml-3 mt-1 border-l border-zinc-200/80 pl-3 dark:border-zinc-800/80">
          <NodeLinksBlock
            title={title}
            links={links}
            onAddContextNode={onAddContextNode}
            emptyText={emptyText}
            compact={compact}
            showTitle={false}
          />
        </div>
      ) : null}
    </section>
  );
}

function ProcessTreeNodeView({ label, node, depth = 0, onAddContextNode }: ProcessTreeNodeViewProps) {
  const children = Object.entries(node.children || {});
  const status = toDisplayStatus(node.state);
  const statusTone = getStatusTone(node.state);
  const durationLabel = getDurationLabel(node);
  const nodeLabel = node.process_label || label || "Process";
  const RowIcon = children.length > 0 ? GitBranch : CircleDot;
  const inputLinks = node.inputs ?? [];
  const outputLinks = node.outputs ?? [];
  const hasLinks = inputLinks.length > 0 || outputLinks.length > 0;
  const [isLinksOpen, setIsLinksOpen] = useState(false);

  return (
    <div className={cn("space-y-1", depth > 0 && "ml-3 border-l border-zinc-200/80 pl-4 dark:border-zinc-800/80")}>
      <div className="group flex items-center justify-between gap-3 rounded-md px-2 py-1.5 transition-colors duration-200 hover:bg-zinc-100/80 dark:hover:bg-zinc-900/65">
        <div className="min-w-0 flex items-center gap-2">
          <RowIcon className="h-3.5 w-3.5 shrink-0 text-zinc-500 dark:text-zinc-400" />
          <p className="truncate text-sm text-zinc-900 dark:text-zinc-100">
            <span className="font-medium">{nodeLabel}</span>{" "}
            <span className="font-mono text-[11px] text-zinc-500 dark:text-zinc-400">({node.pk})</span>
          </p>
        </div>
        <div className="shrink-0 flex items-center gap-3">
          {hasLinks ? (
            <button
              type="button"
              className="inline-flex items-center gap-1 text-[10px] uppercase tracking-[0.08em] text-zinc-500 transition-colors hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200"
              onClick={() => setIsLinksOpen((open) => !open)}
              aria-label={isLinksOpen ? "Hide node links" : "Show node links"}
            >
              <ChevronDown className={cn("h-3 w-3 transition-transform duration-200", isLinksOpen && "rotate-180")} />
              LINKS
            </button>
          ) : null}
          <span className={cn("inline-flex items-center gap-1 text-[11px] font-medium", statusTone.textClassName)}>
            <span className={cn("h-1.5 w-1.5 rounded-full", statusTone.dotClassName)} />
            {status}
          </span>
          <span className="font-mono text-[11px] text-zinc-500 dark:text-zinc-400">{durationLabel}</span>
        </div>
      </div>

      {hasLinks && isLinksOpen ? (
        <div className="ml-5 space-y-2">
          <NodeLinksBlock
            title="Inputs"
            links={inputLinks}
            onAddContextNode={onAddContextNode}
            emptyText="No direct inputs."
            compact
          />
          <NodeLinksBlock
            title="Outputs"
            links={outputLinks}
            onAddContextNode={onAddContextNode}
            emptyText="No direct outputs."
            compact
          />
        </div>
      ) : null}

      {children.length > 0 ? (
        <div className="space-y-1">
          {children.map(([childLabel, child]) => (
            <ProcessTreeNodeView
              key={`${childLabel}-${child.pk}`}
              label={childLabel}
              node={child}
              depth={depth + 1}
              onAddContextNode={onAddContextNode}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function renderLogs(logs: ProcessLogsResponse | undefined) {
  const lines = logs?.lines ?? [];
  if (!logs) {
    return (
      <p className="text-sm text-zinc-500 dark:text-zinc-400">No execution logs are available for this process yet.</p>
    );
  }
  if (lines.length === 0) {
    return <p className="text-sm text-zinc-500 dark:text-zinc-400">{logs.text || "No logs found."}</p>;
  }
  const snippet = lines.slice(-LOG_SNIPPET_LINE_LIMIT);
  const hasMore = lines.length > snippet.length;
  return (
    <div className="space-y-2">
      <p className="text-xs text-zinc-500 dark:text-zinc-400">
        Latest {snippet.length} line{snippet.length === 1 ? "" : "s"}
        {hasMore ? ` of ${lines.length}` : ""}.
      </p>
      <pre className="max-h-[18rem] overflow-auto rounded-lg border border-zinc-200/80 bg-zinc-50/70 p-3 text-xs leading-5 text-zinc-700 dark:border-zinc-800 dark:bg-zinc-900/65 dark:text-zinc-200">
        {snippet.join("\n")}
      </pre>
    </div>
  );
}

function renderProcessTree(
  detail: ProcessDetailResponse | undefined,
  onAddContextNode: (node: FocusNode) => void,
) {
  const treeRoot = detail?.workchain?.provenance_tree;
  if (treeRoot) {
    return <ProcessTreeNodeView label="root" node={treeRoot} onAddContextNode={onAddContextNode} />;
  }

  const summary = detail?.summary;
  if (!summary?.pk) {
    return (
      <p className="text-sm text-zinc-500 dark:text-zinc-400">Process tree is not available for this node type.</p>
    );
  }

  const summaryNode: ProcessTreeNode = {
    pk: summary.pk,
    process_label: summary.type || "ProcessNode",
    state: summary.state || "unknown",
    exit_status: summary.exit_status ?? null,
    inputs: detail?.inputs ?? [],
    outputs: detail?.outputs ?? [],
    children: {},
  };

  return (
    <div className="space-y-1">
      <ProcessTreeNodeView label="root" node={summaryNode} onAddContextNode={onAddContextNode} />
      <p className="pl-2 text-xs text-zinc-500 dark:text-zinc-400">
        No nested provenance tree returned by worker.
      </p>
    </div>
  );
}

export function ProcessDetailDrawer({ process, onClose, onAddContextNode }: ProcessDetailDrawerProps) {
  const isOpen = process !== null;

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [isOpen, onClose]);

  const detailQuery = useQuery({
    queryKey: ["process-detail", process?.pk],
    queryFn: () => getProcessDetail(process!.pk),
    enabled: Boolean(process?.pk),
    staleTime: 4_000,
  });

  const logsQuery = useQuery({
    queryKey: ["process-logs", process?.pk],
    queryFn: () => getProcessLogs(process!.pk),
    enabled: Boolean(process?.pk),
    staleTime: 4_000,
  });

  const summaryState = detailQuery.data?.summary?.state ?? process?.process_state ?? process?.state ?? "unknown";
  const detailInputs = detailQuery.data?.inputs ?? [];
  const detailOutputs = detailQuery.data?.outputs ?? [];
  const showProcessTree =
    isWorkChainType(process?.node_type) ||
    isWorkChainType(detailQuery.data?.summary?.type) ||
    Boolean(detailQuery.data?.workchain?.provenance_tree);
  return (
    <div className={cn("fixed inset-0 z-50 transition-opacity duration-200", isOpen ? "pointer-events-auto" : "pointer-events-none")}>
      <div
        className={cn("absolute inset-0 bg-zinc-950/45 transition-opacity duration-200", isOpen ? "opacity-100" : "opacity-0")}
        onClick={onClose}
        aria-hidden
      />
      <aside
        className={cn(
          "absolute right-0 top-0 h-full w-full max-w-2xl transform border-l border-zinc-200/80 bg-white shadow-2xl transition-transform duration-300 dark:border-zinc-800 dark:bg-zinc-950",
          isOpen ? "translate-x-0" : "translate-x-full",
        )}
        role="dialog"
        aria-modal="true"
        aria-label="Process detail drawer"
      >
        <div className="flex h-full min-h-0 flex-col">
          <header className="flex items-start justify-between border-b border-zinc-200/70 px-5 py-4 dark:border-zinc-800">
            <div className="min-w-0">
              <p className="text-xs uppercase tracking-[0.16em] text-zinc-500 dark:text-zinc-400">Process Detail</p>
              <h2 className="mt-1 truncate text-lg font-semibold text-zinc-900 dark:text-zinc-100">
                {process?.label || "Unknown Process"}
              </h2>
              <p className="mt-1 text-xs text-zinc-600 dark:text-zinc-300">
                #{process?.pk ?? "N/A"} · {toDisplayStatus(summaryState)}
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-zinc-500 transition-colors duration-200 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-900 dark:hover:text-zinc-100"
              aria-label="Close process detail drawer"
            >
              <X className="h-4 w-4" />
            </button>
          </header>

          <div className="minimal-scrollbar min-h-0 flex-1 space-y-5 overflow-y-auto px-5 py-4">
            {showProcessTree ? (
              <section>
                <div className="mb-2 flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Process Tree</h3>
                  {detailQuery.isFetching ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin text-zinc-400 dark:text-zinc-500" />
                  ) : null}
                </div>
                {detailQuery.isError ? (
                  <p className="text-sm text-rose-500">Failed to load process tree.</p>
                ) : detailQuery.isPending ? (
                  <p className="text-sm text-zinc-500 dark:text-zinc-400">Loading process tree...</p>
                ) : (
                  renderProcessTree(detailQuery.data, onAddContextNode)
                )}
              </section>
            ) : (
              <section className="space-y-2">
                <div className="mb-1 flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Inputs & Outputs</h3>
                  {detailQuery.isFetching ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin text-zinc-400 dark:text-zinc-500" />
                  ) : null}
                </div>
                {detailQuery.isError ? (
                  <p className="text-sm text-rose-500">Failed to load node links.</p>
                ) : detailQuery.isPending ? (
                  <p className="text-sm text-zinc-500 dark:text-zinc-400">Loading inputs and outputs...</p>
                ) : (
                  <div className="space-y-2">
                    <NodeLinksAccordion
                      key={`calc-inputs-${process?.pk ?? "none"}`}
                      title="Inputs"
                      links={detailInputs}
                      onAddContextNode={onAddContextNode}
                      emptyText="No incoming links reported."
                      defaultOpen
                    />
                    <NodeLinksAccordion
                      key={`calc-outputs-${process?.pk ?? "none"}`}
                      title="Outputs"
                      links={detailOutputs}
                      onAddContextNode={onAddContextNode}
                      emptyText="No outgoing links reported."
                      defaultOpen
                    />
                  </div>
                )}
              </section>
            )}

            <section>
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Execution Logs</h3>
                {logsQuery.isFetching ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-zinc-400 dark:text-zinc-500" />
                ) : null}
              </div>
              {logsQuery.isError ? (
                <p className="text-sm text-rose-500">Failed to load execution logs.</p>
              ) : logsQuery.isPending ? (
                <p className="text-sm text-zinc-500 dark:text-zinc-400">Loading execution logs...</p>
              ) : (
                renderLogs(logsQuery.data ?? detailQuery.data?.logs)
              )}
            </section>
          </div>
        </div>
      </aside>
    </div>
  );
}
