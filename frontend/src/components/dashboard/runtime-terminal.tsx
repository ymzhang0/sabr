import { useEffect, useRef } from "react";

import { Panel } from "@/components/ui/panel";

type RuntimeTerminalProps = {
  lines: string[];
};

export function RuntimeTerminal({ lines }: RuntimeTerminalProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }
    container.scrollTop = container.scrollHeight;
  }, [lines]);

  return (
    <Panel className="min-w-0 w-full shrink-0 p-3">
      <div className="mb-2 flex items-center justify-between px-1">
        <p className="text-[11px] uppercase tracking-[0.18em] text-zinc-500 dark:text-zinc-400">
          Runtime Terminal
        </p>
        <div className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-rose-500" />
          <span className="h-2.5 w-2.5 rounded-full bg-amber-400" />
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
        </div>
      </div>

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
    </Panel>
  );
}
