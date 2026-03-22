import type { PropsWithChildren } from "react";

import { cn } from "@/lib/utils";

export function Panel({ children, className }: PropsWithChildren<{ className?: string }>) {
  return (
    <section
      className={cn(
        "border-0 bg-white p-4 shadow-none dark:bg-zinc-950/45",
        className,
      )}
    >
      {children}
    </section>
  );
}
