import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, PlugZap } from "lucide-react";

import { getBridgePlugins, getBridgeStatus } from "@/lib/api";
import { cn } from "@/lib/utils";

const STATUS_POLL_INTERVAL_MS = 10_000;
const PLUGIN_REFRESH_INTERVAL_MS = 30_000;
const DEFAULT_BRIDGE_URL = "http://127.0.0.1:8001";
const DEFAULT_ENVIRONMENT = "Local Sandbox";

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

export function BridgeStatus() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [isPopoverOpen, setIsPopoverOpen] = useState(false);

  const statusQuery = useQuery({
    queryKey: ["aiida-bridge-status"],
    queryFn: getBridgeStatus,
    refetchInterval: STATUS_POLL_INTERVAL_MS,
    refetchOnWindowFocus: false,
    staleTime: 2_000,
  });

  const status = statusQuery.data?.status ?? "offline";
  const bridgeUrl = statusQuery.data?.url ?? DEFAULT_BRIDGE_URL;
  const environment = statusQuery.data?.environment ?? DEFAULT_ENVIRONMENT;
  const isOnline = status === "online";
  const portLabel = useMemo(() => resolvePortLabel(bridgeUrl), [bridgeUrl]);

  const pluginsQuery = useQuery({
    queryKey: ["aiida-bridge-plugins"],
    queryFn: getBridgePlugins,
    enabled: isOnline || isPopoverOpen,
    refetchOnWindowFocus: false,
    refetchInterval: isOnline ? PLUGIN_REFRESH_INTERVAL_MS : false,
  });

  const plugins = pluginsQuery.data ?? [];

  useEffect(() => {
    const handleOutsideClick = (event: MouseEvent) => {
      const target = event.target as Node;
      if (containerRef.current && !containerRef.current.contains(target)) {
        setIsPopoverOpen(false);
      }
    };

    window.addEventListener("mousedown", handleOutsideClick);
    return () => window.removeEventListener("mousedown", handleOutsideClick);
  }, []);

  return (
    <div
      ref={containerRef}
      className="relative"
      onMouseEnter={() => setIsPopoverOpen(true)}
      onMouseLeave={() => setIsPopoverOpen(false)}
    >
      <button
        type="button"
        className="group flex w-full items-center gap-3 rounded-2xl border border-zinc-200/80 bg-white/65 px-3 py-2.5 text-left shadow-sm backdrop-blur-xl transition-all duration-200 hover:border-zinc-300 hover:bg-white/75 dark:border-white/10 dark:bg-zinc-950/45 dark:hover:border-white/20 dark:hover:bg-zinc-900/55"
        onClick={() => setIsPopoverOpen((open) => !open)}
        aria-label="AiiDA worker bridge connection status"
      >
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

        <div className="min-w-0 flex-1">
          <p className="text-[10px] font-semibold uppercase tracking-[0.17em] text-zinc-500 dark:text-zinc-400">
            AiiDA Worker
          </p>
          <p className="truncate text-sm font-medium text-zinc-800 dark:text-zinc-100">
            {portLabel} · {isOnline ? "Online" : "Offline"}
          </p>
        </div>

        <PlugZap
          className={cn(
            "h-4 w-4 shrink-0 transition-colors duration-200",
            isOnline ? "text-emerald-500" : "text-rose-500",
          )}
        />
      </button>

      {isPopoverOpen ? (
        <div className="absolute left-0 right-0 top-[calc(100%+0.45rem)] z-30 rounded-2xl border border-zinc-200/80 bg-zinc-50/95 p-3 shadow-lg backdrop-blur-xl dark:border-zinc-800/85 dark:bg-zinc-900/95">
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-zinc-500 dark:text-zinc-400">
              Installed Plugins
            </p>
            <p className="truncate text-[10px] text-zinc-500 dark:text-zinc-400">{environment}</p>
          </div>

          <div className="minimal-scrollbar max-h-28 overflow-y-auto pr-1">
            {pluginsQuery.isLoading ? (
              <p className="text-xs text-zinc-500 dark:text-zinc-400">Loading plugin list...</p>
            ) : plugins.length === 0 ? (
              <p className="text-xs text-zinc-500 dark:text-zinc-400">
                {isOnline ? "No plugin entries returned." : "Bridge offline. Plugin list unavailable."}
              </p>
            ) : (
              <ul className="flex flex-wrap gap-1.5">
                {plugins.map((plugin) => (
                  <li
                    key={plugin}
                    className="max-w-full truncate rounded-full border border-zinc-300/75 bg-white/80 px-2 py-0.5 text-[10px] text-zinc-700 dark:border-zinc-700 dark:bg-zinc-800/70 dark:text-zinc-200"
                    title={plugin}
                  >
                    {plugin}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {!isOnline ? (
            <p className="mt-2 inline-flex items-center gap-1.5 text-[11px] text-rose-600 dark:text-rose-300">
              <AlertTriangle className="h-3.5 w-3.5" />
              Check bridge at {portLabel}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
