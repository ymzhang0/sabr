import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Code2, Cpu, Loader2, PlugZap } from "lucide-react";

import {
  getBridgeProfiles,
  getBridgeResources,
  getBridgeStatus,
  switchBridgeProfile,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const STATUS_POLL_INTERVAL_MS = 10_000;
const DETAILS_POLL_INTERVAL_MS = 30_000;
const DEFAULT_BRIDGE_URL = "http://127.0.0.1:8001";
const DEFAULT_ENVIRONMENT = "Remote Bridge";

type HoveredDetail = "computers" | "codes" | "plugins" | null;

function resolvePortLabel(url: string): string {
  try {
    const parsed = new URL(url);
    if (parsed.port) {
      return `:${parsed.port}`;
    }
    if (parsed.protocol === "https:") {
      return ":443";
    }
    if (parsed.protocol === "http:") {
      return ":80";
    }
  } catch {
    const match = url.match(/:(\d+)(?:\/|$)/);
    if (match?.[1]) {
      return `:${match[1]}`;
    }
  }
  return ":8001";
}

function formatComputerDetail(item: { label: string; hostname: string }): string {
  return `${item.label} (${item.hostname})`;
}

function formatCodeDetail(item: { label: string; default_plugin: string | null; computer_label: string | null }): string {
  const plugin = item.default_plugin ? ` • ${item.default_plugin}` : "";
  const computer = item.computer_label ? ` @ ${item.computer_label}` : "";
  return `${item.label}${plugin}${computer}`;
}

export function BridgeStatus() {
  const queryClient = useQueryClient();
  const [hoveredDetail, setHoveredDetail] = useState<HoveredDetail>(null);

  const statusQuery = useQuery({
    queryKey: ["aiida-bridge-status"],
    queryFn: getBridgeStatus,
    refetchInterval: STATUS_POLL_INTERVAL_MS,
    refetchOnWindowFocus: false,
    staleTime: 2_000,
  });

  const isOnline = (statusQuery.data?.status ?? "offline") === "online";

  const profilesQuery = useQuery({
    queryKey: ["aiida-bridge-profiles"],
    queryFn: getBridgeProfiles,
    enabled: isOnline,
    refetchInterval: isOnline ? DETAILS_POLL_INTERVAL_MS : false,
    refetchOnWindowFocus: false,
  });

  const resourcesQuery = useQuery({
    queryKey: ["aiida-bridge-resources"],
    queryFn: getBridgeResources,
    enabled: isOnline,
    refetchInterval: isOnline ? DETAILS_POLL_INTERVAL_MS : false,
    refetchOnWindowFocus: false,
  });

  const switchProfileMutation = useMutation({
    mutationFn: switchBridgeProfile,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["aiida-bridge-status"] });
      void queryClient.invalidateQueries({ queryKey: ["aiida-bridge-profiles"] });
      void queryClient.invalidateQueries({ queryKey: ["aiida-bridge-resources"] });
    },
  });

  const status = statusQuery.data?.status ?? "offline";
  const bridgeUrl = statusQuery.data?.url ?? DEFAULT_BRIDGE_URL;
  const environment = statusQuery.data?.environment ?? DEFAULT_ENVIRONMENT;
  const profileName = statusQuery.data?.profile ?? profilesQuery.data?.current_profile ?? "unknown";
  const pluginNames = statusQuery.data?.plugins ?? [];
  const resourceCounts = statusQuery.data?.resources ?? { computers: 0, codes: 0, workchains: 0 };
  const computers = resourcesQuery.data?.computers ?? [];
  const codes = resourcesQuery.data?.codes ?? [];
  const profileOptions = profilesQuery.data?.profiles ?? [];
  const pluginCount = pluginNames.length;
  const computerCount = computers.length || resourceCounts.computers;
  const codeCount = codes.length || resourceCounts.codes;
  const portLabel = useMemo(() => resolvePortLabel(bridgeUrl), [bridgeUrl]);

  const hoveredItems = useMemo(() => {
    if (hoveredDetail === "computers") {
      return computers.map((item) => formatComputerDetail(item));
    }
    if (hoveredDetail === "codes") {
      return codes.map((item) => formatCodeDetail(item));
    }
    if (hoveredDetail === "plugins") {
      return pluginNames;
    }
    return [];
  }, [codes, computers, hoveredDetail, pluginNames]);

  return (
    <section className="relative z-40 min-h-[220px] overflow-visible rounded-2xl border border-zinc-200/80 bg-white/65 p-4 shadow-sm backdrop-blur-xl dark:border-white/10 dark:bg-zinc-950/45">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <span className="relative flex h-2.5 w-2.5 items-center justify-center">
            <span
              className={cn(
                "absolute inline-flex h-4 w-4 rounded-full",
                isOnline ? "animate-ping bg-emerald-500/35" : "animate-pulse bg-rose-500/35",
              )}
            />
            <span
              className={cn(
                "relative inline-flex h-2.5 w-2.5 rounded-full",
                isOnline
                  ? "bg-emerald-500 shadow-[0_0_12px_rgba(16,185,129,0.85)]"
                  : "bg-rose-500 shadow-[0_0_12px_rgba(239,68,68,0.8)]",
              )}
            />
          </span>

          <div className="min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-[0.17em] text-zinc-500 dark:text-zinc-400">
              AiiDA Worker
            </p>
            <p className="truncate text-sm font-medium text-zinc-800 dark:text-zinc-100">
              {portLabel} · {status === "online" ? "Online" : "Offline"}
            </p>
          </div>
        </div>

        <PlugZap
          className={cn(
            "h-4 w-4 shrink-0 transition-colors duration-200",
            isOnline ? "text-emerald-500" : "text-rose-500",
          )}
        />
      </div>

      <div className="space-y-2 text-xs text-zinc-700 dark:text-zinc-200">
        <div className="rounded-xl border border-zinc-200/80 bg-white/80 px-2.5 py-2 dark:border-zinc-700/80 dark:bg-zinc-800/65">
          <p className="mb-1 text-zinc-500 dark:text-zinc-400">Remote Profile</p>
          <div className="flex items-center gap-2">
            <select
              className="h-8 w-full rounded-lg border border-zinc-200/70 bg-zinc-50/80 px-2 text-[12px] text-zinc-800 outline-none transition-colors duration-200 focus:border-zinc-400 dark:border-zinc-700 dark:bg-zinc-900/65 dark:text-zinc-100 dark:focus:border-zinc-500"
              value={profileName === "unknown" ? "" : profileName}
              disabled={!isOnline || switchProfileMutation.isPending || profileOptions.length === 0}
              onChange={(event) => {
                const next = event.target.value.trim();
                if (!next || next === profileName || switchProfileMutation.isPending) {
                  return;
                }
                switchProfileMutation.mutate(next);
              }}
              aria-label="Select remote AiiDA profile"
            >
              {profileOptions.length === 0 ? (
                <option value="">No profiles</option>
              ) : null}
              {profileOptions.map((profile) => (
                <option key={profile.name} value={profile.name}>
                  {profile.name}
                </option>
              ))}
            </select>
            {switchProfileMutation.isPending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin text-zinc-500 dark:text-zinc-300" />
            ) : null}
          </div>
        </div>

        <div
          className="relative rounded-xl border border-zinc-200/80 bg-white/80 px-2.5 py-2 dark:border-zinc-700/80 dark:bg-zinc-800/65"
          onMouseLeave={() => setHoveredDetail(null)}
        >
          <p className="mb-1 text-zinc-500 dark:text-zinc-400">Resources</p>
          <div className="flex flex-wrap items-center gap-1 text-[11px] font-medium text-zinc-800 dark:text-zinc-100">
            <button
              type="button"
              className="rounded px-1 hover:bg-zinc-100 dark:hover:bg-zinc-700/60"
              onMouseEnter={() => setHoveredDetail("computers")}
            >
              <span className="inline-flex items-center gap-1">
                <Cpu className="h-3.5 w-3.5" />
                {computerCount} Computers
              </span>
            </button>
            <span className="text-zinc-400 dark:text-zinc-500">|</span>
            <button
              type="button"
              className="rounded px-1 hover:bg-zinc-100 dark:hover:bg-zinc-700/60"
              onMouseEnter={() => setHoveredDetail("codes")}
            >
              <span className="inline-flex items-center gap-1">
                <Code2 className="h-3.5 w-3.5" />
                {codeCount} Codes
              </span>
            </button>
            <span className="text-zinc-400 dark:text-zinc-500">|</span>
            <button
              type="button"
              className="rounded px-1 hover:bg-zinc-100 dark:hover:bg-zinc-700/60"
              onMouseEnter={() => setHoveredDetail("plugins")}
            >
              <span className="inline-flex items-center gap-1">
                <PlugZap className="h-3.5 w-3.5" />
                {pluginCount} Plugins
              </span>
            </button>
          </div>

          {hoveredDetail ? (
            <div className="absolute left-0 right-0 top-[calc(100%+0.4rem)] z-30 max-h-56 overflow-y-auto rounded-xl border border-zinc-200/80 bg-zinc-50/95 p-2 shadow-lg backdrop-blur-xl dark:border-zinc-700/85 dark:bg-zinc-900/95">
              <p className="mb-1 text-[10px] uppercase tracking-[0.12em] text-zinc-500 dark:text-zinc-400">
                {hoveredDetail === "computers" ? "Computers" : hoveredDetail === "codes" ? "Codes" : "Plugins"}
              </p>
              {hoveredItems.length === 0 ? (
                <p className="text-[11px] text-zinc-500 dark:text-zinc-400">No details reported.</p>
              ) : (
                <div className="space-y-1">
                  {hoveredItems.map((item) => (
                    <p key={item} className="truncate rounded-md px-2 py-1 text-[11px] text-zinc-700 dark:text-zinc-200">
                      {item}
                    </p>
                  ))}
                </div>
              )}
            </div>
          ) : null}
        </div>
      </div>

      <p className="mt-3 truncate text-[10px] text-zinc-500 dark:text-zinc-400">{environment}</p>

      {!isOnline ? (
        <p className="mt-2 inline-flex items-center gap-1.5 text-[11px] text-rose-600 dark:text-rose-300">
          <AlertTriangle className="h-3.5 w-3.5" />
          Check bridge at {portLabel}
        </p>
      ) : null}
    </section>
  );
}
