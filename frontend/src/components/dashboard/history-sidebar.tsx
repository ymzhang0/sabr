import { ChevronDown, ChevronRight, FolderOpen, Layers3, Moon, Plus, Search, Sun, Tag } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import { cn } from "@/lib/utils";
import type {
  ChatProject,
  ChatSessionSummary,
  ChatSessionWorkspaceResponse,
} from "@/types/aiida";

type HistorySidebarProps = {
  projects: ChatProject[];
  sessions: ChatSessionSummary[];
  activeProjectId: string | null;
  activeSessionId: string | null;
  activeSession: ChatSessionSummary | null;
  activeWorkspace: ChatSessionWorkspaceResponse | null;
  isWorkspaceLoading: boolean;
  isBusy: boolean;
  isDarkMode: boolean;
  onToggleTheme: () => void;
  onActivateSession: (sessionId: string) => void;
  onUpdateSessionTags: (sessionId: string, tags: string[]) => void;
  onCreateProject: (payload: { name: string; rootPath: string }) => void;
  onOpenWorkspace: (sessionId: string) => void;
};

function formatSessionTime(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "Unknown";
  }
  return parsed.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function normalizeTagValue(value: string): string {
  const trimmed = value.trim().replace(/\s+/g, "-");
  if (!trimmed) {
    return "";
  }
  return trimmed.startsWith("#") ? trimmed : `#${trimmed}`;
}

export function HistorySidebar({
  projects,
  sessions,
  activeProjectId,
  activeSessionId,
  activeSession,
  activeWorkspace,
  isWorkspaceLoading,
  isBusy,
  isDarkMode,
  onToggleTheme,
  onActivateSession,
  onUpdateSessionTags,
  onCreateProject,
  onOpenWorkspace,
}: HistorySidebarProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [tagFilter, setTagFilter] = useState("all");
  const [tagDraft, setTagDraft] = useState("");
  const [isProjectFormOpen, setIsProjectFormOpen] = useState(false);
  const [projectNameDraft, setProjectNameDraft] = useState("");
  const [projectPathDraft, setProjectPathDraft] = useState("");
  const [expandedProjects, setExpandedProjects] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (!activeProjectId) {
      return;
    }
    setExpandedProjects((current) => ({ ...current, [activeProjectId]: true }));
  }, [activeProjectId]);

  const availableTags = useMemo(
    () =>
      [...new Set(sessions.flatMap((session) => session.tags))]
        .filter(Boolean)
        .sort((left, right) => left.localeCompare(right)),
    [sessions],
  );

  const filteredSessions = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return sessions.filter((session) => {
      if (tagFilter !== "all" && !session.tags.includes(tagFilter)) {
        return false;
      }
      if (!query) {
        return true;
      }
      return [session.title, session.preview, session.project_label ?? "", session.tags.join(" "), session.workspace_path]
        .join(" ")
        .toLowerCase()
        .includes(query);
    });
  }, [searchQuery, sessions, tagFilter]);

  const projectGroups = useMemo(() => {
    const hasFilters = Boolean(searchQuery.trim()) || tagFilter !== "all";
    const sessionsByProject = new Map<string, ChatSessionSummary[]>();
    filteredSessions.forEach((session) => {
      const bucket = sessionsByProject.get(session.project_id) ?? [];
      bucket.push(session);
      sessionsByProject.set(session.project_id, bucket);
    });

    return projects
      .map((project) => ({
        project,
        sessions:
          (sessionsByProject.get(project.id) ?? []).sort((left, right) =>
            right.updated_at.localeCompare(left.updated_at),
          ),
      }))
      .filter(({ sessions: groupSessions }) => !hasFilters || groupSessions.length > 0);
  }, [filteredSessions, projects, searchQuery, tagFilter]);

  const handleAddTag = () => {
    if (!activeSession) {
      return;
    }
    const nextTag = normalizeTagValue(tagDraft);
    if (!nextTag || activeSession.tags.includes(nextTag)) {
      setTagDraft("");
      return;
    }
    onUpdateSessionTags(activeSession.id, [...activeSession.tags, nextTag]);
    setTagDraft("");
  };

  const handleCreateProject = () => {
    const cleanedName = projectNameDraft.trim();
    if (!cleanedName) {
      return;
    }
    onCreateProject({ name: cleanedName, rootPath: projectPathDraft.trim() });
    setProjectNameDraft("");
    setProjectPathDraft("");
    setIsProjectFormOpen(false);
  };

  return (
    <aside className="flex h-full min-h-0 w-full flex-col gap-2 p-3 font-sans tracking-tight">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-zinc-900 dark:text-zinc-100">Projects</h1>
          <p className="text-xs text-zinc-500 dark:text-zinc-400">Browse chat sessions by workspace project.</p>
        </div>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onToggleTheme} aria-label="Toggle color mode">
            {isDarkMode ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
        </div>
      </header>

      <Panel className="flex min-h-0 flex-1 flex-col gap-3 border-zinc-100/90 p-3 dark:border-zinc-800/80">
        <div className="space-y-2">
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" />
            <input
              type="text"
              placeholder="Search projects, sessions, tags..."
              className="h-9 w-full rounded-lg border border-zinc-200/65 bg-zinc-50/70 pl-9 pr-3 text-sm text-zinc-700 outline-none transition-colors focus:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-900/45 dark:text-zinc-200 dark:focus:border-zinc-600"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
            />
          </div>

          <div className="flex items-center gap-2">
            <select
              className="h-9 flex-1 rounded-lg border border-zinc-200/65 bg-zinc-50/70 px-3 text-sm text-zinc-700 outline-none transition-colors focus:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-900/45 dark:text-zinc-200 dark:focus:border-zinc-600"
              value={tagFilter}
              onChange={(event) => setTagFilter(event.target.value)}
            >
              <option value="all">All Tags</option>
              {availableTags.map((tag) => (
                <option key={tag} value={tag}>
                  {tag}
                </option>
              ))}
            </select>
            <Button
              variant={isProjectFormOpen ? "outline" : "default"}
              className="h-9 rounded-lg px-3"
              onClick={() => setIsProjectFormOpen((value) => !value)}
            >
              <Plus className="h-4 w-4" />
              Create New Project
            </Button>
          </div>

          {isProjectFormOpen ? (
            <div className="space-y-2 rounded-2xl border border-zinc-200/75 bg-zinc-50/70 p-3 dark:border-zinc-800/80 dark:bg-zinc-900/40">
              <input
                type="text"
                placeholder="Project name"
                className="h-9 w-full rounded-lg border border-zinc-200/65 bg-white px-3 text-sm text-zinc-700 outline-none transition-colors focus:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-950/60 dark:text-zinc-200 dark:focus:border-zinc-600"
                value={projectNameDraft}
                onChange={(event) => setProjectNameDraft(event.target.value)}
              />
              <input
                type="text"
                placeholder="Disk path (optional, server-side absolute or relative path)"
                className="h-9 w-full rounded-lg border border-zinc-200/65 bg-white px-3 text-sm text-zinc-700 outline-none transition-colors focus:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-950/60 dark:text-zinc-200 dark:focus:border-zinc-600"
                value={projectPathDraft}
                onChange={(event) => setProjectPathDraft(event.target.value)}
              />
              <div className="flex items-center justify-end gap-2">
                <Button variant="ghost" className="h-8 rounded-lg px-3" onClick={() => setIsProjectFormOpen(false)}>
                  Cancel
                </Button>
                <Button className="h-8 rounded-lg px-3" onClick={handleCreateProject} disabled={isBusy || !projectNameDraft.trim()}>
                  Create
                </Button>
              </div>
            </div>
          ) : null}
        </div>

        {activeSession ? (
          <section className="rounded-2xl border border-zinc-200/75 bg-zinc-50/60 p-3 dark:border-zinc-800/80 dark:bg-zinc-900/40">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-zinc-500 dark:text-zinc-400">
              <Layers3 className="h-3.5 w-3.5" />
              Active Session
            </div>
            <div className="mt-2 space-y-2 text-sm text-zinc-600 dark:text-zinc-300">
              <p>Project: {activeSession.project_label ?? "Unassigned"}</p>
              <p className="break-all text-xs text-zinc-500 dark:text-zinc-400">{activeSession.workspace_path}</p>
              <p>Attached nodes: {activeSession.node_count}</p>
              <div className="flex flex-wrap gap-1.5">
                {activeSession.tags.length > 0 ? (
                  activeSession.tags.map((tag) => (
                    <button
                      key={tag}
                      type="button"
                      onClick={() => onUpdateSessionTags(activeSession.id, activeSession.tags.filter((value) => value !== tag))}
                      className="rounded-full border border-zinc-200/80 bg-white px-2 py-1 text-[11px] text-zinc-600 transition-colors hover:border-zinc-300 hover:text-zinc-900 dark:border-zinc-700 dark:bg-zinc-950/50 dark:text-zinc-300 dark:hover:border-zinc-500 dark:hover:text-white"
                    >
                      {tag}
                    </button>
                  ))
                ) : (
                  <span className="text-xs text-zinc-400">No tags yet.</span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <div className="relative flex-1">
                  <Tag className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-zinc-400" />
                  <input
                    type="text"
                    placeholder="Add tag like #relaxation"
                    className="h-9 w-full rounded-lg border border-zinc-200/65 bg-white pl-8 pr-3 text-sm text-zinc-700 outline-none transition-colors focus:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-950/60 dark:text-zinc-200 dark:focus:border-zinc-600"
                    value={tagDraft}
                    onChange={(event) => setTagDraft(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        event.preventDefault();
                        handleAddTag();
                      }
                    }}
                  />
                </div>
                <Button size="sm" className="h-9 rounded-lg" onClick={handleAddTag} disabled={isBusy}>
                  Add
                </Button>
              </div>
            </div>
          </section>
        ) : null}

        <div className="minimal-scrollbar min-h-0 flex-1 space-y-2 overflow-y-auto pr-1">
          {projectGroups.length === 0 ? (
            <p className="rounded-xl border border-dashed border-zinc-300/60 bg-zinc-50/40 p-3 text-sm text-zinc-500 dark:border-white/10 dark:bg-zinc-900/30 dark:text-zinc-400">
              No project sessions match the current filters.
            </p>
          ) : (
            projectGroups.map(({ project, sessions: groupSessions }) => {
              const defaultExpanded = Boolean(searchQuery.trim()) || project.id === activeProjectId || project.active;
              const isExpanded = expandedProjects[project.id] ?? defaultExpanded;
              return (
                <section
                  key={project.id}
                  className="overflow-hidden rounded-2xl border border-zinc-200/75 bg-white/70 dark:border-zinc-800/80 dark:bg-zinc-900/45"
                >
                  <button
                    type="button"
                    className="flex w-full items-start justify-between gap-3 px-3 py-3 text-left"
                    onClick={() =>
                      setExpandedProjects((current) => ({
                        ...current,
                        [project.id]: !(current[project.id] ?? (project.id === activeProjectId || project.active)),
                      }))
                    }
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        {isExpanded ? <ChevronDown className="h-4 w-4 text-zinc-500" /> : <ChevronRight className="h-4 w-4 text-zinc-500" />}
                        <p className="truncate text-sm font-semibold text-zinc-900 dark:text-zinc-100">{project.name}</p>
                      </div>
                      <p className="mt-1 truncate pl-6 text-xs text-zinc-500 dark:text-zinc-400">{project.root_path}</p>
                    </div>
                    <span className="shrink-0 rounded-full bg-zinc-100 px-2 py-1 text-[11px] text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
                      {groupSessions.length}
                    </span>
                  </button>

                  {isExpanded ? (
                    <div className="space-y-2 border-t border-zinc-200/70 px-3 py-3 dark:border-zinc-800/70">
                      {groupSessions.length === 0 ? (
                        <p className="rounded-xl border border-dashed border-zinc-300/60 bg-zinc-50/40 p-3 text-sm text-zinc-500 dark:border-white/10 dark:bg-zinc-900/30 dark:text-zinc-400">
                          No sessions in this project yet.
                        </p>
                      ) : (
                        groupSessions.map((session) => {
                          const isActive = session.id === activeSessionId;
                          return (
                            <button
                              key={session.id}
                              type="button"
                              onClick={() => onActivateSession(session.id)}
                              disabled={isBusy || isActive}
                              className={cn(
                                "w-full rounded-2xl border px-3 py-3 text-left transition-all",
                                "border-zinc-200/75 bg-zinc-50/70 hover:border-zinc-300/85 hover:bg-white/90 dark:border-zinc-800/80 dark:bg-zinc-950/35 dark:hover:border-zinc-700/85 dark:hover:bg-zinc-900/65",
                                isActive && "border-zinc-300 bg-zinc-100 shadow-[0_10px_28px_-22px_rgba(15,23,42,0.7)] dark:border-zinc-700 dark:bg-zinc-800/65",
                              )}
                            >
                              <div className="flex items-start justify-between gap-3">
                                <div className="min-w-0">
                                  <p className="truncate text-sm font-semibold text-zinc-900 dark:text-zinc-100">{session.title}</p>
                                  <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{formatSessionTime(session.updated_at)}</p>
                                </div>
                                <span className="shrink-0 rounded-full bg-zinc-100 px-2 py-1 text-[11px] text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
                                  {session.message_count} msgs
                                </span>
                              </div>

                              <p className="mt-2 max-h-10 overflow-hidden text-sm text-zinc-600 dark:text-zinc-300">
                                {session.preview || "No messages yet."}
                              </p>

                              <div className="mt-3 flex flex-wrap items-center gap-1.5 text-[11px]">
                                <span className="rounded-full border border-zinc-200/80 bg-zinc-50 px-2 py-1 text-zinc-600 dark:border-zinc-700 dark:bg-zinc-950/40 dark:text-zinc-300">
                                  {session.node_count} nodes
                                </span>
                                {session.is_archived ? (
                                  <span className="rounded-full border border-amber-200/80 bg-amber-50 px-2 py-1 text-amber-700 dark:border-amber-900/80 dark:bg-amber-950/40 dark:text-amber-300">
                                    Archived
                                  </span>
                                ) : null}
                                {session.tags.map((tag) => (
                                  <span
                                    key={`${session.id}-${tag}`}
                                    className="rounded-full border border-zinc-200/80 bg-white px-2 py-1 text-zinc-600 dark:border-zinc-700 dark:bg-zinc-950/60 dark:text-zinc-300"
                                  >
                                    {tag}
                                  </span>
                                ))}
                              </div>
                            </button>
                          );
                        })
                      )}
                    </div>
                  ) : null}
                </section>
              );
            })
          )}
        </div>

        {activeSession ? (
          <section className="rounded-2xl border border-zinc-200/75 bg-zinc-50/60 p-3 dark:border-zinc-800/80 dark:bg-zinc-900/40">
            <div className="flex items-center justify-between gap-2">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-zinc-500 dark:text-zinc-400">Workspace</p>
                <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">Web mode lists files in the session folder.</p>
              </div>
              <Button
                className="h-9 rounded-lg px-3"
                onClick={() => onOpenWorkspace(activeSession.id)}
                disabled={isWorkspaceLoading}
              >
                <FolderOpen className="h-4 w-4" />
                Open Workspace Folder
              </Button>
            </div>
            {activeWorkspace ? (
              <div className="mt-3 space-y-2">
                <p className="break-all text-xs text-zinc-500 dark:text-zinc-400">{activeWorkspace.workspace_path}</p>
                <div className="max-h-36 space-y-1 overflow-y-auto rounded-xl border border-zinc-200/75 bg-white/80 p-2 dark:border-zinc-800/80 dark:bg-zinc-950/45">
                  {activeWorkspace.entries.length === 0 ? (
                    <p className="text-xs text-zinc-500 dark:text-zinc-400">Workspace is empty.</p>
                  ) : (
                    activeWorkspace.entries.map((entry) => (
                      <div
                        key={entry.relative_path}
                        className="flex items-center justify-between gap-3 rounded-lg px-2 py-1 text-xs text-zinc-600 dark:text-zinc-300"
                      >
                        <span className="truncate font-medium">{entry.is_dir ? `${entry.name}/` : entry.name}</span>
                        <span className="shrink-0 text-zinc-400 dark:text-zinc-500">
                          {entry.is_dir ? "dir" : `${entry.size ?? 0} B`}
                        </span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            ) : null}
          </section>
        ) : null}
      </Panel>
    </aside>
  );
}
