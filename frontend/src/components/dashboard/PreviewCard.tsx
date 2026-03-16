import { type LucideIcon } from "lucide-react";
import { type ReactNode } from "react";

import { cn } from "@/lib/utils";

export type PreviewCardBadge = {
  id: string;
  label: string;
  value: ReactNode;
  tone?: "default" | "info" | "success" | "warning";
};

export type PreviewCardMetaItem = {
  id: string;
  label: string;
  value: ReactNode;
  icon: LucideIcon;
  helper?: ReactNode;
};

type PreviewCardProps = {
  eyebrow?: string | null;
  title: string;
  badges?: PreviewCardBadge[];
  actions?: ReactNode;
  metadata?: PreviewCardMetaItem[];
  columns?: 2 | 3;
  children?: ReactNode;
  className?: string;
};

type PreviewCardSectionProps = {
  title: string;
  stats?: Array<{ id: string; value: ReactNode }>;
  hint?: ReactNode;
  children: ReactNode;
  className?: string;
};

function badgeToneClasses(tone: PreviewCardBadge["tone"]): string {
  switch (tone) {
    case "info":
      return "border-blue-200/80 bg-blue-50/70 text-blue-700 dark:border-blue-900/50 dark:bg-blue-950/30 dark:text-blue-200";
    case "success":
      return "border-emerald-200/80 bg-emerald-50/70 text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/30 dark:text-emerald-200";
    case "warning":
      return "border-amber-200/80 bg-amber-50/70 text-amber-700 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-200";
    default:
      return "border-slate-200/80 bg-slate-50/75 text-slate-600 dark:border-slate-800 dark:bg-slate-900/55 dark:text-slate-300";
  }
}

export function PreviewCard({
  eyebrow,
  title,
  badges = [],
  actions,
  metadata = [],
  columns = 3,
  children,
  className,
}: PreviewCardProps) {
  return (
    <div
      className={cn(
        "rounded-2xl border border-slate-200/90 bg-white shadow-[0_10px_30px_rgba(15,23,42,0.06)] dark:border-slate-800 dark:bg-slate-950/70",
        className,
      )}
    >
      <div className="flex flex-col gap-3 border-b border-slate-100 px-4 py-3 dark:border-slate-800/80 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          {eyebrow ? (
            <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-400 dark:text-slate-500">
              {eyebrow}
            </p>
          ) : null}
          <h2 className="mt-1 truncate text-[15px] font-semibold tracking-tight text-slate-900 dark:text-slate-100 sm:text-base">
            {title}
          </h2>
          {badges.length > 0 ? (
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              {badges.map((badge) => (
                <span
                  key={badge.id}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px]",
                    badgeToneClasses(badge.tone),
                  )}
                >
                  <span className="font-semibold uppercase tracking-[0.12em] opacity-70">{badge.label}</span>
                  <span className="font-medium">{badge.value}</span>
                </span>
              ))}
            </div>
          ) : null}
        </div>
        {actions ? <div className="flex shrink-0 items-start gap-2 self-start">{actions}</div> : null}
      </div>

      {metadata.length > 0 ? (
        <div className="px-4 py-3">
          <div
            className={cn(
              "grid rounded-2xl border border-slate-100 bg-white px-3 py-2 dark:border-slate-800 dark:bg-slate-950/40",
              columns === 2 ? "gap-x-4 gap-y-3 md:grid-cols-2" : "gap-x-4 gap-y-3 md:grid-cols-2 xl:grid-cols-3",
            )}
          >
            {metadata.map((item) => {
              const Icon = item.icon;
              return (
                <div key={item.id} className="flex min-w-0 items-start gap-3 py-1">
                  <div className="mt-0.5 rounded-lg border border-slate-100 bg-slate-50 p-2 text-slate-500 dark:border-slate-800 dark:bg-slate-900/70 dark:text-slate-300">
                    <Icon className="h-3.5 w-3.5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                      {item.label}
                    </p>
                    <div className="mt-1 min-w-0 text-sm font-medium text-slate-700 dark:text-slate-100">
                      {item.value}
                    </div>
                    {item.helper ? (
                      <div className="mt-1 text-[11px] text-slate-500 dark:text-slate-400">{item.helper}</div>
                    ) : null}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : null}

      {children ? <div className="px-4 pb-4">{children}</div> : null}
    </div>
  );
}

export function PreviewCardSection({
  title,
  stats = [],
  hint,
  children,
  className,
}: PreviewCardSectionProps) {
  return (
    <section className={cn("border-t border-slate-100 pt-3 dark:border-slate-800/80", className)}>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h3 className="text-[12px] font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">
            {title}
          </h3>
          {hint ? <div className="mt-1 text-[11px] text-slate-500 dark:text-slate-400">{hint}</div> : null}
        </div>
        {stats.length > 0 ? (
          <div className="flex flex-wrap items-center gap-1.5">
            {stats.map((stat) => (
              <span
                key={stat.id}
                className="inline-flex items-center rounded-full border border-slate-200/80 bg-white px-2 py-0.5 text-[11px] text-slate-500 dark:border-slate-800 dark:bg-slate-950/70 dark:text-slate-300"
              >
                {stat.value}
              </span>
            ))}
          </div>
        ) : null}
      </div>
      <div className="mt-3">{children}</div>
    </section>
  );
}
