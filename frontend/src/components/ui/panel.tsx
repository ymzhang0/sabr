import type { PropsWithChildren } from "react";

import { cn } from "@/lib/utils";

export function Panel({ children, className }: PropsWithChildren<{ className?: string }>) {
  return (
    <section
      className={cn(
        "rounded-2xl border border-white/50 bg-white/70 p-4 shadow-glass backdrop-blur-xl dark:border-white/10 dark:bg-zinc-950/45",
        className,
      )}
    >
      {children}
    </section>
  );
}
