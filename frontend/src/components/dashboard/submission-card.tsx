import { ExternalLink, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";

type SubmissionDraftPkMapEntry = {
  pk: number;
  path?: string;
  label?: string;
};

export type SubmissionValidationSummary = {
  status?: string;
  is_valid?: boolean;
  blocking_error_count?: number;
  warning_count?: number;
  errors?: string[];
  warnings?: string[];
  summary_text?: string;
};

export type SubmissionDraftPayload = {
  process_label: string;
  inputs: Record<string, unknown>;
  meta: {
    pk_map?: SubmissionDraftPkMapEntry[];
    target_computer?: string | null;
    parallel_settings?: Record<string, unknown>;
    validation_summary?: SubmissionValidationSummary | null;
    validation?: Record<string, unknown> | null;
    draft?: Record<string, unknown>;
  };
};

export type SubmissionCardState = {
  status: "idle" | "submitting" | "submitted" | "cancelled" | "error";
  processPk?: number | null;
  errorText?: string | null;
};

type SubmissionCardProps = {
  turnId: number;
  submissionDraft: SubmissionDraftPayload;
  state: SubmissionCardState;
  isBusy: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  onInspectInputPk: (pk: number) => void;
  onOpenDetail: (pk: number) => void;
};

const CARD_FONT_STYLE = {
  fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif",
};

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function toPositiveInteger(value: unknown): number | null {
  if (typeof value === "number" && Number.isInteger(value) && value > 0) {
    return value;
  }
  if (typeof value === "string" && value.trim() !== "" && /^\d+$/.test(value.trim())) {
    const parsed = Number.parseInt(value.trim(), 10);
    return parsed > 0 ? parsed : null;
  }
  return null;
}

function formatParallelKey(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function stringifyCompact(value: unknown): string {
  if (value === null || value === undefined) {
    return "Not specified";
  }
  if (typeof value === "string") {
    const text = value.trim();
    return text || "Not specified";
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return "Not specified";
    }
    const printable = value
      .slice(0, 4)
      .map((item) => stringifyCompact(item))
      .filter((item) => item !== "Not specified");
    if (printable.length === 0) {
      return "Not specified";
    }
    const suffix = value.length > printable.length ? " ..." : "";
    return `${printable.join(", ")}${suffix}`;
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function findFirstNamedValue(payload: unknown, candidateKeys: Set<string>): unknown {
  if (Array.isArray(payload)) {
    for (const item of payload) {
      const nested = findFirstNamedValue(item, candidateKeys);
      if (nested !== undefined && nested !== null) {
        return nested;
      }
    }
    return null;
  }

  const record = asRecord(payload);
  if (!record) {
    return null;
  }

  for (const [key, value] of Object.entries(record)) {
    const lowered = key.trim().toLowerCase();
    if (candidateKeys.has(lowered) && value !== undefined && value !== null && value !== "") {
      return value;
    }
    const nested = findFirstNamedValue(value, candidateKeys);
    if (nested !== undefined && nested !== null) {
      return nested;
    }
  }
  return null;
}

function normalizePkMapEntries(value: unknown): SubmissionDraftPkMapEntry[] {
  if (!Array.isArray(value)) {
    return [];
  }
  const entries: SubmissionDraftPkMapEntry[] = [];
  const seen = new Set<number>();
  value.forEach((item) => {
    const record = asRecord(item);
    if (!record) {
      return;
    }
    const pk = toPositiveInteger(record.pk);
    if (pk === null) {
      return;
    }
    if (seen.has(pk)) {
      return;
    }
    seen.add(pk);
    const path = typeof record.path === "string" && record.path.trim() ? record.path.trim() : undefined;
    entries.push({
      pk,
      path,
      label: typeof record.label === "string" && record.label.trim() ? record.label.trim() : undefined,
    });
  });
  return entries;
}

function buildParallelEntries(parallel: unknown): Array<[string, unknown]> {
  const record = asRecord(parallel);
  if (!record) {
    return [];
  }
  return Object.entries(record).filter(
    ([, value]) =>
      value !== null &&
      value !== undefined &&
      !(typeof value === "string" && value.trim() === ""),
  );
}

export function SubmissionCard({
  turnId,
  submissionDraft,
  state,
  isBusy,
  onConfirm,
  onCancel,
  onInspectInputPk,
  onOpenDetail,
}: SubmissionCardProps) {
  const pkEntries = normalizePkMapEntries(submissionDraft.meta.pk_map);
  const targetComputer =
    typeof submissionDraft.meta.target_computer === "string" && submissionDraft.meta.target_computer.trim()
      ? submissionDraft.meta.target_computer.trim()
      : "Not specified";
  const parallelEntries = buildParallelEntries(submissionDraft.meta.parallel_settings);

  const codeSummary = stringifyCompact(
    findFirstNamedValue(submissionDraft.inputs, new Set(["code", "code_label", "pw_code", "qe_code", "codes"])),
  );
  const kPointsSummary = stringifyCompact(
    findFirstNamedValue(
      submissionDraft.inputs,
      new Set(["kpoints", "k_points", "kpoint_mesh", "kpoints_mesh", "mesh"]),
    ),
  );
  const pseudoSummary = stringifyCompact(
    findFirstNamedValue(
      submissionDraft.inputs,
      new Set(["pseudos", "pseudo", "pseudopotentials", "pseudo_family", "pseudo_family_label"]),
    ),
  );

  return (
    <section
      className="mt-3 rounded-xl border border-blue-200/80 bg-blue-50/50 p-3 shadow-sm dark:border-blue-900/60 dark:bg-blue-950/20"
      style={CARD_FONT_STYLE}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-blue-700/90 dark:text-blue-300/90">
            Submission Draft
          </p>
          <p className="mt-1 text-sm font-semibold text-blue-900 dark:text-blue-100">{submissionDraft.process_label}</p>
        </div>
        {state.status === "submitting" ? (
          <span className="inline-flex items-center gap-1 text-xs text-blue-700 dark:text-blue-200">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Submitting
          </span>
        ) : null}
      </div>

      <div className="mt-3 grid gap-2 text-[11px] sm:grid-cols-3">
        <div className="rounded-lg border border-blue-200/70 bg-white/70 px-2.5 py-2 dark:border-blue-900/60 dark:bg-blue-950/30">
          <p className="uppercase tracking-[0.08em] text-blue-600/90 dark:text-blue-300/85">Code</p>
          <p className="mt-1 break-words text-blue-900 dark:text-blue-100">{codeSummary}</p>
        </div>
        <div className="rounded-lg border border-blue-200/70 bg-white/70 px-2.5 py-2 dark:border-blue-900/60 dark:bg-blue-950/30">
          <p className="uppercase tracking-[0.08em] text-blue-600/90 dark:text-blue-300/85">K-points</p>
          <p className="mt-1 break-words text-blue-900 dark:text-blue-100">{kPointsSummary}</p>
        </div>
        <div className="rounded-lg border border-blue-200/70 bg-white/70 px-2.5 py-2 dark:border-blue-900/60 dark:bg-blue-950/30">
          <p className="uppercase tracking-[0.08em] text-blue-600/90 dark:text-blue-300/85">Pseudopotentials</p>
          <p className="mt-1 break-words text-blue-900 dark:text-blue-100">{pseudoSummary}</p>
        </div>
      </div>

      <div className="mt-3 space-y-2 text-xs text-blue-900 dark:text-blue-100">
        <div>
          <p className="font-semibold">Input PKs</p>
          {pkEntries.length > 0 ? (
            <div className="mt-1 flex flex-wrap gap-1.5">
              {pkEntries.map((entry, index) => (
                <button
                  key={`${turnId}-pk-${entry.pk}-${index}`}
                  type="button"
                  className="rounded-full border border-blue-300/80 bg-white/85 px-2.5 py-0.5 font-mono text-[11px] text-blue-700 transition-colors hover:bg-blue-100 dark:border-blue-800 dark:bg-blue-950/50 dark:text-blue-200 dark:hover:bg-blue-900/50"
                  onClick={() => onInspectInputPk(entry.pk)}
                  title={entry.path ?? `PK ${entry.pk}`}
                  disabled={isBusy}
                >
                  #{entry.pk}
                </button>
              ))}
            </div>
          ) : (
            <p className="mt-1 text-blue-700/85 dark:text-blue-200/85">No input PKs detected.</p>
          )}
        </div>

        <div className="grid gap-1 sm:grid-cols-2">
          <p>
            <span className="font-semibold">Target computer:</span> {targetComputer}
          </p>
          <p>
            <span className="font-semibold">Parallel keys:</span> {parallelEntries.length}
          </p>
        </div>

        {parallelEntries.length > 0 ? (
          <div className="grid gap-x-4 gap-y-1 sm:grid-cols-2">
            {parallelEntries.map(([key, value]) => (
              <p key={`${turnId}-parallel-${key}`} className="truncate">
                <span className="font-semibold">{formatParallelKey(key)}:</span> {stringifyCompact(value)}
              </p>
            ))}
          </div>
        ) : null}
      </div>

      <div className="mt-3">
        {state.status === "submitted" ? (
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-sm font-semibold text-emerald-700 dark:text-emerald-300">
              Submitted as PK #{state.processPk ?? "unknown"}
            </p>
            {state.processPk ? (
              <button
                type="button"
                onClick={() => onOpenDetail(state.processPk!)}
                className="inline-flex items-center gap-1 text-xs font-semibold text-blue-700 hover:text-blue-800 hover:underline dark:text-blue-300 dark:hover:text-blue-200"
              >
                <ExternalLink className="h-3.5 w-3.5" />
                View in Monitor
              </button>
            ) : null}
          </div>
        ) : state.status === "cancelled" ? (
          <p className="text-sm text-blue-700/85 dark:text-blue-200/85">Submission cancelled.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              className="bg-blue-600 text-white hover:bg-blue-500 dark:bg-blue-500 dark:hover:bg-blue-400"
              onClick={onConfirm}
              disabled={state.status === "submitting"}
            >
              {state.status === "submitting" ? (
                <span className="inline-flex items-center gap-1">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Submitting...
                </span>
              ) : (
                "Confirm & Submit"
              )}
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="border-blue-300/80 bg-white/70 text-blue-700 hover:bg-blue-100 dark:border-blue-800 dark:bg-blue-950/40 dark:text-blue-100 dark:hover:bg-blue-900/50"
              onClick={onCancel}
              disabled={state.status === "submitting"}
            >
              Cancel
            </Button>
          </div>
        )}
        {state.status === "error" && state.errorText ? (
          <p className="mt-2 text-xs text-rose-600 dark:text-rose-300">{state.errorText}</p>
        ) : null}
      </div>
    </section>
  );
}
