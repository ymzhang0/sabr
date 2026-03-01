import { CheckCircle2, ChevronDown, Loader2, X } from "lucide-react";
import { type ReactNode, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type SubmissionDraftPkMapEntry = {
  pk: number;
  path?: string;
  label?: string;
};

type SubmissionStructureMetadata = {
  pk?: number | null;
  label?: string | null;
  formula?: string | null;
  symmetry?: string | null;
  num_atoms?: number | null;
  estimated_runtime?: unknown;
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

type SubmissionPrimaryInputField = {
  label?: string;
  value?: unknown;
  pk?: number;
};

export type SubmissionSubmitDraft = Record<string, unknown> | Array<Record<string, unknown>>;

export type SubmissionDraftPayload = {
  process_label: string;
  inputs: Record<string, unknown>;
  primary_inputs?: Record<string, SubmissionPrimaryInputField | unknown>;
  recommended_inputs?: Record<string, unknown>;
  all_inputs?: Record<string, unknown>;
  advanced_settings?: Record<string, unknown>;
  meta: {
    pk_map?: SubmissionDraftPkMapEntry[];
    target_computer?: string | null;
    parallel_settings?: Record<string, unknown>;
    validation_summary?: SubmissionValidationSummary | null;
    validation?: Record<string, unknown> | null;
    draft?: SubmissionSubmitDraft | null;
    recommended_inputs?: Record<string, unknown> | null;
    all_inputs?: Record<string, unknown> | null;
    structure_metadata?: SubmissionStructureMetadata[] | null;
    symmetry?: string | null;
    num_atoms?: number | null;
    estimated_runtime?: unknown;
  };
};

export type SubmissionModalState = {
  status: "idle" | "submitting" | "submitted" | "cancelled" | "error";
  processPk?: number | null;
  processPks?: number[] | null;
  errorText?: string | null;
};

type SubmissionModalProps = {
  open: boolean;
  turnId: number | null;
  submissionDraft: SubmissionDraftPayload | null;
  state: SubmissionModalState;
  isBusy: boolean;
  onClose: () => void;
  onConfirm: (draftPayload: SubmissionSubmitDraft) => void;
  onCancel: () => void;
  onOpenDetail: (pk: number) => void;
};

const MODAL_FONT_STYLE = {
  fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif",
};

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function toRecordArray(value: unknown): Array<Record<string, unknown>> {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => asRecord(item))
    .filter((item): item is Record<string, unknown> => Boolean(item));
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

function toFiniteNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number.parseFloat(value.trim());
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function isMissingValue(value: unknown): boolean {
  if (value === null || value === undefined) {
    return true;
  }
  if (typeof value === "string") {
    return value.trim() === "";
  }
  if (Array.isArray(value)) {
    return value.length === 0;
  }
  if (typeof value === "object") {
    return Object.keys(value as Record<string, unknown>).length === 0;
  }
  return false;
}

function stringifyCompact(value: unknown): string {
  if (isMissingValue(value)) {
    return "";
  }
  if (typeof value === "string") {
    return value.trim();
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value)) {
    const compact = value
      .slice(0, 4)
      .map((item) => stringifyCompact(item))
      .filter(Boolean);
    if (compact.length === 0) {
      return "";
    }
    return `${compact.join(", ")}${value.length > compact.length ? " ..." : ""}`;
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function formatSettingKey(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function findFirstNamedValue(payload: unknown, candidateKeys: Set<string>): unknown {
  if (Array.isArray(payload)) {
    for (const item of payload) {
      const nested = findFirstNamedValue(item, candidateKeys);
      if (!isMissingValue(nested)) {
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
    if (candidateKeys.has(key.trim().toLowerCase()) && !isMissingValue(value)) {
      return value;
    }
    const nested = findFirstNamedValue(value, candidateKeys);
    if (!isMissingValue(nested)) {
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
    if (pk === null || seen.has(pk)) {
      return;
    }
    seen.add(pk);
    entries.push({
      pk,
      path: typeof record.path === "string" && record.path.trim() ? record.path.trim() : undefined,
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
  return Object.entries(record).filter(([, value]) => !isMissingValue(value));
}

function normalizePrimaryField(
  label: string,
  value: unknown,
): SubmissionPrimaryInputField | null {
  if (isMissingValue(value)) {
    return null;
  }

  const record = asRecord(value);
  if (record) {
    const pk = toPositiveInteger(record.pk ?? record.structure_pk ?? record.code_pk);
    const display =
      typeof record.value === "string" && record.value.trim()
        ? record.value.trim()
        : typeof record.label === "string" && record.label.trim()
          ? record.label.trim()
          : typeof record.name === "string" && record.name.trim()
            ? record.name.trim()
            : stringifyCompact(value);
    return {
      label,
      value: display,
      pk: pk ?? undefined,
    };
  }

  const pk = toPositiveInteger(value);
  return {
    label,
    value: pk !== null && label.toLowerCase() === "structure" ? `PK ${pk}` : stringifyCompact(value),
    pk: pk !== null && label.toLowerCase() === "structure" ? pk : undefined,
  };
}

function extractPrimaryFields(submissionDraft: SubmissionDraftPayload): Record<string, SubmissionPrimaryInputField | null> {
  const source = asRecord(submissionDraft.primary_inputs);
  const fromSource = (key: string, label: string): SubmissionPrimaryInputField | null => {
    const entry = source?.[key];
    const normalized = normalizePrimaryField(label, entry);
    if (normalized) {
      return normalized;
    }
    return null;
  };

  const inputs = submissionDraft.inputs;
  const fallbackCode = findFirstNamedValue(inputs, new Set(["code", "code_label", "pw_code", "qe_code", "codes"]));
  const fallbackStructure = findFirstNamedValue(inputs, new Set(["structure", "structure_pk", "structure_id"]));
  const fallbackPseudos = findFirstNamedValue(
    inputs,
    new Set(["pseudos", "pseudo", "pseudopotentials", "pseudo_family", "pseudo_family_label"]),
  );

  return {
    code: fromSource("code", "Code") ?? normalizePrimaryField("Code", fallbackCode),
    structure: fromSource("structure", "Structure") ?? normalizePrimaryField("Structure", fallbackStructure),
    pseudos: fromSource("pseudos", "Pseudopotentials") ?? normalizePrimaryField("Pseudopotentials", fallbackPseudos),
  };
}

function renderPkLinkedText(
  text: string,
  seed: string,
  onOpenDetail: (pk: number) => void,
): ReactNode[] {
  const nodes: ReactNode[] = [];
  const pattern = /\b(PK|Node|#|structure)\s*(\d+)\b/gi;
  let cursor = 0;
  let match = pattern.exec(text);

  while (match) {
    const [full] = match;
    const pk = toPositiveInteger(match[2]);
    const start = match.index;
    const end = start + full.length;
    if (start > cursor) {
      nodes.push(text.slice(cursor, start));
    }
    if (pk !== null) {
      nodes.push(
        <button
          key={`${seed}-${start}-${pk}`}
          type="button"
          className="font-mono text-sky-700 underline decoration-dotted underline-offset-2 transition-colors hover:text-sky-900 dark:text-sky-300 dark:hover:text-sky-200"
          onClick={() => onOpenDetail(pk)}
        >
          {full}
        </button>,
      );
    } else {
      nodes.push(full);
    }
    cursor = end;
    match = pattern.exec(text);
  }
  if (cursor < text.length) {
    nodes.push(text.slice(cursor));
  }
  return nodes;
}

function renderValueNode(value: unknown, seed: string, onOpenDetail: (pk: number) => void): ReactNode {
  const text = stringifyCompact(value);
  if (!text) {
    return <span className="inline-flex rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500 dark:bg-slate-800 dark:text-slate-300">Default</span>;
  }
  return (
    <span className="break-all" title={text}>
      {renderPkLinkedText(text, seed, onOpenDetail)}
    </span>
  );
}

type DraftFieldEditorKind = "boolean" | "number" | "string" | "json";

type DraftFieldEditorValue = {
  path: string;
  label: string;
  kind: DraftFieldEditorKind;
  value: boolean | string;
  initialValue: boolean | string;
  isRecommended: boolean;
};

type SubmissionAllInputEntry = {
  path: string;
  value: unknown;
  isRecommended: boolean;
};

const DRAFT_TOP_LEVEL_OVERRIDE_SKIP = new Set([
  "workchain",
  "structure_pk",
  "code",
  "protocol",
  "overrides",
  "inputs",
  "primary_inputs",
  "recommended_inputs",
  "advanced_settings",
  "all_inputs",
  "meta",
]);

function inferFieldKind(value: unknown): DraftFieldEditorKind {
  if (typeof value === "boolean") {
    return "boolean";
  }
  if (typeof value === "number") {
    return "number";
  }
  if (Array.isArray(value) || asRecord(value)) {
    return "json";
  }
  return "string";
}

function flattenInputPorts(payload: unknown, prefix = "", out: Record<string, unknown> = {}): Record<string, unknown> {
  if (Array.isArray(payload)) {
    if (prefix) {
      out[prefix] = payload;
    }
    return out;
  }

  const record = asRecord(payload);
  if (!record) {
    if (prefix) {
      out[prefix] = payload;
    }
    return out;
  }

  Object.entries(record).forEach(([key, value]) => {
    const cleanKey = key.trim();
    if (!cleanKey) {
      return;
    }
    const path = prefix ? `${prefix}.${cleanKey}` : cleanKey;
    if (asRecord(value)) {
      flattenInputPorts(value, path, out);
      return;
    }
    out[path] = value;
  });
  return out;
}

function allInputEntriesFromDraft(submissionDraft: SubmissionDraftPayload): SubmissionAllInputEntry[] {
  const directAllInputs = asRecord(submissionDraft.all_inputs) ?? asRecord(submissionDraft.meta.all_inputs);
  const directRecommended = asRecord(submissionDraft.recommended_inputs) ?? asRecord(submissionDraft.meta.recommended_inputs) ?? {};
  const recommendedKeys = new Set(
    Object.keys(directRecommended)
      .map((key) => key.trim().toLowerCase())
      .filter(Boolean),
  );

  const entries: SubmissionAllInputEntry[] = [];
  const seen = new Set<string>();

  if (directAllInputs) {
    Object.entries(directAllInputs).forEach(([path, rawValue]) => {
      const normalizedPath = path.trim();
      if (!normalizedPath || seen.has(normalizedPath)) {
        return;
      }
      seen.add(normalizedPath);
      const entryRecord = asRecord(rawValue);
      const hasValueField = entryRecord && Object.prototype.hasOwnProperty.call(entryRecord, "value");
      const entryValue = hasValueField ? entryRecord?.value : rawValue;
      const leaf = normalizedPath.toLowerCase().split(".").pop() ?? "";
      const isRecommended =
        (typeof entryRecord?.is_recommended === "boolean"
          ? entryRecord.is_recommended
          : undefined) ?? (recommendedKeys.has(normalizedPath.toLowerCase()) || recommendedKeys.has(leaf));
      entries.push({
        path: normalizedPath,
        value: entryValue,
        isRecommended: Boolean(isRecommended),
      });
    });
  }

  if (entries.length > 0) {
    return entries;
  }

  const flattened = flattenInputPorts(submissionDraft.inputs);
  Object.entries(flattened).forEach(([path, value]) => {
    const normalizedPath = path.trim();
    if (!normalizedPath || seen.has(normalizedPath)) {
      return;
    }
    seen.add(normalizedPath);
    const leaf = normalizedPath.toLowerCase().split(".").pop() ?? "";
    entries.push({
      path: normalizedPath,
      value,
      isRecommended: recommendedKeys.has(normalizedPath.toLowerCase()) || recommendedKeys.has(leaf),
    });
  });

  return entries;
}

function buildDraftFieldEditorState(
  entries: SubmissionAllInputEntry[],
): Record<string, DraftFieldEditorValue> {
  const editors: Record<string, DraftFieldEditorValue> = {};
  entries.forEach((entry) => {
    const path = entry.path.trim();
    if (!path || isMissingValue(entry.value) || editors[path]) {
      return;
    }
    const kind = inferFieldKind(entry.value);
    let nextValue: boolean | string;
    if (kind === "boolean") {
      nextValue = Boolean(entry.value);
    } else if (kind === "json") {
      nextValue = JSON.stringify(entry.value, null, 2);
    } else {
      nextValue = stringifyCompact(entry.value);
    }
    editors[path] = {
      path,
      label: formatSettingKey(path.split(".").pop() ?? path),
      kind,
      value: nextValue,
      initialValue: nextValue,
      isRecommended: entry.isRecommended,
    };
  });
  return editors;
}

function parseDraftFieldEditorState(
  editors: Record<string, DraftFieldEditorValue>,
): {
  valuesByPath: Record<string, unknown>;
  errors: Record<string, string>;
} {
  const valuesByPath: Record<string, unknown> = {};
  const errors: Record<string, string> = {};

  Object.entries(editors).forEach(([path, editor]) => {
    if (editor.kind === "boolean") {
      valuesByPath[path] = Boolean(editor.value);
      return;
    }

    const raw = String(editor.value ?? "").trim();
    if (!raw) {
      return;
    }

    if (editor.kind === "number") {
      const numeric = toFiniteNumber(raw);
      if (numeric === null) {
        errors[path] = "Enter a valid number.";
        return;
      }
      valuesByPath[path] = numeric;
      return;
    }

    if (editor.kind === "json") {
      try {
        valuesByPath[path] = JSON.parse(raw);
      } catch {
        errors[path] = "JSON format is invalid.";
      }
      return;
    }

    valuesByPath[path] = raw;
  });

  return { valuesByPath, errors };
}

function isFieldModified(editor: DraftFieldEditorValue): boolean {
  if (editor.kind === "boolean") {
    return Boolean(editor.value) !== Boolean(editor.initialValue);
  }
  return String(editor.value).trim() !== String(editor.initialValue).trim();
}

function cloneDraftRecord(draft: Record<string, unknown>): Record<string, unknown> {
  if (typeof structuredClone === "function") {
    try {
      return structuredClone(draft) as Record<string, unknown>;
    } catch {
      // Fall through to JSON clone.
    }
  }
  return JSON.parse(JSON.stringify(draft)) as Record<string, unknown>;
}

function setValueByPath(target: Record<string, unknown>, path: string, value: unknown): boolean {
  const segments = path.split(".").map((segment) => segment.trim()).filter(Boolean);
  if (segments.length === 0) {
    return false;
  }
  let cursor: Record<string, unknown> = target;
  for (let index = 0; index < segments.length - 1; index += 1) {
    const segment = segments[index];
    const next = cursor[segment];
    const nextRecord = asRecord(next);
    if (!nextRecord) {
      return false;
    }
    cursor = nextRecord;
  }
  const leaf = segments[segments.length - 1];
  if (!Object.prototype.hasOwnProperty.call(cursor, leaf)) {
    return false;
  }
  cursor[leaf] = value;
  return true;
}

function applyLeafKeyRecursively(node: unknown, leafKey: string, value: unknown): boolean {
  if (Array.isArray(node)) {
    return node.reduce<boolean>(
      (applied, item) => applyLeafKeyRecursively(item, leafKey, value) || applied,
      false,
    );
  }
  const record = asRecord(node);
  if (!record) {
    return false;
  }
  let applied = false;
  Object.entries(record).forEach(([key, nested]) => {
    if (key.trim().toLowerCase() === leafKey) {
      record[key] = value;
      applied = true;
      return;
    }
    if (Array.isArray(nested) || asRecord(nested)) {
      applied = applyLeafKeyRecursively(nested, leafKey, value) || applied;
    }
  });
  return applied;
}

function mergeEditorValuesIntoDraft(
  draft: Record<string, unknown>,
  valuesByPath: Record<string, unknown>,
): Record<string, unknown> {
  if (Object.keys(valuesByPath).length === 0) {
    return draft;
  }

  const next = cloneDraftRecord(draft);
  const hasBuilderShape =
    typeof next.workchain === "string" &&
    toPositiveInteger(next.structure_pk) !== null &&
    typeof next.code === "string";
  const existingOverrides = asRecord(next.overrides);
  const nextOverrides: Record<string, unknown> = existingOverrides ? { ...existingOverrides } : {};
  const allInputsRecord = asRecord(next.all_inputs) ?? {};
  const recommendedInputsRecord = asRecord(next.recommended_inputs) ?? {};

  Object.entries(valuesByPath).forEach(([path, value]) => {
    const normalizedPath = path.trim();
    if (!normalizedPath) {
      return;
    }
    const appliedByPath = setValueByPath(next, normalizedPath, value);
    const leaf = normalizedPath.toLowerCase().split(".").pop() ?? normalizedPath.toLowerCase();
    const topLevelKey = normalizedPath.toLowerCase().split(".")[0] ?? "";
    const appliedByLeaf = appliedByPath ? true : applyLeafKeyRecursively(next, leaf, value);
    if ((hasBuilderShape || !appliedByLeaf) && !DRAFT_TOP_LEVEL_OVERRIDE_SKIP.has(topLevelKey)) {
      nextOverrides[leaf] = value;
    }
    allInputsRecord[normalizedPath] = {
      value,
      is_recommended:
        asRecord(allInputsRecord[normalizedPath])?.is_recommended ??
        asRecord(allInputsRecord[normalizedPath])?.isRecommended ??
        false,
    };
    if (Object.prototype.hasOwnProperty.call(recommendedInputsRecord, leaf)) {
      recommendedInputsRecord[leaf] = value;
    }
  });

  if (Object.keys(nextOverrides).length > 0) {
    next.overrides = nextOverrides;
  }
  if (Object.keys(allInputsRecord).length > 0) {
    next.all_inputs = allInputsRecord;
  }
  if (Object.keys(recommendedInputsRecord).length > 0) {
    next.recommended_inputs = recommendedInputsRecord;
  }
  return next;
}

function applyEditorValuesToSubmitDraft(
  draftPayload: SubmissionSubmitDraft,
  valuesByPath: Record<string, unknown>,
): SubmissionSubmitDraft {
  if (Object.keys(valuesByPath).length === 0) {
    return draftPayload;
  }
  if (Array.isArray(draftPayload)) {
    return draftPayload.map((draft) => mergeEditorValuesIntoDraft(draft, valuesByPath));
  }
  return mergeEditorValuesIntoDraft(draftPayload, valuesByPath);
}

function parseSecondsFromRuntimeValue(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value) && value > 0) {
    return Math.round(value);
  }
  if (typeof value !== "string") {
    return null;
  }
  const raw = value.trim().toLowerCase();
  if (!raw) {
    return null;
  }
  if (/^\d+(\.\d+)?$/.test(raw)) {
    const numeric = Number.parseFloat(raw);
    return Number.isFinite(numeric) && numeric > 0 ? Math.round(numeric) : null;
  }
  const timeMatch = raw.match(/^(\d+):(\d{2})(?::(\d{2}))?$/);
  if (timeMatch) {
    const hours = Number.parseInt(timeMatch[1], 10);
    const minutes = Number.parseInt(timeMatch[2], 10);
    const seconds = Number.parseInt(timeMatch[3] ?? "0", 10);
    return Math.max(0, (hours * 60 + minutes) * 60 + seconds);
  }
  const unitMatches = [...raw.matchAll(/(\d+(?:\.\d+)?)\s*(h|hr|hrs|hour|hours|m|min|mins|minute|minutes|s|sec|secs|second|seconds)\b/g)];
  if (unitMatches.length === 0) {
    return null;
  }
  let totalSeconds = 0;
  unitMatches.forEach((match) => {
    const scalar = Number.parseFloat(match[1]);
    const unit = match[2];
    if (!Number.isFinite(scalar)) {
      return;
    }
    if (unit.startsWith("h")) {
      totalSeconds += scalar * 3600;
      return;
    }
    if (unit.startsWith("m")) {
      totalSeconds += scalar * 60;
      return;
    }
    totalSeconds += scalar;
  });
  return totalSeconds > 0 ? Math.round(totalSeconds) : null;
}

function inferRuntimeFromDraftHeuristic(payload: unknown): number | null {
  const protocol = stringifyCompact(findFirstNamedValue(payload, new Set(["protocol"]))).toLowerCase();
  let estimatedSeconds = 3600;
  if (protocol.includes("precise") || protocol.includes("strict")) {
    estimatedSeconds = 3 * 3600;
  } else if (protocol.includes("fast")) {
    estimatedSeconds = 1800;
  }

  const kpointsDistance = toFiniteNumber(
    findFirstNamedValue(payload, new Set(["kpoints_distance", "kpoint_distance"])),
  );
  if (kpointsDistance !== null && kpointsDistance > 0) {
    if (kpointsDistance < 0.12) {
      estimatedSeconds *= 1.7;
    } else if (kpointsDistance < 0.2) {
      estimatedSeconds *= 1.35;
    }
  }

  if (!isMissingValue(findFirstNamedValue(payload, new Set(["hubbard_u", "hubbard_v"])))) {
    estimatedSeconds *= 1.2;
  }

  const nstep = toFiniteNumber(findFirstNamedValue(payload, new Set(["nstep", "max_steps"])));
  if (nstep !== null && nstep > 80) {
    estimatedSeconds *= 1.4;
  }

  const totalMpiProcs = toFiniteNumber(
    findFirstNamedValue(payload, new Set(["tot_num_mpiprocs", "num_mpiprocs", "npool"])),
  );
  if (totalMpiProcs !== null && totalMpiProcs > 1) {
    const speedup = Math.min(4, Math.max(1, Math.sqrt(totalMpiProcs)));
    estimatedSeconds /= speedup;
  }

  return Math.round(Math.max(600, estimatedSeconds));
}

function extractRuntimePredictionSeconds(payload: unknown): number | null {
  const direct = findFirstNamedValue(
    payload,
    new Set([
      "runtime_prediction",
      "runtime_estimate",
      "estimated_runtime",
      "estimated_runtime_seconds",
      "time_estimate",
      "time_estimate_seconds",
      "predicted_runtime_seconds",
      "runtime_seconds",
      "max_wallclock_seconds",
    ]),
  );
  const directRecord = asRecord(direct);
  const candidateValues: unknown[] = [
    direct,
    directRecord?.seconds,
    directRecord?.estimated_seconds,
    directRecord?.runtime_seconds,
    directRecord?.value,
    directRecord?.total_seconds,
  ];
  for (const candidate of candidateValues) {
    const parsed = parseSecondsFromRuntimeValue(candidate);
    if (parsed !== null && parsed > 0) {
      return parsed;
    }
  }
  return inferRuntimeFromDraftHeuristic(payload);
}

function formatRuntimeEstimate(seconds: number | null): string {
  if (seconds === null || seconds <= 0) {
    return "System estimated";
  }
  const minutes = Math.max(1, Math.round(seconds / 60));
  if (minutes < 60) {
    return `~${minutes}m`;
  }
  const hours = Math.floor(minutes / 60);
  const remainderMinutes = minutes % 60;
  if (remainderMinutes === 0) {
    return `~${hours}h`;
  }
  return `~${hours}h ${remainderMinutes}m`;
}

function extractSymmetryLabel(payload: unknown): string | null {
  const candidate = findFirstNamedValue(
    payload,
    new Set([
      "symmetry",
      "symmetry_label",
      "spacegroup",
      "space_group",
      "space_group_symbol",
      "international_symbol",
      "crystal_system",
      "spglib",
    ]),
  );
  const record = asRecord(candidate);
  if (record) {
    const prioritizedKeys = [
      "international_symbol",
      "space_group_symbol",
      "spacegroup",
      "symbol",
      "crystal_system",
      "label",
      "name",
      "hall_symbol",
    ];
    for (const key of prioritizedKeys) {
      const value = record[key];
      if (typeof value === "string" && value.trim()) {
        return value.trim();
      }
    }
    const number = toPositiveInteger(record.number);
    if (number !== null) {
      return `Space group ${number}`;
    }
  }
  if (typeof candidate === "string" && candidate.trim()) {
    return candidate.trim();
  }
  const numeric = toPositiveInteger(candidate);
  if (numeric !== null) {
    return `Space group ${numeric}`;
  }
  return null;
}

type BatchJobDraft = {
  id: string;
  pk: number | null;
  label: string;
  formula: string;
  symmetry: string;
  runtimeSeconds: number | null;
  runtimeEstimate: string;
  numAtoms: number | null;
  draft: Record<string, unknown>;
};

function normalizeStructureMetadataEntries(submissionDraft: SubmissionDraftPayload): SubmissionStructureMetadata[] {
  const raw = submissionDraft.meta.structure_metadata;
  if (!Array.isArray(raw)) {
    return [];
  }
  const entries: SubmissionStructureMetadata[] = [];
  raw.forEach((entry) => {
    const record = asRecord(entry);
    if (!record) {
      return;
    }
    entries.push({
      pk: toPositiveInteger(record.pk),
      label: typeof record.label === "string" && record.label.trim() ? record.label.trim() : null,
      formula: typeof record.formula === "string" && record.formula.trim() ? record.formula.trim() : null,
      symmetry: typeof record.symmetry === "string" && record.symmetry.trim() ? record.symmetry.trim() : null,
      num_atoms: toPositiveInteger(record.num_atoms),
      estimated_runtime: record.estimated_runtime,
    });
  });
  return entries;
}

function extractBatchDrafts(submissionDraft: SubmissionDraftPayload): Array<Record<string, unknown>> {
  const metaDraft = submissionDraft.meta.draft;
  const rootRecord = asRecord(metaDraft);
  const fromMetaDraftArray = toRecordArray(metaDraft);
  if (fromMetaDraftArray.length > 0) {
    return fromMetaDraftArray;
  }
  const nestedKeys = ["jobs", "tasks", "submissions", "drafts"];
  for (const key of nestedKeys) {
    const nested = toRecordArray(rootRecord?.[key]);
    if (nested.length > 0) {
      return nested;
    }
  }
  for (const key of nestedKeys) {
    const nested = toRecordArray(submissionDraft.inputs[key]);
    if (nested.length > 0) {
      return nested;
    }
  }
  return [];
}

function extractBatchJobRows(submissionDraft: SubmissionDraftPayload): BatchJobDraft[] {
  const drafts = extractBatchDrafts(submissionDraft);
  const metadataEntries = normalizeStructureMetadataEntries(submissionDraft);
  if (drafts.length <= 1 && metadataEntries.length > 1) {
    const baseDraft =
      asRecord(submissionDraft.meta.draft) ??
      toRecordArray(submissionDraft.meta.draft)[0] ??
      submissionDraft.inputs;
    return metadataEntries.map((entry, index) => {
      const pk = toPositiveInteger(entry.pk);
      const formula =
        (typeof entry.formula === "string" && entry.formula.trim() ? entry.formula.trim() : null) ??
        (typeof entry.label === "string" && entry.label.trim() ? entry.label.trim() : null) ??
        (pk ? `Structure #${pk}` : `Task ${index + 1}`);
      const symmetry =
        (typeof entry.symmetry === "string" && entry.symmetry.trim() ? entry.symmetry.trim() : null) ??
        "System selected";
      const runtimeSeconds =
        parseSecondsFromRuntimeValue(entry.estimated_runtime) ??
        extractRuntimePredictionSeconds(baseDraft);
      const numAtoms = toPositiveInteger(entry.num_atoms);
      const rowDraft = cloneDraftRecord(baseDraft);
      if (pk !== null) {
        rowDraft.structure_pk = pk;
      }
      return {
        id: `${index}-${pk ?? "none"}`,
        pk: pk ?? null,
        label: formula,
        formula,
        symmetry,
        runtimeSeconds,
        runtimeEstimate: formatRuntimeEstimate(runtimeSeconds),
        numAtoms: numAtoms ?? null,
        draft: rowDraft,
      };
    });
  }
  return drafts.map((draft, index) => {
    const structureValue = findFirstNamedValue(
      draft,
      new Set(["structure_pk", "structure_id", "structure", "pk"]),
    );
    const structureRecord = asRecord(structureValue);
    const structurePk =
      toPositiveInteger(structureRecord?.pk) ??
      toPositiveInteger(structureRecord?.structure_pk) ??
      toPositiveInteger(structureValue);
    const label = stringifyCompact(
      findFirstNamedValue(
        draft,
        new Set(["label", "structure_label", "name", "formula", "structure_name"]),
      ),
    ) || (structurePk ? `Structure #${structurePk}` : `Task ${index + 1}`);
    const metadataMatch =
      metadataEntries.find((entry) => entry.pk !== null && entry.pk === structurePk) ??
      metadataEntries[index] ??
      null;
    const formula =
      (typeof metadataMatch?.formula === "string" && metadataMatch.formula.trim()
        ? metadataMatch.formula.trim()
        : stringifyCompact(findFirstNamedValue(draft, new Set(["formula", "chemical_formula", "formula_hill"])))) ||
      label;
    const symmetry =
      (typeof metadataMatch?.symmetry === "string" && metadataMatch.symmetry.trim()
        ? metadataMatch.symmetry.trim()
        : extractSymmetryLabel(draft)) ?? "System selected";
    const runtimeSeconds =
      parseSecondsFromRuntimeValue(metadataMatch?.estimated_runtime) ??
      extractRuntimePredictionSeconds(draft);
    const numAtoms =
      toPositiveInteger(metadataMatch?.num_atoms) ??
      toPositiveInteger(findFirstNamedValue(draft, new Set(["num_atoms", "natoms", "number_of_atoms"])));
    return {
      id: `${index}-${structurePk ?? "none"}`,
      pk: structurePk ?? null,
      label,
      formula,
      symmetry,
      runtimeSeconds,
      runtimeEstimate: formatRuntimeEstimate(runtimeSeconds),
      numAtoms: numAtoms ?? null,
      draft,
    };
  });
}

export function SubmissionModal({
  open,
  turnId,
  submissionDraft,
  state,
  isBusy,
  onClose,
  onConfirm,
  onCancel,
  onOpenDetail,
}: SubmissionModalProps) {
  const [isAdvancedExpanded, setIsAdvancedExpanded] = useState(false);
  const [isAllInputsExpanded, setIsAllInputsExpanded] = useState(false);
  const [selectedBatchIds, setSelectedBatchIds] = useState<string[]>([]);
  const [draftState, setDraftState] = useState<Record<string, DraftFieldEditorValue>>({});
  const [draftStateErrors, setDraftStateErrors] = useState<Record<string, string>>({});
  const [expandedJsonFields, setExpandedJsonFields] = useState<Record<string, boolean>>({});
  const [globalOverridePath, setGlobalOverridePath] = useState("");
  const [globalOverrideValue, setGlobalOverrideValue] = useState("");

  useEffect(() => {
    if (!open) {
      setIsAdvancedExpanded(false);
      setIsAllInputsExpanded(false);
      return;
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && state.status !== "submitting") {
        onClose();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose, state.status]);

  const pkEntries = useMemo(
    () => normalizePkMapEntries(submissionDraft?.meta.pk_map),
    [submissionDraft],
  );
  const primaryFields = useMemo(
    () => (submissionDraft ? extractPrimaryFields(submissionDraft) : { code: null, structure: null, pseudos: null }),
    [submissionDraft],
  );
  const advancedEntries = useMemo(() => {
    const source = asRecord(submissionDraft?.advanced_settings);
    if (!source) {
      return [];
    }
    return Object.entries(source).filter(([, value]) => !isMissingValue(value));
  }, [submissionDraft]);
  const allInputEntries = useMemo(
    () => (submissionDraft ? allInputEntriesFromDraft(submissionDraft) : []),
    [submissionDraft],
  );
  const allDraftFields = useMemo(() => {
    const fields = Object.values(draftState);
    return fields.sort((left, right) => {
      if (left.isRecommended !== right.isRecommended) {
        return left.isRecommended ? -1 : 1;
      }
      return left.path.localeCompare(right.path);
    });
  }, [draftState]);
  const recommendedDraftFields = useMemo(
    () => allDraftFields.filter((field) => field.isRecommended),
    [allDraftFields],
  );
  const additionalDraftFields = useMemo(
    () => allDraftFields.filter((field) => !field.isRecommended),
    [allDraftFields],
  );
  const globalOverrideOptions = useMemo(
    () => allDraftFields.filter((field) => field.kind !== "json"),
    [allDraftFields],
  );
  const parallelEntries = useMemo(
    () => buildParallelEntries(submissionDraft?.meta.parallel_settings),
    [submissionDraft],
  );
  const batchJobs = useMemo(
    () => (submissionDraft ? extractBatchJobRows(submissionDraft) : []),
    [submissionDraft],
  );
  const isBatchDraft = batchJobs.length > 1;
  const selectedBatchJobs = useMemo(
    () => batchJobs.filter((job) => selectedBatchIds.includes(job.id)),
    [batchJobs, selectedBatchIds],
  );
  const isAllBatchSelected = isBatchDraft && selectedBatchJobs.length === batchJobs.length;
  const singleDraftPayload = useMemo(() => {
    if (!submissionDraft) {
      return null;
    }
    const metaDraftRecord = asRecord(submissionDraft.meta.draft);
    if (metaDraftRecord) {
      return metaDraftRecord;
    }
    const metaDraftArray = toRecordArray(submissionDraft.meta.draft);
    if (metaDraftArray.length > 0) {
      return metaDraftArray[0];
    }
    return submissionDraft.inputs;
  }, [submissionDraft]);

  useEffect(() => {
    if (!open || !isBatchDraft) {
      setSelectedBatchIds([]);
      return;
    }
    setSelectedBatchIds(batchJobs.map((job) => job.id));
  }, [batchJobs, isBatchDraft, open]);

  useEffect(() => {
    if (!open || !submissionDraft) {
      setDraftState({});
      setDraftStateErrors({});
      setExpandedJsonFields({});
      setGlobalOverridePath("");
      setGlobalOverrideValue("");
      return;
    }
    const nextDraftState = buildDraftFieldEditorState(allInputEntries);
    setDraftState(nextDraftState);
    setDraftStateErrors({});
    setExpandedJsonFields({});
    const preferredOverride =
      Object.values(nextDraftState).find((field) =>
        ["kpoints_distance", "kpoint_distance", "ecutwfc", "ecutrho"].includes(
          field.path.split(".").pop()?.toLowerCase() ?? "",
        ),
      ) ?? Object.values(nextDraftState)[0];
    if (preferredOverride) {
      setGlobalOverridePath(preferredOverride.path);
      setGlobalOverrideValue(String(preferredOverride.value));
    } else {
      setGlobalOverridePath("");
      setGlobalOverrideValue("");
    }
  }, [allInputEntries, open, submissionDraft]);

  const targetComputer =
    typeof submissionDraft?.meta.target_computer === "string" && submissionDraft.meta.target_computer.trim()
      ? submissionDraft.meta.target_computer.trim()
      : null;
  const selectedJobsForSummary = isBatchDraft && selectedBatchJobs.length > 0 ? selectedBatchJobs : batchJobs;
  const symmetrySummary = useMemo(() => {
    if (isBatchDraft) {
      const symmetryValues = selectedJobsForSummary
        .map((job) => job.symmetry.trim())
        .filter((value) => value && value.toLowerCase() !== "system selected");
      const unique = [...new Set(symmetryValues)];
      if (unique.length === 0) {
        return "System selected";
      }
      if (unique.length === 1) {
        return unique[0];
      }
      return `${unique.length} symmetry types`;
    }
    return (
      extractSymmetryLabel(singleDraftPayload) ??
      extractSymmetryLabel(submissionDraft?.meta.validation) ??
      "System selected"
    );
  }, [isBatchDraft, selectedJobsForSummary, singleDraftPayload, submissionDraft?.meta.validation]);
  const runtimeSummary = useMemo(() => {
    if (isBatchDraft) {
      const runtimeValues = selectedJobsForSummary
        .map((job) => job.runtimeSeconds)
        .filter((value): value is number => typeof value === "number" && value > 0);
      if (runtimeValues.length === 0) {
        return "System estimated";
      }
      const totalSeconds = runtimeValues.reduce((total, value) => total + value, 0);
      return `Total ${formatRuntimeEstimate(totalSeconds)}`;
    }
    const singleRuntime =
      extractRuntimePredictionSeconds(singleDraftPayload) ??
      extractRuntimePredictionSeconds(submissionDraft?.meta.validation);
    return formatRuntimeEstimate(singleRuntime);
  }, [isBatchDraft, selectedJobsForSummary, singleDraftPayload, submissionDraft?.meta.validation]);
  const atomSummary = useMemo(() => {
    if (isBatchDraft) {
      const atoms = selectedJobsForSummary
        .map((job) => job.numAtoms)
        .filter((value): value is number => typeof value === "number" && value > 0);
      if (atoms.length === 0) {
        return "N/A";
      }
      const total = atoms.reduce((sum, value) => sum + value, 0);
      return `${total} atoms total`;
    }
    const direct = toPositiveInteger(
      submissionDraft?.meta.num_atoms ??
      findFirstNamedValue(singleDraftPayload, new Set(["num_atoms", "natoms", "number_of_atoms"])),
    );
    return direct ? `${direct} atoms` : "N/A";
  }, [isBatchDraft, selectedJobsForSummary, singleDraftPayload, submissionDraft?.meta.num_atoms]);
  const keyParameterEntries = useMemo(() => {
    const source = submissionDraft?.inputs ?? {};
    const kpoints =
      findFirstNamedValue(source, new Set(["kpoints_distance", "kpoint_distance", "kpoints_mesh", "kpoints"])) ??
      findFirstNamedValue(submissionDraft?.meta.validation, new Set(["kpoints_distance", "kpoint_distance", "kpoints_mesh", "kpoints"]));
    const ecutwfc = findFirstNamedValue(source, new Set(["ecutwfc"]));
    const ecutrho = findFirstNamedValue(source, new Set(["ecutrho"]));
    const cutoffs = [ecutwfc !== null && ecutwfc !== undefined ? `ecutwfc=${stringifyCompact(ecutwfc)}` : null, ecutrho !== null && ecutrho !== undefined ? `ecutrho=${stringifyCompact(ecutrho)}` : null]
      .filter((item): item is string => Boolean(item))
      .join(", ");
    return [
      { label: "Code", value: primaryFields.code?.value ?? "System Selected" },
      { label: "K-points", value: kpoints ?? "Default" },
      { label: "Cutoffs", value: cutoffs || "Default" },
    ];
  }, [primaryFields.code?.value, submissionDraft?.inputs, submissionDraft?.meta.validation]);
  const canClose = state.status !== "submitting";

  if (!open || !submissionDraft || turnId === null) {
    return null;
  }

  const renderPrimaryCell = (
    key: string,
    title: string,
    field: SubmissionPrimaryInputField | null,
    missingLabel: string,
  ) => {
    const fieldPk = toPositiveInteger(field?.pk);
    return (
      <div
        key={`${turnId}-primary-${key}`}
        className="rounded-xl border border-slate-200/85 bg-white/85 px-3 py-3 dark:border-slate-800 dark:bg-slate-950/50"
      >
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">{title}</p>
        {field && !isMissingValue(field.value) ? (
          <div className="mt-2 text-sm text-slate-800 dark:text-slate-100">
            {fieldPk !== null ? (
              <button
                type="button"
                className="break-all text-left font-semibold text-sky-700 underline decoration-dotted underline-offset-2 transition-colors hover:text-sky-900 dark:text-sky-300 dark:hover:text-sky-200"
                onClick={() => onOpenDetail(fieldPk)}
                title={stringifyCompact(field.value)}
              >
                {stringifyCompact(field.value)}
              </button>
            ) : (
              renderValueNode(field.value, `${turnId}-primary-${key}`, onOpenDetail)
            )}
          </div>
        ) : (
          <span className="mt-2 inline-flex rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500 dark:bg-slate-800 dark:text-slate-300">
            {missingLabel}
          </span>
        )}
      </div>
    );
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-slate-950/35 px-4 py-6 backdrop-blur-[1.5px]">
      <button
        type="button"
        className="absolute inset-0 cursor-default"
        aria-label="Close submission modal"
        onClick={() => {
          if (canClose) {
            onClose();
          }
        }}
      />
      <section
        className="relative z-10 h-[80vh] w-full max-w-6xl overflow-y-auto overscroll-contain rounded-2xl border border-slate-200/90 bg-white/95 p-5 shadow-[0_24px_80px_rgba(15,23,42,0.35)] dark:border-slate-800 dark:bg-slate-950/95"
        style={MODAL_FONT_STYLE}
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-blue-700/80 dark:text-blue-300/80">
              Submission Review
            </p>
            <h2 className="mt-1 text-lg font-semibold tracking-tight text-slate-900 dark:text-slate-100">
              {submissionDraft.process_label}
            </h2>
            <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[11px] text-slate-600 dark:text-slate-300">
              <span className="inline-flex rounded-full bg-slate-100/85 px-2 py-0.5 dark:bg-slate-800/80">
                Symmetry: {symmetrySummary}
              </span>
              <span className="inline-flex rounded-full bg-slate-100/85 px-2 py-0.5 dark:bg-slate-800/80">
                Time Est.: {runtimeSummary}
              </span>
              <span className="inline-flex rounded-full bg-slate-100/85 px-2 py-0.5 dark:bg-slate-800/80">
                Atoms: {atomSummary}
              </span>
              {isBatchDraft ? (
                <span className="inline-flex rounded-full bg-slate-100/85 px-2 py-0.5 dark:bg-slate-800/80">
                  {selectedBatchJobs.length}/{batchJobs.length} selected
                </span>
              ) : null}
            </div>
          </div>
          <button
            type="button"
            className="rounded-lg p-1.5 text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-700 disabled:cursor-not-allowed disabled:opacity-40 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200"
            onClick={onClose}
            disabled={!canClose}
            aria-label="Close modal"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="mt-3 grid gap-2 md:grid-cols-3">
          {keyParameterEntries.map((entry) => (
            <div
              key={`${turnId}-key-parameter-${entry.label}`}
              className="rounded-xl border border-slate-200/85 bg-slate-50/70 px-3 py-2 dark:border-slate-800 dark:bg-slate-900/35"
            >
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400">
                {entry.label}
              </p>
              <p className="mt-1 break-all text-sm text-slate-800 dark:text-slate-100" title={stringifyCompact(entry.value)}>
                {renderValueNode(entry.value, `${turnId}-key-parameter-${entry.label}`, onOpenDetail)}
              </p>
            </div>
          ))}
        </div>

        {isBatchDraft ? (
          <div className="mt-4">
            <div className="rounded-xl border border-slate-200/80 bg-slate-50/80 dark:border-slate-800 dark:bg-slate-900/35">
              <div className="flex items-center justify-between border-b border-slate-200/80 px-3 py-2 dark:border-slate-800">
                <p className="text-xs font-semibold uppercase tracking-[0.13em] text-slate-500 dark:text-slate-400">
                  High-Throughput Task List
                </p>
                <span className="text-xs text-slate-500 dark:text-slate-400">
                  {selectedBatchJobs.length}/{batchJobs.length} selected
                </span>
              </div>
              {globalOverrideOptions.length > 0 ? (
                <div className="flex flex-wrap items-center gap-2 border-b border-slate-200/70 px-3 py-2 text-xs dark:border-slate-800">
                  <span className="font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400">
                    Apply To All
                  </span>
                  <select
                    value={globalOverridePath}
                    onChange={(event) => {
                      const nextPath = event.currentTarget.value;
                      setGlobalOverridePath(nextPath);
                      const field = draftState[nextPath];
                      if (field) {
                        setGlobalOverrideValue(String(field.value));
                      }
                    }}
                    className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700 outline-none focus:border-blue-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                  >
                    {globalOverrideOptions.map((field) => (
                      <option key={`${turnId}-override-${field.path}`} value={field.path}>
                        {field.label}
                      </option>
                    ))}
                  </select>
                  {draftState[globalOverridePath]?.kind === "boolean" ? (
                    <label className="inline-flex items-center gap-1.5 text-xs text-slate-600 dark:text-slate-300">
                      <input
                        type="checkbox"
                        checked={/^true$/i.test(globalOverrideValue)}
                        onChange={(event) => {
                          setGlobalOverrideValue(event.currentTarget.checked ? "true" : "false");
                        }}
                        className="h-3.5 w-3.5 rounded border-slate-300 text-blue-600 focus:ring-blue-500 dark:border-slate-700"
                      />
                      Enabled
                    </label>
                  ) : (
                    <input
                      value={globalOverrideValue}
                      onChange={(event) => setGlobalOverrideValue(event.currentTarget.value)}
                      className="min-w-[160px] rounded-md border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700 outline-none focus:border-blue-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                      placeholder="Override value"
                    />
                  )}
                  <Button
                    type="button"
                    size="sm"
                    className="h-7 bg-blue-600 px-2.5 text-[11px] text-white hover:bg-blue-500 dark:bg-blue-500 dark:hover:bg-blue-400"
                    onClick={() => {
                      const targetPath = globalOverridePath.trim();
                      if (!targetPath) {
                        return;
                      }
                      setDraftState((current) => {
                        const field = current[targetPath];
                        if (!field) {
                          return current;
                        }
                        const nextValue =
                          field.kind === "boolean"
                            ? /^(true|1|yes|on)$/i.test(globalOverrideValue.trim())
                            : globalOverrideValue;
                        return {
                          ...current,
                          [targetPath]: {
                            ...field,
                            value: nextValue,
                          },
                        };
                      });
                      setDraftStateErrors((current) => {
                        if (!current[targetPath]) {
                          return current;
                        }
                        const next = { ...current };
                        delete next[targetPath];
                        return next;
                      });
                    }}
                  >
                    Apply
                  </Button>
                </div>
              ) : null}
              <div className="minimal-scrollbar max-h-[280px] overflow-auto">
                <table className="w-full min-w-[680px] text-left text-sm">
                  <thead className="sticky top-0 bg-slate-100/95 text-[11px] uppercase tracking-[0.12em] text-slate-500 dark:bg-slate-900/95 dark:text-slate-400">
                    <tr>
                      <th className="px-3 py-2">
                        <input
                          type="checkbox"
                          checked={isAllBatchSelected}
                          onChange={() => {
                            if (isAllBatchSelected) {
                              setSelectedBatchIds([]);
                              return;
                            }
                            setSelectedBatchIds(batchJobs.map((job) => job.id));
                          }}
                          aria-label="Select all jobs"
                          className="h-3.5 w-3.5 rounded border-slate-300 text-blue-600 focus:ring-blue-500 dark:border-slate-700"
                        />
                      </th>
                      <th className="px-3 py-2">PK</th>
                      <th className="px-3 py-2">Formula</th>
                      <th className="px-3 py-2">Symmetry</th>
                      <th className="px-3 py-2">Estimated Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {batchJobs.map((job) => {
                      const selected = selectedBatchIds.includes(job.id);
                      return (
                        <tr
                          key={`${turnId}-batch-${job.id}`}
                          className={cn(
                            "border-t border-slate-200/70 text-slate-700 dark:border-slate-800 dark:text-slate-200",
                            selected ? "bg-white/60 dark:bg-slate-950/20" : "opacity-75",
                          )}
                        >
                          <td className="px-3 py-2">
                            <input
                              type="checkbox"
                              checked={selected}
                              onChange={() => {
                                setSelectedBatchIds((current) =>
                                  current.includes(job.id)
                                    ? current.filter((id) => id !== job.id)
                                    : [...current, job.id],
                                );
                              }}
                              aria-label={`Select ${job.formula}`}
                              className="h-3.5 w-3.5 rounded border-slate-300 text-blue-600 focus:ring-blue-500 dark:border-slate-700"
                            />
                          </td>
                          <td className="px-3 py-2">
                            {job.pk ? (
                              <button
                                type="button"
                                className="font-mono text-sky-700 underline decoration-dotted underline-offset-2 transition-colors hover:text-sky-900 dark:text-sky-300 dark:hover:text-sky-200"
                                onClick={() => onOpenDetail(job.pk!)}
                              >
                                #{job.pk}
                              </button>
                            ) : (
                              <span className="text-slate-400 dark:text-slate-500">-</span>
                            )}
                          </td>
                          <td className="max-w-[220px] px-3 py-2" title={job.formula}>
                            <span className="block truncate">{job.formula}</span>
                          </td>
                          <td className="max-w-[180px] px-3 py-2" title={job.symmetry}>
                            <span className="block truncate">{job.symmetry}</span>
                          </td>
                          <td className="px-3 py-2">{job.runtimeEstimate}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        ) : (
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            {renderPrimaryCell("code", "Code", primaryFields.code, "System Selected")}
            {renderPrimaryCell("structure", "Structure", primaryFields.structure, "Default")}
            {renderPrimaryCell("pseudos", "Pseudopotentials", primaryFields.pseudos, "System Selected")}
          </div>
        )}

        <div className="mt-3 rounded-xl border border-slate-200/85 bg-slate-50/75 px-3 py-3 dark:border-slate-800 dark:bg-slate-900/35">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-[11px] font-semibold uppercase tracking-[0.13em] text-slate-500 dark:text-slate-400">
              Interactive Inputs
            </p>
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="rounded-full bg-white/80 px-2 py-0.5 text-[11px] text-slate-500 dark:bg-slate-800/80 dark:text-slate-300">
                {recommendedDraftFields.length} recommended
              </span>
              <span className="rounded-full bg-white/80 px-2 py-0.5 text-[11px] text-slate-500 dark:bg-slate-800/80 dark:text-slate-300">
                {allDraftFields.length} total ports
              </span>
            </div>
          </div>
          {allDraftFields.length > 0 ? (
            <>
              <div className="mt-2 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
                {recommendedDraftFields.map((field) => {
                  const error = draftStateErrors[field.path];
                  const isModified = isFieldModified(field);
                  return (
                    <label
                      key={`${turnId}-port-recommended-${field.path}`}
                      className={cn(
                        "rounded-lg border bg-white/90 px-2.5 py-2 text-sm dark:bg-slate-950/40",
                        isModified
                          ? "border-blue-400/90 shadow-[0_0_0_1px_rgba(59,130,246,0.2)] dark:border-blue-500/80"
                          : "border-slate-200/80 dark:border-slate-800",
                      )}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400">
                          {field.label}
                        </span>
                        <div className="flex items-center gap-1">
                          {field.isRecommended ? (
                            <span className="rounded-full bg-emerald-100 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300">
                              AI
                            </span>
                          ) : null}
                          {isModified ? (
                            <span className="rounded-full bg-blue-100 px-1.5 py-0.5 text-[10px] font-medium text-blue-700 dark:bg-blue-900/40 dark:text-blue-300">
                              Modified
                            </span>
                          ) : null}
                        </div>
                      </div>
                      <p className="mt-0.5 break-all text-[11px] text-slate-500 dark:text-slate-400" title={field.path}>
                        {field.path}
                      </p>
                      {field.kind === "boolean" ? (
                        <button
                          type="button"
                          className="mt-1.5 inline-flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300"
                          onClick={() => {
                            setDraftState((current) => ({
                              ...current,
                              [field.path]: {
                                ...field,
                                value: !Boolean(field.value),
                              },
                            }));
                            setDraftStateErrors((current) => {
                              if (!current[field.path]) {
                                return current;
                              }
                              const next = { ...current };
                              delete next[field.path];
                              return next;
                            });
                          }}
                        >
                          <span
                            className={cn(
                              "relative inline-flex h-5 w-9 items-center rounded-full transition-colors",
                              Boolean(field.value) ? "bg-blue-600" : "bg-slate-300 dark:bg-slate-700",
                            )}
                          >
                            <span
                              className={cn(
                                "inline-block h-4 w-4 transform rounded-full bg-white transition-transform",
                                Boolean(field.value) ? "translate-x-4" : "translate-x-0.5",
                              )}
                            />
                          </span>
                          <span>{Boolean(field.value) ? "Enabled" : "Disabled"}</span>
                        </button>
                      ) : field.kind === "json" ? (
                        <>
                          <button
                            type="button"
                            className="mt-1.5 rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-600 transition-colors hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                            onClick={() =>
                              setExpandedJsonFields((current) => ({
                                ...current,
                                [field.path]: !Boolean(current[field.path]),
                              }))
                            }
                          >
                            {expandedJsonFields[field.path] ? "Hide JSON Editor" : "Click to Edit JSON"}
                          </button>
                          {expandedJsonFields[field.path] ? (
                            <textarea
                              className={cn(
                                "minimal-scrollbar mt-1.5 h-24 w-full resize-y rounded-md border px-2 py-1.5 font-mono text-xs text-slate-800 outline-none transition-colors dark:bg-slate-900 dark:text-slate-100",
                                error
                                  ? "border-rose-300 focus:border-rose-500 dark:border-rose-700"
                                  : "border-slate-300 focus:border-blue-500 dark:border-slate-700",
                              )}
                              value={String(field.value)}
                              onChange={(event) => {
                                const nextValue = event.currentTarget.value;
                                setDraftState((current) => ({
                                  ...current,
                                  [field.path]: { ...field, value: nextValue },
                                }));
                                setDraftStateErrors((current) => {
                                  if (!current[field.path]) {
                                    return current;
                                  }
                                  const next = { ...current };
                                  delete next[field.path];
                                  return next;
                                });
                              }}
                            />
                          ) : null}
                        </>
                      ) : (
                        <input
                          type={field.kind === "number" ? "number" : "text"}
                          step={field.kind === "number" ? "any" : undefined}
                          className={cn(
                            "mt-1.5 w-full rounded-md border px-2 py-1.5 text-sm text-slate-800 outline-none transition-colors dark:bg-slate-900 dark:text-slate-100",
                            error
                              ? "border-rose-300 focus:border-rose-500 dark:border-rose-700"
                              : "border-slate-300 focus:border-blue-500 dark:border-slate-700",
                          )}
                          value={String(field.value)}
                          onChange={(event) => {
                            const nextValue = event.currentTarget.value;
                            setDraftState((current) => ({
                              ...current,
                              [field.path]: { ...field, value: nextValue },
                            }));
                            setDraftStateErrors((current) => {
                              if (!current[field.path]) {
                                return current;
                              }
                              const next = { ...current };
                              delete next[field.path];
                              return next;
                            });
                          }}
                        />
                      )}
                      {error ? (
                        <span className="mt-1 block text-[11px] text-rose-600 dark:text-rose-300">{error}</span>
                      ) : null}
                    </label>
                  );
                })}
              </div>

              {additionalDraftFields.length > 0 ? (
                <div className="mt-2">
                  <button
                    type="button"
                    className="inline-flex w-full items-center justify-between rounded-xl bg-white/75 px-3 py-2 text-left text-sm font-medium text-slate-700 transition-colors hover:bg-slate-100 dark:bg-slate-900/60 dark:text-slate-200 dark:hover:bg-slate-800/70"
                    onClick={() => setIsAllInputsExpanded((current) => !current)}
                    aria-expanded={isAllInputsExpanded}
                  >
                    <span>Additional Ports ({additionalDraftFields.length})</span>
                    <ChevronDown
                      className={cn(
                        "h-4 w-4 shrink-0 transition-transform duration-200",
                        isAllInputsExpanded ? "rotate-180" : "rotate-0",
                      )}
                    />
                  </button>
                  <div
                    className={cn(
                      "overflow-hidden transition-[max-height,opacity] duration-300 ease-out",
                      isAllInputsExpanded ? "mt-2 max-h-[560px] opacity-100" : "max-h-0 opacity-0",
                    )}
                  >
                    <div className="minimal-scrollbar grid max-h-[360px] gap-2 overflow-auto md:grid-cols-2 xl:grid-cols-3">
                      {additionalDraftFields.map((field) => {
                        const error = draftStateErrors[field.path];
                        const isModified = isFieldModified(field);
                        return (
                          <label
                            key={`${turnId}-port-additional-${field.path}`}
                            className={cn(
                              "rounded-lg border bg-white/90 px-2.5 py-2 text-sm dark:bg-slate-950/40",
                              isModified
                                ? "border-blue-400/90 shadow-[0_0_0_1px_rgba(59,130,246,0.2)] dark:border-blue-500/80"
                                : "border-slate-200/80 dark:border-slate-800",
                            )}
                          >
                            <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400">
                              {field.label}
                            </span>
                            <p className="mt-0.5 break-all text-[11px] text-slate-500 dark:text-slate-400" title={field.path}>
                              {field.path}
                            </p>
                            {field.kind === "boolean" ? (
                              <button
                                type="button"
                                className="mt-1.5 inline-flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300"
                                onClick={() => {
                                  setDraftState((current) => ({
                                    ...current,
                                    [field.path]: {
                                      ...field,
                                      value: !Boolean(field.value),
                                    },
                                  }));
                                  setDraftStateErrors((current) => {
                                    if (!current[field.path]) {
                                      return current;
                                    }
                                    const next = { ...current };
                                    delete next[field.path];
                                    return next;
                                  });
                                }}
                              >
                                <span
                                  className={cn(
                                    "relative inline-flex h-5 w-9 items-center rounded-full transition-colors",
                                    Boolean(field.value) ? "bg-blue-600" : "bg-slate-300 dark:bg-slate-700",
                                  )}
                                >
                                  <span
                                    className={cn(
                                      "inline-block h-4 w-4 transform rounded-full bg-white transition-transform",
                                      Boolean(field.value) ? "translate-x-4" : "translate-x-0.5",
                                    )}
                                  />
                                </span>
                                <span>{Boolean(field.value) ? "Enabled" : "Disabled"}</span>
                              </button>
                            ) : field.kind === "json" ? (
                              <>
                                <button
                                  type="button"
                                  className="mt-1.5 rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-600 transition-colors hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                                  onClick={() =>
                                    setExpandedJsonFields((current) => ({
                                      ...current,
                                      [field.path]: !Boolean(current[field.path]),
                                    }))
                                  }
                                >
                                  {expandedJsonFields[field.path] ? "Hide JSON Editor" : "Click to Edit JSON"}
                                </button>
                                {expandedJsonFields[field.path] ? (
                                  <textarea
                                    className={cn(
                                      "minimal-scrollbar mt-1.5 h-20 w-full resize-y rounded-md border px-2 py-1.5 font-mono text-xs text-slate-800 outline-none transition-colors dark:bg-slate-900 dark:text-slate-100",
                                      error
                                        ? "border-rose-300 focus:border-rose-500 dark:border-rose-700"
                                        : "border-slate-300 focus:border-blue-500 dark:border-slate-700",
                                    )}
                                    value={String(field.value)}
                                    onChange={(event) => {
                                      const nextValue = event.currentTarget.value;
                                      setDraftState((current) => ({
                                        ...current,
                                        [field.path]: { ...field, value: nextValue },
                                      }));
                                      setDraftStateErrors((current) => {
                                        if (!current[field.path]) {
                                          return current;
                                        }
                                        const next = { ...current };
                                        delete next[field.path];
                                        return next;
                                      });
                                    }}
                                  />
                                ) : null}
                              </>
                            ) : (
                              <input
                                type={field.kind === "number" ? "number" : "text"}
                                step={field.kind === "number" ? "any" : undefined}
                                className={cn(
                                  "mt-1.5 w-full rounded-md border px-2 py-1.5 text-sm text-slate-800 outline-none transition-colors dark:bg-slate-900 dark:text-slate-100",
                                  error
                                    ? "border-rose-300 focus:border-rose-500 dark:border-rose-700"
                                    : "border-slate-300 focus:border-blue-500 dark:border-slate-700",
                                )}
                                value={String(field.value)}
                                onChange={(event) => {
                                  const nextValue = event.currentTarget.value;
                                  setDraftState((current) => ({
                                    ...current,
                                    [field.path]: { ...field, value: nextValue },
                                  }));
                                  setDraftStateErrors((current) => {
                                    if (!current[field.path]) {
                                      return current;
                                    }
                                    const next = { ...current };
                                    delete next[field.path];
                                    return next;
                                  });
                                }}
                              />
                            )}
                            {error ? (
                              <span className="mt-1 block text-[11px] text-rose-600 dark:text-rose-300">{error}</span>
                            ) : null}
                          </label>
                        );
                      })}
                    </div>
                  </div>
                </div>
              ) : null}
            </>
          ) : (
            <p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400">
              No editable input ports were provided. Submission will use validated defaults.
            </p>
          )}
        </div>

        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <div className="rounded-xl border border-slate-200/85 bg-slate-50/70 px-3 py-2.5 dark:border-slate-800 dark:bg-slate-900/35">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400">Target Computer</p>
            <div className="mt-1.5 text-sm text-slate-800 dark:text-slate-100">
              {targetComputer ? (
                renderValueNode(targetComputer, `${turnId}-target`, onOpenDetail)
              ) : (
                <span className="inline-flex rounded-full bg-slate-200/80 px-2 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                  System Selected
                </span>
              )}
            </div>
          </div>
          <div className="rounded-xl border border-slate-200/85 bg-slate-50/70 px-3 py-2.5 dark:border-slate-800 dark:bg-slate-900/35">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400">Parallel Settings</p>
            {parallelEntries.length > 0 ? (
              <div className="mt-1.5 flex flex-wrap gap-1.5 text-xs text-slate-700 dark:text-slate-200">
                {parallelEntries.map(([key, value]) => (
                  <span
                    key={`${turnId}-parallel-${key}`}
                    className="rounded-full bg-white/90 px-2 py-0.5 dark:bg-slate-800/90"
                  >
                    {formatSettingKey(key)}: {renderValueNode(value, `${turnId}-parallel-${key}`, onOpenDetail)}
                  </span>
                ))}
              </div>
            ) : (
              <span className="mt-1.5 inline-flex rounded-full bg-slate-200/80 px-2 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                Default
              </span>
            )}
          </div>
        </div>

        {!isBatchDraft && pkEntries.length > 0 ? (
          <div className="mt-3 rounded-xl border border-slate-200/80 bg-slate-50/80 px-3 py-2 dark:border-slate-800 dark:bg-slate-900/30">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400">Input PKs</p>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {pkEntries.map((entry, index) => (
                <button
                  key={`${turnId}-pk-${entry.pk}-${index}`}
                  type="button"
                  className="rounded-full border border-sky-200 bg-sky-50 px-2 py-0.5 font-mono text-[11px] font-semibold text-sky-700 transition-colors hover:bg-sky-100 dark:border-sky-900/60 dark:bg-sky-950/40 dark:text-sky-200 dark:hover:bg-sky-900/50"
                  onClick={() => onOpenDetail(entry.pk)}
                  title={entry.path ?? `PK ${entry.pk}`}
                >
                  #{entry.pk}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {!isBatchDraft ? (
          <div className="mt-4">
            <button
              type="button"
              className="inline-flex w-full items-center justify-between rounded-xl bg-slate-100/85 px-3 py-2 text-left text-sm font-medium text-slate-700 transition-colors hover:bg-slate-200/70 dark:bg-slate-900/60 dark:text-slate-200 dark:hover:bg-slate-800/70"
              onClick={() => setIsAdvancedExpanded((current) => !current)}
              aria-expanded={isAdvancedExpanded}
            >
              <span>Advanced Settings ({advancedEntries.length})</span>
              <ChevronDown
                className={cn(
                  "h-4 w-4 shrink-0 transition-transform duration-200",
                  isAdvancedExpanded ? "rotate-180" : "rotate-0",
                )}
              />
            </button>
            <div
              className={cn(
                "overflow-hidden transition-[max-height,opacity] duration-300 ease-out",
                isAdvancedExpanded ? "mt-2 max-h-[360px] opacity-100" : "max-h-0 opacity-0",
              )}
            >
              {advancedEntries.length > 0 ? (
                <div className="grid gap-2 sm:grid-cols-2">
                  {advancedEntries.map(([key, value]) => (
                    <div key={`${turnId}-advanced-${key}`} className="px-1 py-0.5 text-sm text-slate-700 dark:text-slate-200">
                      <p className="text-[11px] font-medium uppercase tracking-[0.11em] text-slate-500 dark:text-slate-400">
                        {formatSettingKey(key)}
                      </p>
                      <p className="mt-0.5 break-words">{renderValueNode(value, `${turnId}-advanced-${key}`, onOpenDetail)}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  No advanced overrides detected. Validated defaults will be applied.
                </p>
              )}
            </div>
          </div>
        ) : null}

        <div className="mt-5 border-t border-slate-200/80 pt-4 dark:border-slate-800">
          {state.status === "submitted" ? (
            <div className="rounded-xl bg-emerald-50/90 px-3 py-3 dark:bg-emerald-950/35">
              <div className="flex items-center gap-3">
                <span className="relative inline-flex h-9 w-9 items-center justify-center">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-300/70 dark:bg-emerald-500/40" />
                  <span className="relative inline-flex h-9 w-9 items-center justify-center rounded-full bg-emerald-600 text-white dark:bg-emerald-500">
                    <CheckCircle2 className="h-5 w-5" />
                  </span>
                </span>
                <div>
                  <p className="text-sm font-semibold text-emerald-800 dark:text-emerald-200">Submission successful</p>
                  {Array.isArray(state.processPks) && state.processPks.length > 0 ? (
                    <div className="mt-1 flex flex-wrap gap-1.5 text-xs text-emerald-700 dark:text-emerald-300">
                      {state.processPks.slice(0, 8).map((pk) => (
                        <button
                          key={`${turnId}-submitted-${pk}`}
                          type="button"
                          className="rounded-full bg-emerald-100 px-2 py-0.5 font-mono font-semibold underline underline-offset-2 dark:bg-emerald-900/45"
                          onClick={() => onOpenDetail(pk)}
                        >
                          #{pk}
                        </button>
                      ))}
                      {state.processPks.length > 8 ? (
                        <span>+{state.processPks.length - 8} more</span>
                      ) : null}
                    </div>
                  ) : (
                    <p className="text-xs text-emerald-700 dark:text-emerald-300">
                      {state.processPk ? (
                        <button
                          type="button"
                          className="font-semibold underline underline-offset-2"
                          onClick={() => onOpenDetail(state.processPk!)}
                        >
                          PK #{state.processPk}
                        </button>
                      ) : (
                        "Process created"
                      )}
                    </p>
                  )}
                </div>
              </div>
            </div>
          ) : state.status === "cancelled" ? (
            <p className="text-sm text-slate-600 dark:text-slate-300">Submission cancelled.</p>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <Button
                size="sm"
                className="bg-blue-600 text-white hover:bg-blue-500 dark:bg-blue-500 dark:hover:bg-blue-400"
                onClick={() => {
                  const { valuesByPath, errors } = parseDraftFieldEditorState(draftState);
                  if (Object.keys(errors).length > 0) {
                    setDraftStateErrors(errors);
                    return;
                  }
                  setDraftStateErrors({});

                  const selectedDraft: SubmissionSubmitDraft = isBatchDraft
                    ? selectedBatchJobs.map((job) => job.draft)
                    : (() => {
                        const metaDraftRecord = asRecord(submissionDraft.meta.draft);
                        if (metaDraftRecord) {
                          return metaDraftRecord;
                        }
                        const metaDraftArray = toRecordArray(submissionDraft.meta.draft);
                        if (metaDraftArray.length > 0) {
                          return metaDraftArray[0];
                        }
                        return submissionDraft.inputs;
                      })();
                  const mergedDraft = applyEditorValuesToSubmitDraft(
                    selectedDraft,
                    valuesByPath,
                  );
                  onConfirm(mergedDraft);
                }}
                disabled={
                  state.status === "submitting" ||
                  isBusy ||
                  (isBatchDraft && selectedBatchJobs.length === 0)
                }
              >
                {state.status === "submitting" ? (
                  <span className="inline-flex items-center gap-1">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Submitting...
                  </span>
                ) : isBatchDraft ? (
                  "Launch All"
                ) : (
                  "Launch"
                )}
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="border-slate-300 bg-white/80 text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800"
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
    </div>
  );
}
