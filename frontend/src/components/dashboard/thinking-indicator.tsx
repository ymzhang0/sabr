import { ChevronDown } from "lucide-react";
import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

export type ProcessLogEntry = {
  id: string;
  toolName: string;
  friendlyStep: string;
  args?: string | null;
  result?: string | null;
  raw: string;
};

type ThinkingIndicatorProps = {
  currentStep?: string | null;
  processLog: ProcessLogEntry[];
  fallbackText?: string;
};

export function ThinkingIndicator({
  currentStep,
  processLog,
  fallbackText = "Thinking...",
}: ThinkingIndicatorProps) {
  const normalizedStep = (currentStep || "").trim();
  const displayStep = normalizedStep || fallbackText;
  const [isExpanded, setIsExpanded] = useState(false);

  const hasProcessLog = processLog.length > 0;
  const historyLog = hasProcessLog ? processLog.slice(0, -1) : [];
  const hasHistory = historyLog.length > 0;
  const hasActiveStep = normalizedStep.length > 0;

  useEffect(() => {
    if (!hasHistory && isExpanded) {
      setIsExpanded(false);
    }
  }, [hasHistory, isExpanded]);

  return (
    <section className="rounded-xl bg-zinc-50/55 px-2 py-1.5 transition-colors duration-200 dark:bg-zinc-900/45">
      <button
        type="button"
        className="inline-flex w-full items-center justify-between gap-2 rounded-md px-1 text-left"
        onClick={() => {
          if (!hasHistory) {
            return;
          }
          setIsExpanded((current) => !current);
        }}
        aria-label={isExpanded ? "Hide thought history" : "Show thought history"}
      >
        <span
          className={cn(
            "text-sm font-medium transition-colors duration-150 ease-out",
            hasActiveStep ? "animate-shimmer" : "text-slate-500 dark:text-slate-400",
          )}
        >
          {displayStep}
        </span>
        <ChevronDown
          className={cn(
            "h-3.5 w-3.5 shrink-0 text-slate-500 transition-transform duration-200 dark:text-slate-400",
            isExpanded && hasHistory ? "rotate-180" : "rotate-0",
            !hasHistory && "opacity-50",
          )}
          aria-hidden
        />
      </button>

      <div
        className={cn(
          "overflow-hidden transition-[max-height,opacity] duration-300 ease-out",
          isExpanded && hasHistory ? "mt-1 max-h-64 opacity-100" : "max-h-0 opacity-0",
        )}
      >
        <ul className="space-y-1 pl-1">
          {historyLog.map((entry) => (
            <li key={entry.id} className="text-xs text-slate-400 dark:text-slate-500">
              <span>{entry.friendlyStep}</span>
              <span className="ml-1.5 font-mono opacity-85">{entry.toolName}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
