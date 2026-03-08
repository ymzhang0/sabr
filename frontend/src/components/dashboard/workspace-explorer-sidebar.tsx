import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { getChatProjectWorkspace } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { ChatProject, ChatProjectWorkspaceResponse, WorkspaceEntry } from "@/types/aiida";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import {
  ChevronDown,
  ChevronRight,
  FileCode2,
  FileText,
  Folder,
  FolderOpen,
  Image as ImageIcon,
  Loader2,
  RefreshCw,
} from "lucide-react";

type WorkspaceExplorerSidebarProps = {
  project: ChatProject | null;
};

type WorkspaceFilter = "all" | "code" | "images";

const CODE_EXTENSIONS = new Set([
  "c",
  "cc",
  "cpp",
  "css",
  "cu",
  "csv",
  "dat",
  "html",
  "in",
  "ipynb",
  "java",
  "js",
  "json",
  "md",
  "out",
  "py",
  "sh",
  "toml",
  "ts",
  "tsx",
  "txt",
  "xml",
  "yaml",
  "yml",
]);

const IMAGE_EXTENSIONS = new Set(["bmp", "gif", "jpeg", "jpg", "pdf", "png", "svg", "tif", "tiff", "webp"]);

function normalizeRelativePath(value?: string | null): string {
  return String(value ?? "")
    .trim()
    .replace(/^\/+/, "")
    .replace(/\/+$/, "");
}

function formatBytes(value: number | null): string {
  if (value === null || !Number.isFinite(value) || value < 0) {
    return "file";
  }
  if (value < 1024) {
    return `${value} B`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  if (value < 1024 * 1024 * 1024) {
    return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  }
  return `${(value / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

function getFileExtension(name: string): string {
  const parts = name.toLowerCase().split(".");
  return parts.length > 1 ? parts.at(-1) ?? "" : "";
}

function matchesFilter(entry: WorkspaceEntry, filter: WorkspaceFilter): boolean {
  if (entry.is_dir || filter === "all") {
    return true;
  }
  const extension = getFileExtension(entry.name);
  if (filter === "code") {
    return CODE_EXTENSIONS.has(extension);
  }
  if (filter === "images") {
    return IMAGE_EXTENSIONS.has(extension);
  }
  return true;
}

function sortEntries(entries: WorkspaceEntry[]): WorkspaceEntry[] {
  return [...entries].sort((left, right) => {
    if (left.is_dir !== right.is_dir) {
      return left.is_dir ? -1 : 1;
    }
    return left.name.localeCompare(right.name, undefined, { numeric: true, sensitivity: "base" });
  });
}

function WorkspaceFileIcon({ entry }: { entry: WorkspaceEntry }) {
  if (entry.is_dir) {
    return <Folder className="h-4 w-4" />;
  }
  const extension = getFileExtension(entry.name);
  if (IMAGE_EXTENSIONS.has(extension)) {
    return <ImageIcon className="h-4 w-4" />;
  }
  if (CODE_EXTENSIONS.has(extension)) {
    return <FileCode2 className="h-4 w-4" />;
  }
  return <FileText className="h-4 w-4" />;
}

export function WorkspaceExplorerSidebar({ project }: WorkspaceExplorerSidebarProps) {
  const [workspaceByPath, setWorkspaceByPath] = useState<Record<string, ChatProjectWorkspaceResponse>>({});
  const [expandedPaths, setExpandedPaths] = useState<string[]>([]);
  const [loadingPaths, setLoadingPaths] = useState<string[]>([]);
  const [failedPaths, setFailedPaths] = useState<Record<string, string>>({});
  const [filter, setFilter] = useState<WorkspaceFilter>("all");
  const activeProjectIdRef = useRef<string | null>(null);
  const workspaceByPathRef = useRef<Record<string, ChatProjectWorkspaceResponse>>({});
  const loadingPathSetRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    activeProjectIdRef.current = project?.id ?? null;
  }, [project?.id]);

  useEffect(() => {
    workspaceByPathRef.current = workspaceByPath;
  }, [workspaceByPath]);

  const loadDirectory = useCallback(
    async (relativePath?: string, force = false) => {
      if (!project?.id) {
        return;
      }

      const normalizedPath = normalizeRelativePath(relativePath);
      if (!force && workspaceByPathRef.current[normalizedPath]) {
        return;
      }
      if (loadingPathSetRef.current.has(normalizedPath)) {
        return;
      }

      loadingPathSetRef.current.add(normalizedPath);
      setLoadingPaths((current) => (current.includes(normalizedPath) ? current : [...current, normalizedPath]));
      setFailedPaths((current) => {
        if (!current[normalizedPath]) {
          return current;
        }
        const next = { ...current };
        delete next[normalizedPath];
        return next;
      });

      try {
        const response = await getChatProjectWorkspace(project.id, normalizedPath || undefined);
        if (activeProjectIdRef.current !== project.id) {
          return;
        }
        const responsePath = normalizeRelativePath(response.relative_path);
        setWorkspaceByPath((current) => ({
          ...current,
          [responsePath]: response,
        }));
      } catch (error) {
        console.error("Failed to load workspace directory", error);
        if (activeProjectIdRef.current !== project.id) {
          return;
        }
        setFailedPaths((current) => ({
          ...current,
          [normalizedPath]: "Failed to load directory.",
        }));
      } finally {
        loadingPathSetRef.current.delete(normalizedPath);
        setLoadingPaths((current) => current.filter((path) => path !== normalizedPath));
      }
    },
    [project?.id],
  );

  useEffect(() => {
    workspaceByPathRef.current = {};
    loadingPathSetRef.current.clear();
    setWorkspaceByPath({});
    setLoadingPaths([]);
    setFailedPaths({});
    setExpandedPaths(project ? [""] : []);
    if (!project?.id) {
      return;
    }
    void loadDirectory("", true);
  }, [loadDirectory, project?.id]);

  const toggleDirectory = useCallback(
    (relativePath: string) => {
      const normalizedPath = normalizeRelativePath(relativePath);
      const isExpanded = expandedPaths.includes(normalizedPath);
      if (isExpanded) {
        setExpandedPaths((current) => current.filter((path) => path !== normalizedPath));
        return;
      }
      setExpandedPaths((current) => [...current, normalizedPath]);
      void loadDirectory(normalizedPath);
    },
    [expandedPaths, loadDirectory],
  );

  const rootWorkspace = workspaceByPath[""] ?? null;
  const visibleRootEntries = useMemo(
    () => sortEntries(rootWorkspace?.entries ?? []).filter((entry) => matchesFilter(entry, filter)),
    [filter, rootWorkspace?.entries],
  );

  const renderEntries = useCallback(
    (entries: WorkspaceEntry[], depth: number) =>
      sortEntries(entries)
        .filter((entry) => matchesFilter(entry, filter))
        .map((entry) => {
          const normalizedPath = normalizeRelativePath(entry.relative_path);
          const isExpanded = expandedPaths.includes(normalizedPath);
          const childWorkspace = workspaceByPath[normalizedPath];
          const isLoading = loadingPaths.includes(normalizedPath);
          const hasError = failedPaths[normalizedPath];

          if (!entry.is_dir) {
            return (
              <div
                key={entry.relative_path}
                className="flex items-center justify-between gap-3 rounded-xl px-3 py-2 text-left transition-colors hover:bg-zinc-100/80 dark:hover:bg-zinc-900/70"
                style={{ paddingLeft: `${12 + depth * 18}px` }}
              >
                <div className="min-w-0 flex items-center gap-2">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-zinc-100 text-zinc-500 dark:bg-zinc-900 dark:text-zinc-400">
                    <WorkspaceFileIcon entry={entry} />
                  </span>
                  <div className="min-w-0">
                    <p className="truncate text-sm text-zinc-800 dark:text-zinc-100">{entry.name}</p>
                    <p className="truncate text-[11px] text-zinc-400 dark:text-zinc-500">{entry.relative_path}</p>
                  </div>
                </div>
                <span className="shrink-0 text-[11px] text-zinc-400 dark:text-zinc-500">{formatBytes(entry.size)}</span>
              </div>
            );
          }

          return (
            <div key={entry.relative_path} className="space-y-1">
              <button
                type="button"
                className={cn(
                  "flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2 text-left transition-colors hover:bg-blue-50/70 dark:hover:bg-blue-950/20",
                  isExpanded && "bg-blue-50/50 dark:bg-blue-950/10",
                )}
                style={{ paddingLeft: `${12 + depth * 18}px` }}
                onClick={() => toggleDirectory(normalizedPath)}
              >
                <div className="min-w-0 flex items-center gap-2">
                  <span className="text-zinc-400 dark:text-zinc-500">
                    {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                  </span>
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-blue-600 dark:bg-blue-950/30 dark:text-blue-300">
                    {isExpanded ? <FolderOpen className="h-4 w-4" /> : <Folder className="h-4 w-4" />}
                  </span>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-zinc-900 dark:text-zinc-100">{entry.name}</p>
                    <p className="truncate text-[11px] text-zinc-400 dark:text-zinc-500">{entry.relative_path}</p>
                  </div>
                </div>
                {isLoading ? <Loader2 className="h-4 w-4 shrink-0 animate-spin text-zinc-400 dark:text-zinc-500" /> : null}
              </button>

              {isExpanded && hasError ? (
                <div
                  className="flex items-center gap-2 rounded-lg border border-dashed border-red-200/80 bg-red-50/60 px-3 py-2 text-xs text-red-600 dark:border-red-900/80 dark:bg-red-950/10 dark:text-red-300"
                  style={{ marginLeft: `${32 + depth * 18}px` }}
                >
                  <span className="min-w-0 flex-1 truncate">{hasError}</span>
                  <Button
                    variant="ghost"
                    className="h-7 rounded-lg px-2 text-[11px]"
                    onClick={() => {
                      void loadDirectory(normalizedPath, true);
                    }}
                  >
                    Retry
                  </Button>
                </div>
              ) : null}

              {isExpanded && childWorkspace ? renderEntries(childWorkspace.entries, depth + 1) : null}
            </div>
          );
        }),
    [expandedPaths, failedPaths, filter, loadDirectory, loadingPaths, workspaceByPath],
  );

  const rootPathLabel = rootWorkspace?.workspace_path ?? project?.root_path ?? "";
  const rootIsLoading = loadingPaths.includes("");
  const rootError = failedPaths[""];

  return (
    <aside className="flex h-full min-h-0 w-full flex-col gap-2 font-sans tracking-tight">
      <header className="flex items-center justify-between px-2.5 pt-2">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-zinc-900 dark:text-zinc-100">Workspace Explorer</h1>
          <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">
            {project ? project.name : "Select a project to browse its workspace"}
          </p>
        </div>
        {project ? (
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 rounded-lg"
            onClick={() => {
              void loadDirectory("", true);
            }}
            aria-label="Refresh workspace root"
          >
            {rootIsLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
          </Button>
        ) : null}
      </header>

      <Panel className="flex min-h-0 flex-1 flex-col gap-3 border-zinc-100/90 p-3 dark:border-zinc-800/80">
        {!project ? (
          <div className="flex h-full min-h-0 items-center justify-center rounded-2xl border border-dashed border-zinc-300/70 bg-zinc-50/50 px-4 text-center text-sm text-zinc-500 dark:border-zinc-700/80 dark:bg-zinc-900/30 dark:text-zinc-400">
            Open a project from the Projects view, then its workspace tree will stay here.
          </div>
        ) : (
          <>
            <div className="rounded-2xl border border-zinc-200/70 bg-zinc-50/75 p-3 dark:border-zinc-800/80 dark:bg-zinc-900/45">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-zinc-500 dark:text-zinc-400">
                    Current Project
                  </p>
                  <h2 className="mt-1 truncate text-sm font-semibold text-zinc-900 dark:text-zinc-100">{project.name}</h2>
                </div>
                <div className="flex items-center gap-1 rounded-xl bg-white/80 p-1 dark:bg-zinc-950/60">
                  {(["all", "code", "images"] as const).map((option) => (
                    <button
                      key={option}
                      type="button"
                      className={cn(
                        "rounded-lg px-2.5 py-1 text-[11px] font-medium transition-colors",
                        filter === option
                          ? "bg-blue-600 text-white"
                          : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800",
                      )}
                      onClick={() => setFilter(option)}
                    >
                      {option === "all" ? "All" : option === "code" ? "Code" : "Images"}
                    </button>
                  ))}
                </div>
              </div>
              <p className="mt-2 break-all text-[11px] text-zinc-500 dark:text-zinc-400">{rootPathLabel || "Workspace path unavailable."}</p>
            </div>

            <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border border-zinc-200/75 bg-white/75 dark:border-zinc-800/80 dark:bg-zinc-950/35">
              <div className="flex items-center justify-between gap-3 border-b border-zinc-200/70 px-4 py-3 dark:border-zinc-800">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.14em] text-zinc-500 dark:text-zinc-400">Files</p>
                  <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                    {rootWorkspace ? `${visibleRootEntries.length} visible items at root` : "Loading workspace tree"}
                  </p>
                </div>
                <span className="rounded-full bg-zinc-100 px-2.5 py-1 text-[11px] font-medium text-zinc-600 dark:bg-zinc-900 dark:text-zinc-300">
                  {filter === "all" ? "All files" : filter === "code" ? "Code only" : "Images only"}
                </span>
              </div>

              <div className="minimal-scrollbar min-h-0 flex-1 overflow-y-auto p-3">
                {rootIsLoading && !rootWorkspace ? (
                  <div className="flex min-h-40 items-center justify-center gap-2 text-sm text-zinc-500 dark:text-zinc-400">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Loading workspace…
                  </div>
                ) : null}

                {rootError && !rootWorkspace ? (
                  <div className="space-y-3 rounded-2xl border border-dashed border-red-200/80 bg-red-50/70 p-4 text-sm text-red-700 dark:border-red-900/80 dark:bg-red-950/15 dark:text-red-300">
                    <p>{rootError}</p>
                    <div>
                      <Button
                        variant="ghost"
                        className="h-8 rounded-lg px-3"
                        onClick={() => {
                          void loadDirectory("", true);
                        }}
                      >
                        Retry
                      </Button>
                    </div>
                  </div>
                ) : null}

                {rootWorkspace && visibleRootEntries.length === 0 ? (
                  <div className="flex min-h-40 items-center justify-center rounded-2xl border border-dashed border-zinc-300/70 bg-zinc-50/50 px-4 text-sm text-zinc-500 dark:border-zinc-700/80 dark:bg-zinc-900/30 dark:text-zinc-400">
                    No matching files under the current filter.
                  </div>
                ) : null}

                {rootWorkspace ? <div className="space-y-1">{renderEntries(rootWorkspace.entries, 0)}</div> : null}
              </div>
            </div>
          </>
        )}
      </Panel>
    </aside>
  );
}
