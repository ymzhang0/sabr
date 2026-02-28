import { useEffect, useRef, useState } from "react";

import { Panel } from "@/components/ui/panel";
import { cn } from "@/lib/utils";

type RuntimeTerminalProps = {
  lines: string[];
};

export function RuntimeTerminal({ lines }: RuntimeTerminalProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [isCollapsed, setIsCollapsed] = useState(false);

  useEffect(() => {
    if (isCollapsed) {
      return;
    }
    const container = containerRef.current;
    if (!container) {
      return;
    }
    container.scrollTop = container.scrollHeight;
  }, [isCollapsed, lines]);

  return (
    <Panel
      className={cn(
        "min-w-0 w-full shrink-0 overflow-hidden p-0 transition-all duration-300 ease-in-out",
        isCollapsed ? "max-h-14" : "max-h-[18rem]",
      )}
    >
      <div className="flex items-center justify-between px-4 py-3">
        <p className="text-[11px] uppercase tracking-[0.18em] text-zinc-500 dark:text-zinc-400">
          Runtime Terminal
        </p>
        <div className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-rose-500" />
          <button
            type="button"
            className="inline-flex h-3.5 w-3.5 items-center justify-center rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-300/80 dark:focus-visible:ring-amber-700/80"
            onClick={() => setIsCollapsed((current) => !current)}
            aria-label={isCollapsed ? "Expand runtime terminal" : "Collapse runtime terminal"}
          >
            <span
              className={cn(
                "h-2.5 w-2.5 rounded-full transition-colors duration-200",
                isCollapsed ? "bg-amber-300 dark:bg-amber-500" : "bg-amber-400",
              )}
            />
          </button>
          <button
            type="button"
            className="inline-flex h-3.5 w-3.5 items-center justify-center rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-300/80 dark:focus-visible:ring-emerald-700/80"
            onClick={() => setIsCollapsed(false)}
            aria-label="Expand runtime terminal"
          >
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
          </button>
        </div>
      </div>

      <div
        className={cn(
          "overflow-hidden px-3 transition-all duration-300 ease-in-out",
          isCollapsed ? "max-h-0 pb-0 opacity-0" : "max-h-56 pb-3 opacity-100",
        )}
      >
        <div
          ref={containerRef}
          className="minimal-scrollbar h-32 w-full overflow-x-auto overflow-y-auto rounded-xl bg-zinc-950 px-3 py-2 font-mono text-xs leading-5 text-zinc-200"
        >
          {lines.length === 0 ? (
            <p className="text-zinc-500">No runtime logs yet.</p>
          ) : (
            lines.map((line, index) => (
              <div key={`${index}-${line.slice(0, 20)}`} className="whitespace-nowrap">
                {line}
              </div>
            ))
          )}
        </div>
      </div>
    </Panel>
  );
}
