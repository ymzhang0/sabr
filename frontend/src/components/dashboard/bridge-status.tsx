import { type DragEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Code2, Cpu, Loader2, PlugZap, Plus } from "lucide-react";

import {
  getBridgeProfiles,
  getBridgeResources,
  getBridgeStatus,
  switchBridgeProfile,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import type { BridgeCodeResource, BridgeComputerResource, ResourceAttachment } from "@/types/aiida";
import { NewProfileDrawer } from "./new-profile-drawer";

const STATUS_POLL_INTERVAL_MS = 10_000;
const DETAILS_POLL_INTERVAL_MS = 30_000;
const DEFAULT_BRIDGE_URL = "http://127.0.0.1:8001";
const DEFAULT_ENVIRONMENT = "Remote Bridge";

type HoveredDetail = "computers" | "codes" | "plugins" | null;
const RESOURCE_ATTACHMENT_DRAG_MIME = "application/x-sabr-resource-attachment";

type HoveredResourceItem = {
  id: string;
  label: string;
  attachment: ResourceAttachment;
};

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

function toComputerAttachment(item: BridgeComputerResource): ResourceAttachment {
  const label = formatComputerDetail(item);
  const value = item.label?.trim() || item.hostname?.trim() || label;
  return {
    kind: "computer",
    value,
    label,
    plugin: null,
    computerLabel: item.label?.trim() || null,
    hostname: item.hostname?.trim() || null,
  };
}

function toCodeAttachment(item: BridgeCodeResource): ResourceAttachment {
  const codeLabel = item.label?.trim() || "code";
  const computerLabel = item.computer_label?.trim() || null;
  const value = computerLabel ? `${codeLabel}@${computerLabel}` : codeLabel;
  return {
    kind: "code",
    value,
    label: formatCodeDetail(item),
    plugin: item.default_plugin?.trim() || null,
    computerLabel,
    hostname: null,
  };
}

function toPluginAttachment(pluginName: string): ResourceAttachment {
  const value = pluginName.trim();
  return {
    kind: "plugin",
    value,
    label: value,
    plugin: value || null,
    computerLabel: null,
    hostname: null,
  };
}

interface BridgeStatusProps {
  onInfrastructureClick?: () => void;
  onSwitchProfileStart?: () => void;
  onSwitchProfileEnd?: () => void;
}

export function BridgeStatus({ onInfrastructureClick, onSwitchProfileStart, onSwitchProfileEnd }: BridgeStatusProps) {
  const queryClient = useQueryClient();
  const [hoveredDetail, setHoveredDetail] = useState<HoveredDetail>(null);
  const [isNewProfileDrawerOpen, setIsNewProfileDrawerOpen] = useState(false);

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
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["aiida-bridge-status"] }),
        queryClient.invalidateQueries({ queryKey: ["aiida-bridge-profiles"] }),
        queryClient.invalidateQueries({ queryKey: ["aiida-bridge-resources"] }),
        // Invalidate process and groups to get the new snapshot
        queryClient.invalidateQueries({ queryKey: ["processes"] }),
        queryClient.invalidateQueries({ queryKey: ["groups"] })
      ]);
    },
    onSettled: () => {
      onSwitchProfileEnd?.();
    }
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
  const pluginCount = pluginNames.length || resourceCounts.workchains;
  const computerCount = computers.length || resourceCounts.computers;
  const codeCount = codes.length || resourceCounts.codes;
  const portLabel = useMemo(() => resolvePortLabel(bridgeUrl), [bridgeUrl]);

  const hoveredItems = useMemo(() => {
    if (hoveredDetail === "computers") {
      return computers.map((item) => {
        const attachment = toComputerAttachment(item);
        return {
          id: `computer:${attachment.value}`,
          label: attachment.label,
          attachment,
        } satisfies HoveredResourceItem;
      });
    }
    if (hoveredDetail === "codes") {
      return codes.map((item) => {
        const attachment = toCodeAttachment(item);
        return {
          id: `code:${attachment.value}`,
          label: attachment.label,
          attachment,
        } satisfies HoveredResourceItem;
      });
    }
    if (hoveredDetail === "plugins") {
      return pluginNames
        .filter((pluginName) => pluginName.trim())
        .map((pluginName) => {
          const attachment = toPluginAttachment(pluginName);
          return {
            id: `plugin:${attachment.value}`,
            label: attachment.label,
            attachment,
          } satisfies HoveredResourceItem;
        });
    }
    return [];
  }, [codes, computers, hoveredDetail, pluginNames]);

  const handleResourceDragStart = (event: DragEvent<HTMLDivElement>, attachment: ResourceAttachment) => {
    const cleanedValue = attachment.value.trim();
    if (!cleanedValue) {
      return;
    }
    event.dataTransfer.effectAllowed = "copy";
    event.dataTransfer.setData(RESOURCE_ATTACHMENT_DRAG_MIME, JSON.stringify(attachment));
    event.dataTransfer.setData("text/plain", cleanedValue);
  };

  return (
    <section className="relative z-40 min-h-0 overflow-visible rounded-2xl border border-zinc-200/80 bg-white/65 p-4 shadow-sm backdrop-blur-xl dark:border-white/10 dark:bg-zinc-950/45">
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
            <div className="flex items-center gap-2 truncate text-sm font-medium text-zinc-800 dark:text-zinc-100">
              {portLabel} · {status === "online" ? "Online" : "Offline"}
              {isOnline && (
                <button
                  onClick={onInfrastructureClick}
                  className="inline-flex items-center gap-1 rounded bg-zinc-100/80 px-1.5 py-0.5 text-[10px] font-medium text-zinc-600 transition-colors hover:bg-zinc-200 dark:bg-zinc-800/80 dark:text-zinc-300 dark:hover:bg-zinc-700"
                  title="View Infrastructure"
                >
                  <span className={cn("h-1.5 w-1.5 rounded-full", computerCount > 0 ? "bg-emerald-500" : "bg-rose-500")} />
                  {computerCount} Hosts
                </button>
              )}
            </div>
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
        <div className="flex items-center gap-2 rounded-xl border border-zinc-200/80 bg-white/80 px-2.5 py-1.5 dark:border-zinc-700/80 dark:bg-zinc-800/65">
          <p className="shrink-0 text-zinc-500 dark:text-zinc-400">Profile</p>
          <select
            className="h-7 w-full rounded-lg border border-zinc-200/70 bg-zinc-50/80 px-2 text-[12px] text-zinc-800 outline-none transition-colors duration-200 focus:border-zinc-400 dark:border-zinc-700 dark:bg-zinc-900/65 dark:text-zinc-100 dark:focus:border-zinc-500"
            value={profileName === "unknown" ? "" : profileName}
            disabled={!isOnline || switchProfileMutation.isPending || profileOptions.length === 0}
            onChange={(event) => {
              const next = event.target.value.trim();
              if (!next || next === profileName || switchProfileMutation.isPending) {
                return;
              }
              onSwitchProfileStart?.();
              switchProfileMutation.mutate(next);
            }}
            aria-label="Select AiiDA profile"
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
          <button
            onClick={() => setIsNewProfileDrawerOpen(true)}
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-transparent text-zinc-500 hover:bg-zinc-100 hover:text-zinc-700 transition-colors dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
            title="Create New Profile"
          >
            <Plus className="h-3.5 w-3.5" />
          </button>
          {isNewProfileDrawerOpen && (
            <NewProfileDrawer
              isOpen={isNewProfileDrawerOpen}
              onClose={() => setIsNewProfileDrawerOpen(false)}
              onSuccess={() => { }}
            />
          )}
          {switchProfileMutation.isPending ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin text-zinc-500 dark:text-zinc-300" />
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
