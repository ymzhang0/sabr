import { ChevronDown, FileUp, Loader2, Moon, Sun } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import { BridgeStatus } from "@/components/dashboard/bridge-status";
import { cn } from "@/lib/utils";
import type { ProcessItem, ProfileItem } from "@/types/aiida";

function stateDotClass(state: ProcessItem["status_color"]): string {
  if (state === "running") {
    return "bg-emerald-400 shadow-[0_0_14px_rgba(52,211,153,0.65)] animate-pulse";
  }
  if (state === "success") {
    return "bg-emerald-500";
  }
  if (state === "error") {
    return "bg-rose-500";
  }
  return "bg-zinc-400 dark:bg-zinc-500";
}

function clampRecentLimit(value: number): number {
  return Math.min(100, Math.max(1, value));
}

function isStructureNode(process: ProcessItem): boolean {
  return process.node_type === "StructureData" || Boolean(process.formula);
}

function toDisplayStatus(state: string | null): string {
  const normalized = String(state || "unknown").trim().replace(/_/g, " ").toLowerCase();
  if (!normalized) {
    return "Unknown";
  }
  return normalized
    .split(" ")
    .filter(Boolean)
    .map((word: string) => `${word.charAt(0).toUpperCase()}${word.slice(1)}`)
    .join(" ");
}

type SidebarProps = {
  profiles: ProfileItem[];
  currentProfile: string | null;
  processes: ProcessItem[];
  groupOptions: string[];
  selectedGroup: string;
  selectedType: string;
  processLimit: number;
  referencedNodeIds: number[];
  isUpdatingProcessLimit: boolean;
  isSwitchingProfile: boolean;
  isUploadingArchive: boolean;
  isDarkMode: boolean;
  onToggleTheme: () => void;
  onGroupChange: (groupLabel: string) => void;
  onTypeChange: (nodeType: string) => void;
  onProcessLimitChange: (limit: number) => void;
  onSwitchProfile: (profileName: string) => void;
  onUploadArchive: (file: File) => void;
  onReferenceNode: (process: ProcessItem) => void;
};

const NODE_TYPE_OPTIONS = ["ProcessNode", "WorkChainNode", "StructureData"] as const;

export function Sidebar({
  profiles,
  currentProfile,
  processes,
  groupOptions,
  selectedGroup,
  selectedType,
  processLimit,
  referencedNodeIds,
  isUpdatingProcessLimit,
  isSwitchingProfile,
  isUploadingArchive,
  isDarkMode,
  onToggleTheme,
  onGroupChange,
  onTypeChange,
  onProcessLimitChange,
  onSwitchProfile,
  onUploadArchive,
  onReferenceNode,
}: SidebarProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const groupMenuRef = useRef<HTMLDivElement | null>(null);
  const typeMenuRef = useRef<HTMLDivElement | null>(null);
  const [selectedProfile, setSelectedProfile] = useState(currentProfile ?? "");
  const [dragActive, setDragActive] = useState(false);
  const [isGroupMenuOpen, setIsGroupMenuOpen] = useState(false);
  const [isTypeMenuOpen, setIsTypeMenuOpen] = useState(false);
  const [limitInput, setLimitInput] = useState(String(processLimit));

  useEffect(() => {
    setSelectedProfile(currentProfile ?? "");
  }, [currentProfile]);

  useEffect(() => {
    setLimitInput(String(processLimit));
  }, [processLimit]);

  const sortedProfiles = useMemo(
    () => [...profiles].sort((a, b) => a.display_name.localeCompare(b.display_name)),
    [profiles],
  );
  const sortedGroups = useMemo(
    () => [...groupOptions].sort((a, b) => a.localeCompare(b)),
    [groupOptions],
  );
  const referencedNodeSet = useMemo(
    () => new Set(referencedNodeIds),
    [referencedNodeIds],
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
    <aside className="flex h-full min-h-0 w-full shrink-0 flex-col gap-2 lg:w-[320px]">
      <header className="flex items-center justify-between">
        <h1 className="text-lg font-semibold tracking-tight text-zinc-900 dark:text-zinc-100">
          AiiDA Dashboard
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
        className={cn(
          "space-y-3 border-zinc-100/90 p-3 transition-opacity duration-300 dark:border-zinc-800/80",
          (isSwitchingProfile || isUploadingArchive) && "opacity-70",
        )}
      >
        <div className="mx-auto w-[90%] space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-[11px] font-medium uppercase tracking-[0.18em] text-zinc-500 dark:text-zinc-400">
              Profile
            </label>
            {isSwitchingProfile ? (
              <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-[0.15em] text-zinc-500 dark:text-zinc-400">
                <Loader2 className="h-3 w-3 animate-spin" />
                Switching
              </span>
            ) : null}
          </div>

          <div className="grid w-full grid-cols-[minmax(0,1fr)_36px] items-center gap-2">
            <select
              className="h-9 w-full truncate rounded-lg border border-zinc-200/70 bg-zinc-50/80 px-3 pr-8 text-sm text-zinc-800 outline-none transition-all duration-200 focus:border-zinc-400 focus:bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900/50 dark:text-zinc-200 dark:hover:border-zinc-700 dark:focus:border-zinc-600 dark:focus:bg-zinc-900/60"
              value={selectedProfile}
              disabled={isSwitchingProfile}
              onChange={(event) => {
                const nextProfile = event.target.value;
                setSelectedProfile(nextProfile);
                if (nextProfile && nextProfile !== currentProfile) {
                  onSwitchProfile(nextProfile);
                }
              }}
              aria-label="Select AiiDA profile"
            >
              <option value="">Select profile</option>
              {sortedProfiles.map((profile) => (
                <option key={profile.name} value={profile.name}>
                  {profile.display_name}
                </option>
              ))}
            </select>

            <Button
              variant="outline"
              size="icon"
              className="h-9 w-9 shrink-0 border-zinc-200/80 bg-transparent transition-colors duration-200 hover:bg-zinc-100/70 dark:border-zinc-800 dark:hover:bg-zinc-900/70"
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploadingArchive}
              aria-label="Upload archive"
            >
              <FileUp className="h-4 w-4" />
            </Button>
          </div>

          <div
            className={cn(
              "w-full rounded-lg border border-dashed px-3 py-2 text-[11px] text-zinc-500 transition-colors dark:text-zinc-400",
              dragActive
                ? "border-emerald-400/80 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                : "border-zinc-200/80 dark:border-zinc-800",
            )}
            onDragEnter={(event) => {
              event.preventDefault();
              setDragActive(true);
            }}
            onDragOver={(event) => {
              event.preventDefault();
              setDragActive(true);
            }}
            onDragLeave={(event) => {
              event.preventDefault();
              setDragActive(false);
            }}
            onDrop={(event) => {
              event.preventDefault();
              setDragActive(false);
              const file = event.dataTransfer.files?.[0];
              if (file) {
                onUploadArchive(file);
              }
            }}
          >
            Drop `.aiida` or `.zip` archive
          </div>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          accept=".aiida,.zip"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) {
              onUploadArchive(file);
            }
            event.target.value = "";
          }}
        />
      </Panel>

      <Panel
        className={cn(
          "flex min-h-0 flex-1 flex-col border-zinc-100/90 p-4 transition-opacity duration-300 dark:border-zinc-800/80",
          isSwitchingProfile && "opacity-75",
        )}
      >
        <div className="mx-auto flex h-full min-h-0 w-[90%] flex-col">
          <div className="mb-3 flex items-center justify-between gap-2">
            <p className="text-[11px] uppercase tracking-[0.18em] text-zinc-500 dark:text-zinc-400">
              Process Monitor
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
                  const isReferenced = referencedNodeSet.has(process.pk);
                  return (
                    <div
                      key={`${process.pk}-${process.state}-${process.formula ?? ""}`}
                      className={cn(
                        "grid grid-cols-[auto_1fr_auto] items-center gap-2 rounded-xl border px-3 py-2 transition-colors duration-200",
                        isReferenced
                          ? "border-zinc-300/85 bg-zinc-100/55 dark:border-zinc-700/85 dark:bg-zinc-800/50"
                          : "border-zinc-200/80 bg-white/55 dark:border-white/10 dark:bg-zinc-900/45",
                      )}
                    >
                      <span className={cn("h-2.5 w-2.5 rounded-full", stateDotClass(process.status_color))} />
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-zinc-800 dark:text-zinc-100">
                          {process.label}
                        </p>
                        <button
                          type="button"
                          className={cn(
                            "truncate text-xs transition-colors duration-200 hover:text-zinc-700 dark:hover:text-zinc-200",
                            isReferenced ? "text-zinc-700 dark:text-zinc-300" : "text-zinc-500 dark:text-zinc-400",
                          )}
                          onClick={() => onReferenceNode(process)}
                          aria-label={`Reference node #${process.pk} in chat`}
                        >
                          #{process.pk}
                        </button>
                      </div>
                      {isStructureNode(process) ? (
                        <p className="max-w-[9.5rem] truncate rounded-md bg-zinc-200/50 px-2 py-1 text-right font-mono text-[11px] text-zinc-700 dark:bg-zinc-800/70 dark:text-zinc-200">
                          {process.formula || "N/A"}
                        </p>
                      ) : (
                        <p className="max-w-[9.5rem] truncate rounded-md border border-zinc-300/70 bg-zinc-100/65 px-2 py-1 text-right text-[10px] uppercase tracking-[0.12em] text-zinc-600 dark:border-zinc-700 dark:bg-zinc-900/75 dark:text-zinc-300">
                          {toDisplayStatus(process.process_state || process.state)}
                        </p>
                      )}
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
