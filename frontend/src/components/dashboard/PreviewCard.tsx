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
  groupId?: string;
  groupLabel?: string;
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
      return "text-blue-600 dark:text-blue-300";
    case "success":
      return "text-emerald-600 dark:text-emerald-300";
    case "warning":
      return "text-amber-600 dark:text-amber-300";
    default:
      return "text-slate-600 dark:text-slate-300";
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
  const metadataGroups = metadata.reduce<
    Array<{ id: string; label?: string; items: PreviewCardMetaItem[] }>
  >((accumulator, item) => {
    const groupId = item.groupId ?? "default";
    const existing = accumulator.find((group) => group.id === groupId);
    if (existing) {
      existing.items.push(item);
      if (!existing.label && item.groupLabel) {
        existing.label = item.groupLabel;
      }
      return accumulator;
    }
    accumulator.push({
      id: groupId,
      label: item.groupLabel,
      items: [item],
    });
    return accumulator;
  }, []);

  return (
    <div
      className={cn(
        "border-0 bg-white shadow-none dark:bg-slate-950",
        className,
      )}
    >
      <div className="flex flex-col gap-3 border-b border-slate-100 px-4 py-3 dark:border-slate-800/80 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          {eyebrow ? (
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400 dark:text-slate-500">
              {eyebrow}
            </p>
          ) : null}
          <h2 className="mt-1 truncate text-[15px] font-semibold tracking-tight text-slate-900 dark:text-slate-100 sm:text-base">
            {title}
          </h2>
          {badges.length > 0 ? (
            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2">
              {badges.map((badge) => (
                <div
                  key={badge.id}
                  className={cn(
                    "min-w-[72px] border-l border-slate-100 pl-4 first:border-l-0 first:pl-0 dark:border-slate-800",
                    badgeToneClasses(badge.tone),
                  )}
                >
                  <div className="flex flex-col gap-0.5">
                    <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400 dark:text-slate-500">
                      {badge.label}
                    </span>
                    <span className="text-sm font-medium text-slate-700 dark:text-slate-100">
                      {badge.value}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </div>
        {actions ? <div className="flex shrink-0 items-start gap-2 self-start">{actions}</div> : null}
      </div>

      {metadataGroups.length > 0 ? (
        <div className="px-4 py-3">
          <div className="px-0 py-0">
            {metadataGroups.map((group, groupIndex) => (
              <div
                key={group.id}
                className={cn(groupIndex > 0 && "mt-3 border-t border-slate-100 pt-3 dark:border-slate-800")}
              >
                {group.label ? (
                  <p className="pb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-slate-500">
                    {group.label}
                  </p>
                ) : null}
                <div
                  className={cn(
                    "grid gap-x-5 gap-y-3",
                    columns === 2 ? "md:grid-cols-2" : "md:grid-cols-2 xl:grid-cols-3",
                  )}
                >
                  {group.items.map((item) => {
                    const Icon = item.icon;
                    return (
                      <div key={item.id} className="flex min-w-0 gap-2.5 py-1">
                        <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400 dark:text-slate-500" />
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                            {item.label}
                          </p>
                          <div className="mt-1 min-w-0 text-sm font-medium text-slate-700 dark:text-slate-100">
                            {item.value}
                          </div>
                          {item.helper ? (
                            <div className="mt-1 min-w-0 text-[11px] text-slate-500 dark:text-slate-400">
                              {item.helper}
                            </div>
                          ) : null}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
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
          <div className="flex flex-wrap gap-x-4 gap-y-1">
            {stats.map((stat) => (
              <span key={stat.id} className="text-[11px] font-medium text-slate-500 dark:text-slate-400">
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
