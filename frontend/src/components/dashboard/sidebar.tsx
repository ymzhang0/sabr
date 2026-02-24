import { FileUp, Loader2, Moon, Sun } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
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

type SidebarProps = {
  profiles: ProfileItem[];
  currentProfile: string | null;
  processes: ProcessItem[];
  isSwitchingProfile: boolean;
  isUploadingArchive: boolean;
  isDarkMode: boolean;
  onToggleTheme: () => void;
  onSwitchProfile: (profileName: string) => void;
  onUploadArchive: (file: File) => void;
};

export function Sidebar({
  profiles,
  currentProfile,
  processes,
  isSwitchingProfile,
  isUploadingArchive,
  isDarkMode,
  onToggleTheme,
  onSwitchProfile,
  onUploadArchive,
}: SidebarProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [selectedProfile, setSelectedProfile] = useState(currentProfile ?? "");
  const [dragActive, setDragActive] = useState(false);

  useEffect(() => {
    setSelectedProfile(currentProfile ?? "");
  }, [currentProfile]);

  const sortedProfiles = useMemo(
    () => [...profiles].sort((a, b) => a.display_name.localeCompare(b.display_name)),
    [profiles],
  );

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
          <div className="mb-3 flex items-center justify-between">
            <p className="text-[11px] uppercase tracking-[0.18em] text-zinc-500 dark:text-zinc-400">
              Process Monitor
            </p>
            <span className="text-xs text-zinc-500 dark:text-zinc-400">
              {processes.length} recent
            </span>
          </div>

          <div className="minimal-scrollbar min-h-0 flex-1 space-y-1.5 overflow-y-auto pr-1">
            {processes.length === 0 ? (
              <p className="rounded-xl border border-dashed border-zinc-300/80 p-3 text-sm text-zinc-500 dark:border-white/10 dark:text-zinc-400">
                No processes available.
              </p>
            ) : (
              processes.map((process) => (
                <div
                  key={`${process.pk}-${process.state}`}
                  className="grid grid-cols-[auto_1fr_auto] items-center gap-2 rounded-xl border border-zinc-200/80 bg-white/55 px-3 py-2 dark:border-white/10 dark:bg-zinc-900/45"
                >
                  <span className={cn("h-2.5 w-2.5 rounded-full", stateDotClass(process.status_color))} />
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-zinc-800 dark:text-zinc-100">
                      {process.label}
                    </p>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400">PK {process.pk}</p>
                  </div>
                  <p className="text-[11px] uppercase tracking-widest text-zinc-500 dark:text-zinc-400">
                    {process.state}
                  </p>
                </div>
              ))
            )}
          </div>
        </div>
      </Panel>
    </aside>
  );
}
