import { AlertTriangle, CheckCircle2, ChevronDown, ChevronRight, Folder, Loader2, X } from "lucide-react";
import { type ReactNode, useCallback, useEffect, useMemo, useState, useRef } from "react";

import { Button } from "@/components/ui/button";
import { CommandPaletteSelect } from "@/components/ui/command-palette-select";
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

type SubmissionInputProperty = {
  path: string;
  key: string;
  label?: string;
  value?: unknown;
  ui_type?: string;
  editor_hint?: string | null;
  is_recommended?: boolean;
};

type SubmissionInputPort = {
  path: string;
  label?: string;
  ui_type?: string;
  editor_hint?: string | null;
  is_recommended?: boolean;
  properties?: SubmissionInputProperty[];
};

type SubmissionInputGroup = {
  id: string;
  title: string;
  ports?: SubmissionInputPort[];
};

type SubmissionAvailableCode = {
  value?: string;
  label?: string;
  code_label?: string;
  computer_label?: string;
  plugin?: string | null;
  pk?: number | null;
};

type SubmissionPortSpecPort = {
  path?: string;
  kind?: string;
  required?: boolean;
};

type SubmissionPortSpec = {
  entry_point?: string;
  namespaces?: string[];
  ports?: SubmissionPortSpecPort[];
  code_paths?: string[];
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

type SubmissionPrimaryFields = {
  code: SubmissionPrimaryInputField | null;
  structure: SubmissionPrimaryInputField | null;
  pseudos: SubmissionPrimaryInputField | null;
};

export type SubmissionSubmitDraft = Record<string, unknown> | Array<Record<string, unknown>>;

export type SubmissionDraftPayload = {
  process_label: string;
  inputs: Record<string, unknown>;
  input_groups?: SubmissionInputGroup[];
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
    input_groups?: SubmissionInputGroup[] | null;
    structure_metadata?: SubmissionStructureMetadata[] | null;
    symmetry?: string | null;
    num_atoms?: number | null;
    estimated_runtime?: unknown;
    available_codes?: SubmissionAvailableCode[] | null;
    required_code_plugin?: string | null;
    port_spec?: SubmissionPortSpec | null;
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
  mode?: "modal" | "inline";
  expanded?: boolean;
  onToggleExpanded?: () => void;
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
    const joined = compact.join(", ");
    const trailer = value.length > compact.length ? " ..." : "";
    return `${joined}${trailer}`;
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

type NormalizedCodeOption = {
  value: string;
  label: string;
  codeLabel: string | null;
  computerLabel: string | null;
  plugin: string | null;
  pk: number | null;
};

type NormalizedPortSpec = {
  namespaces: string[];
  codePaths: Set<string>;
  requiredCodePaths: Set<string>;
};

function normalizeCodeOptions(raw: unknown): NormalizedCodeOption[] {
  if (!Array.isArray(raw)) {
    return [];
  }
  const options: NormalizedCodeOption[] = [];
  const seen = new Set<string>();
  raw.forEach((item) => {
    if (typeof item === "string" && item.trim()) {
      const text = item.trim();
      if (seen.has(text)) {
        return;
      }
      seen.add(text);
      const [codeLabel, computerLabelRaw] = text.split("@", 2);
      options.push({
        value: text,
        label: text,
        codeLabel: codeLabel?.trim() || text,
        computerLabel: computerLabelRaw?.trim() || null,
        plugin: null,
        pk: null,
      });
      return;
    }

    const record = asRecord(item);
    if (!record) {
      return;
    }
    const codeLabel =
      typeof record.code_label === "string" && record.code_label.trim()
        ? record.code_label.trim()
        : typeof record.label === "string" && record.label.trim()
          ? record.label.trim()
          : typeof record.value === "string" && record.value.trim()
            ? record.value.trim()
            : "";
    const computerLabel =
      typeof record.computer_label === "string" && record.computer_label.trim()
        ? record.computer_label.trim()
        : null;
    const value =
      typeof record.value === "string" && record.value.trim()
        ? record.value.trim()
        : computerLabel && codeLabel
          ? `${codeLabel} @${computerLabel} `
          : codeLabel;
    if (!value) {
      return;
    }
    if (seen.has(value)) {
      return;
    }
    seen.add(value);
    options.push({
      value,
      label:
        typeof record.label === "string" && record.label.trim()
          ? record.label.trim()
          : value,
      codeLabel: codeLabel || null,
      computerLabel,
      plugin:
        typeof record.plugin === "string" && record.plugin.trim() ? record.plugin.trim() : null,
      pk: toPositiveInteger(record.pk),
    });
  });
  return options.sort((left, right) => left.label.localeCompare(right.label));
}

function normalizePortSpec(raw: unknown): NormalizedPortSpec {
  const record = asRecord(raw);
  if (!record) {
    return { namespaces: [], codePaths: new Set<string>(), requiredCodePaths: new Set<string>() };
  }

  const namespaceSet = new Set<string>();
  const rawNamespaces = Array.isArray(record.namespaces) ? record.namespaces : [];
  rawNamespaces.forEach((entry) => {
    if (typeof entry !== "string") {
      return;
    }
    const cleaned = stripTechnicalPrefix(entry);
    if (!cleaned) {
      return;
    }
    const segments = cleaned.split(".").map((segment) => segment.trim()).filter(Boolean);
    segments.forEach((_, index) => {
      namespaceSet.add(segments.slice(0, index + 1).join("."));
    });
  });

  const codePaths = new Set<string>();
  const requiredCodePaths = new Set<string>();
  const rawCodePaths = Array.isArray(record.code_paths) ? record.code_paths : [];
  rawCodePaths.forEach((entry) => {
    if (typeof entry !== "string") {
      return;
    }
    const cleaned = stripTechnicalPrefix(entry);
    if (cleaned) {
      codePaths.add(cleaned);
    }
  });

  const rawPorts = Array.isArray(record.ports) ? record.ports : [];
  rawPorts.forEach((entry) => {
    const portRecord = asRecord(entry);
    if (!portRecord) {
      return;
    }
    const rawPath = typeof portRecord.path === "string" ? portRecord.path.trim() : "";
    if (!rawPath) {
      return;
    }
    const path = stripTechnicalPrefix(rawPath);
    if (!path) return;

    const kind = typeof portRecord.kind === "string" ? portRecord.kind.trim().toLowerCase() : "";
    if (kind === "code") {
      codePaths.add(path);
      if (portRecord.required === true) {
        requiredCodePaths.add(path);
      }
    }
  });

  return {
    namespaces: [...namespaceSet].sort((left, right) => {
      const depthDelta = left.split(".").length - right.split(".").length;
      return depthDelta !== 0 ? depthDelta : left.localeCompare(right);
    }),
    codePaths,
    requiredCodePaths,
  };
}

function sortPathsByDepth(left: string, right: string): number {
  const depthDelta = left.split(".").length - right.split(".").length;
  return depthDelta !== 0 ? depthDelta : left.localeCompare(right);
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

function looksLikeCodeKey(key: string): boolean {
  const lowered = key.trim().toLowerCase();
  return lowered === "code" || lowered === "code_label" || lowered === "codes" || lowered.endsWith("_code");
}

function findFirstMatchingValue(
  payload: unknown,
  predicate: (key: string, value: unknown) => boolean,
): unknown {
  if (Array.isArray(payload)) {
    for (const item of payload) {
      const nested = findFirstMatchingValue(item, predicate);
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
    if (predicate(key, value) && !isMissingValue(value)) {
      return value;
    }
    const nested = findFirstMatchingValue(value, predicate);
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
    value: pk !== null && label.toLowerCase() === "structure" ? `PK ${pk} ` : stringifyCompact(value),
    pk: pk !== null && label.toLowerCase() === "structure" ? pk : undefined,
  };
}

function extractPrimaryFields(submissionDraft: SubmissionDraftPayload): SubmissionPrimaryFields {
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
  const fallbackCode = findFirstMatchingValue(inputs, (key) => looksLikeCodeKey(key));
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
          key={`${seed} -${start} -${pk} `}
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

function isNodeMetadataEnvelope(value: unknown): value is Record<string, unknown> {
  const record = asRecord(value);
  if (!record) {
    return false;
  }
  const loweredKeys = new Set(
    Object.keys(record)
      .map((key) => key.trim().toLowerCase())
      .filter(Boolean),
  );
  if (loweredKeys.size === 0) {
    return false;
  }
  if (loweredKeys.has("pk") || loweredKeys.has("uuid")) {
    return true;
  }
  if (loweredKeys.has("type") && loweredKeys.has("value")) {
    return true;
  }
  return loweredKeys.has("node_type") || loweredKeys.has("full_type");
}

function coerceNodeEnvelopeValue(value: unknown): unknown {
  const record = asRecord(value);
  if (!record) {
    return value;
  }
  for (const candidateKey of ["value", "payload", "label", "name", "full_label", "code", "family"]) {
    const candidate = record[candidateKey];
    if (candidate === null || candidate === undefined) {
      continue;
    }
    if (typeof candidate === "string" && !candidate.trim()) {
      continue;
    }
    return candidate;
  }
  return value;
}

function summarizeNodeMetadataEnvelope(value: unknown): string {
  const record = asRecord(value);
  if (!record) {
    return "AiiDA node";
  }
  const label = typeof record.label === "string" && record.label.trim() ? record.label.trim() : "";
  const type =
    (typeof record.type === "string" && record.type.trim() ? record.type.trim() : "") ||
    (typeof record.node_type === "string" && record.node_type.trim() ? record.node_type.trim() : "Node");
  const pk = typeof record.pk === "number" && Number.isFinite(record.pk) ? Math.trunc(record.pk) : null;
  if (label && pk !== null) {
    return `${label} (#${pk})`;
  }
  if (label) {
    return label;
  }
  if (pk !== null) {
    return `${type} #${pk}`;
  }
  return `Unstored ${type}`;
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
    const path = prefix ? `${prefix}.${cleanKey} ` : cleanKey;
    if (isNodeMetadataEnvelope(value)) {
      out[path] = coerceNodeEnvelopeValue(value);
      return;
    }
    if (asRecord(value)) {
      flattenInputPorts(value, path, out);
      return;
    }
    out[path] = value;
  });
  return out;
}

const INTERNAL_METADATA_KEYS = new Set([
  "success",
  "status",
  "entry_point",
  "protocol",
  "intent_data",
  "overrides",
  "signature",
  "pseudo_expectations",
  "preview",
  "errors",
  "missing_ports",
  "builder_inputs",
]);

function stripTechnicalPrefix(path: string): string {
  const trimmed = path.trim();
  if (trimmed.toLowerCase().startsWith("builder_inputs.")) {
    return trimmed.substring("builder_inputs.".length).trim();
  }
  if (trimmed.toLowerCase() === "builder_inputs") {
    return "";
  }
  return trimmed;
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
      const rawNormalizedPath = path.trim();
      if (!rawNormalizedPath) {
        return;
      }
      const normalizedPath = stripTechnicalPrefix(rawNormalizedPath);
      if (!normalizedPath || seen.has(normalizedPath)) {
        return;
      }

      const rootKey = normalizedPath.split(".")[0].toLowerCase();
      if (INTERNAL_METADATA_KEYS.has(rootKey)) {
        return;
      }

      seen.add(normalizedPath);
      const entryRecord = asRecord(rawValue);
      const hasValueField = entryRecord && Object.prototype.hasOwnProperty.call(entryRecord, "value");
      const entryValue = hasValueField
        ? coerceNodeEnvelopeValue(entryRecord?.value)
        : isNodeMetadataEnvelope(rawValue)
          ? coerceNodeEnvelopeValue(rawValue)
          : rawValue;
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

  const rawInputs = asRecord(submissionDraft.inputs) ?? {};
  const builderInputs = asRecord(rawInputs.builder_inputs);
  // Promote builder_inputs if it is the primary container for workflow parameters
  const source = (builderInputs && Object.keys(builderInputs).length > 0) ? builderInputs : rawInputs;

  const flattened = flattenInputPorts(source);
  Object.entries(flattened).forEach(([path, value]) => {
    const rawNormalizedPath = path.trim();
    if (!rawNormalizedPath) {
      return;
    }
    const normalizedPath = stripTechnicalPrefix(rawNormalizedPath);
    if (!normalizedPath || seen.has(normalizedPath)) {
      return;
    }

    const rootKey = normalizedPath.split(".")[0].toLowerCase();
    if (INTERNAL_METADATA_KEYS.has(rootKey)) {
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

type NormalizedInputProperty = {
  path: string;
  key: string;
  label: string;
  uiType: string;
  editorHint: string | null;
  isRecommended: boolean;
};

type NormalizedInputPort = {
  path: string;
  label: string;
  uiType: string;
  editorHint: string | null;
  isRecommended: boolean;
  properties: NormalizedInputProperty[];
};

type NormalizedInputGroup = {
  id: string;
  title: string;
  ports: NormalizedInputPort[];
};

const INPUT_GROUP_TITLE: Record<string, string> = {
  computational_details: "Computational Details",
  brillouin_zone: "Brillouin Zone",
  system_environment: "System Environment",
  physics_protocol: "Physics Protocol",
};

const INPUT_GROUP_ORDER = [
  "computational_details",
  "brillouin_zone",
  "system_environment",
  "physics_protocol",
];

function inferUiTypeFromPathAndValue(path: string, value: unknown): string {
  const lowered = path.trim().toLowerCase();
  if ((lowered.includes("kpoint") || lowered.includes("kpoints")) && (lowered.endsWith(".mesh") || lowered.includes(".mesh."))) {
    return "mesh";
  }
  if (Array.isArray(value) && value.length === 3 && value.every((item) => typeof item === "number")) {
    return "mesh";
  }
  if (typeof value === "boolean") {
    return "toggle";
  }
  if (Array.isArray(value) || asRecord(value)) {
    return "dict";
  }
  return "scalar";
}

function classifyInputGroup(path: string): string {
  const lowered = path.trim().toLowerCase();
  const leaf = lowered.split(".").pop() ?? lowered;
  if (
    lowered.includes("metadata.options") ||
    lowered.includes(".resources.") ||
    ["resources", "queue_name", "max_wallclock_seconds", "account"].includes(leaf)
  ) {
    return "system_environment";
  }
  if (
    lowered.includes("kpoint") ||
    lowered.includes("kpoints") ||
    ["mesh", "kpoints_distance", "kpoint_distance"].includes(leaf)
  ) {
    return "brillouin_zone";
  }
  if (
    [
      "relax_type",
      "protocol",
      "pseudo_family",
      "pseudo_family_label",
      "pseudopotential",
      "electronic_type",
      "spin_type",
    ].some((token) => lowered.includes(token))
  ) {
    return "physics_protocol";
  }
  if (lowered.includes(".parameters") || lowered.startsWith("parameters")) {
    return "computational_details";
  }
  return "computational_details";
}

function derivePortPath(path: string, groupId: string): string {
  const segments = path.split(".").map((segment) => segment.trim()).filter(Boolean);
  const lowered = segments.map((segment) => segment.toLowerCase());

  if (groupId === "system_environment") {
    for (let index = 0; index < segments.length - 1; index += 1) {
      if (lowered[index] === "metadata" && lowered[index + 1] === "options") {
        const base = segments.slice(0, index + 2);
        if (lowered[index + 2] === "resources") {
          base.push(segments[index + 2]);
        }
        return base.join(".");
      }
    }
  }

  if (groupId === "computational_details") {
    const parametersIndex = lowered.findIndex((segment) => segment === "parameters");
    if (parametersIndex >= 0) {
      return segments.slice(0, parametersIndex + 1).join(".");
    }
  }

  if (groupId === "brillouin_zone") {
    const kpointIndex = lowered.findIndex((segment) => segment.includes("kpoint"));
    if (kpointIndex >= 0) {
      return segments.slice(0, kpointIndex + 1).join(".");
    }
    const meshIndex = lowered.findIndex((segment) => segment === "mesh");
    if (meshIndex >= 0) {
      return segments.slice(0, meshIndex + 1).join(".");
    }
  }

  if (groupId === "physics_protocol") {
    const protocolIndex = lowered.findIndex((segment) =>
      ["relax_type", "protocol", "pseudo_family", "pseudo_family_label"].includes(segment),
    );
    if (protocolIndex >= 0) {
      return segments.slice(0, protocolIndex + 1).join(".");
    }
  }

  if (segments.length <= 1) {
    return path;
  }
  return segments.slice(0, -1).join(".");
}

function inferEditorHint(path: string, uiType: string): string | null {
  const lowered = path.trim().toLowerCase();
  if (uiType === "mesh") {
    return "mesh";
  }
  if (lowered.includes("metadata.options.resources")) {
    return "resource_grid";
  }
  if (uiType === "dict") {
    return "property_grid";
  }
  return null;
}

function normalizeInputGroupsFromPayload(raw: unknown): NormalizedInputGroup[] {
  if (!Array.isArray(raw)) {
    return [];
  }
  const groups: NormalizedInputGroup[] = [];
  raw.forEach((entry) => {
    const groupRecord = asRecord(entry);
    if (!groupRecord) {
      return;
    }
    const id = typeof groupRecord.id === "string" && groupRecord.id.trim() ? groupRecord.id.trim() : "";
    if (!id) {
      return;
    }
    const title =
      typeof groupRecord.title === "string" && groupRecord.title.trim()
        ? groupRecord.title.trim()
        : (INPUT_GROUP_TITLE[id] ?? formatSettingKey(id));
    const portsRaw = Array.isArray(groupRecord.ports) ? groupRecord.ports : [];
    const ports: NormalizedInputPort[] = [];
    portsRaw.forEach((rawPort) => {
      const portRecord = asRecord(rawPort);
      if (!portRecord) {
        return;
      }
      const path = typeof portRecord.path === "string" && portRecord.path.trim() ? portRecord.path.trim() : "";
      if (!path) {
        return;
      }
      const label =
        typeof portRecord.label === "string" && portRecord.label.trim()
          ? portRecord.label.trim()
          : formatSettingKey(path.split(".").pop() ?? path);
      const uiType =
        typeof portRecord.ui_type === "string" && portRecord.ui_type.trim()
          ? portRecord.ui_type.trim()
          : "dict";
      const editorHint =
        typeof portRecord.editor_hint === "string" && portRecord.editor_hint.trim()
          ? portRecord.editor_hint.trim()
          : inferEditorHint(path, uiType);
      const propertiesRaw = Array.isArray(portRecord.properties) ? portRecord.properties : [];
      const properties: NormalizedInputProperty[] = [];
      propertiesRaw.forEach((rawProperty) => {
        const propertyRecord = asRecord(rawProperty);
        if (!propertyRecord) {
          return;
        }
        const propertyPath =
          typeof propertyRecord.path === "string" && propertyRecord.path.trim()
            ? propertyRecord.path.trim()
            : path;
        const key =
          typeof propertyRecord.key === "string" && propertyRecord.key.trim()
            ? propertyRecord.key.trim()
            : propertyPath;
        const propertyUiType =
          typeof propertyRecord.ui_type === "string" && propertyRecord.ui_type.trim()
            ? propertyRecord.ui_type.trim()
            : inferUiTypeFromPathAndValue(propertyPath, propertyRecord.value);
        properties.push({
          path: propertyPath,
          key,
          label:
            typeof propertyRecord.label === "string" && propertyRecord.label.trim()
              ? propertyRecord.label.trim()
              : formatSettingKey(key.split(".").pop() ?? key),
          uiType: propertyUiType,
          editorHint:
            typeof propertyRecord.editor_hint === "string" && propertyRecord.editor_hint.trim()
              ? propertyRecord.editor_hint.trim()
              : inferEditorHint(propertyPath, propertyUiType),
          isRecommended: Boolean(propertyRecord.is_recommended),
        });
      });
      if (properties.length === 0) {
        properties.push({
          path,
          key: path,
          label,
          uiType,
          editorHint,
          isRecommended: Boolean(portRecord.is_recommended),
        });
      }
      ports.push({
        path,
        label,
        uiType,
        editorHint,
        isRecommended: Boolean(portRecord.is_recommended),
        properties,
      });
    });
    if (ports.length > 0) {
      groups.push({ id, title, ports });
    }
  });
  return groups;
}

function buildFallbackInputGroups(entries: SubmissionAllInputEntry[]): NormalizedInputGroup[] {
  const grouped = new Map<string, Map<string, NormalizedInputPort>>();
  entries.forEach((entry) => {
    const groupId = classifyInputGroup(entry.path);
    const portPath = derivePortPath(entry.path, groupId);
    let groupPorts = grouped.get(groupId);
    if (!groupPorts) {
      groupPorts = new Map<string, NormalizedInputPort>();
      grouped.set(groupId, groupPorts);
    }
    const existing = groupPorts.get(portPath);
    const uiType = inferUiTypeFromPathAndValue(entry.path, entry.value);
    const propertyKey = entry.path.startsWith(`${portPath}.`) ? entry.path.slice(portPath.length + 1) : entry.path;
    const property: NormalizedInputProperty = {
      path: entry.path,
      key: propertyKey || entry.path,
      label: formatSettingKey((propertyKey || entry.path).split(".").pop() ?? entry.path),
      uiType,
      editorHint: inferEditorHint(entry.path, uiType),
      isRecommended: entry.isRecommended,
    };
    if (!existing) {
      groupPorts.set(portPath, {
        path: portPath,
        label: formatSettingKey((portPath.split(".").pop() ?? portPath) || portPath),
        uiType: uiType,
        editorHint: inferEditorHint(portPath, uiType),
        isRecommended: entry.isRecommended,
        properties: [property],
      });
      return;
    }
    existing.properties.push(property);
    existing.isRecommended = existing.isRecommended || entry.isRecommended;
    if (uiType === "mesh") {
      existing.uiType = "mesh";
      existing.editorHint = "mesh";
      return;
    }
    existing.uiType = existing.properties.length > 1 ? "dict" : uiType;
    existing.editorHint = inferEditorHint(existing.path, existing.uiType);
  });

  const groups: NormalizedInputGroup[] = [];
  INPUT_GROUP_ORDER.forEach((groupId) => {
    const portsMap = grouped.get(groupId);
    if (!portsMap || portsMap.size === 0) {
      return;
    }
    const ports = [...portsMap.values()]
      .map((port) => ({
        ...port,
        properties: [...port.properties].sort((left, right) => left.key.localeCompare(right.key)),
      }))
      .sort((left, right) => left.path.localeCompare(right.path));
    groups.push({
      id: groupId,
      title: INPUT_GROUP_TITLE[groupId] ?? formatSettingKey(groupId),
      ports,
    });
  });
  return groups;
}

function buildInputGroupsForModal(
  submissionDraft: SubmissionDraftPayload,
  entries: SubmissionAllInputEntry[],
): NormalizedInputGroup[] {
  const fromTopLevel = normalizeInputGroupsFromPayload(submissionDraft.input_groups);
  if (fromTopLevel.length > 0) {
    return fromTopLevel;
  }
  const fromMeta = normalizeInputGroupsFromPayload(submissionDraft.meta.input_groups);
  if (fromMeta.length > 0) {
    return fromMeta;
  }
  return buildFallbackInputGroups(entries);
}

function toMessageList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  const seen = new Set<string>();
  const messages: string[] = [];
  value.forEach((entry) => {
    let message = "";
    if (typeof entry === "string") {
      message = entry.trim();
    } else if (entry && typeof entry === "object") {
      const record = entry as Record<string, unknown>;
      const candidate =
        record.message ?? record.error ?? record.detail ?? record.reason ?? record.title ?? record.path;
      message = String(candidate ?? "").trim();
    } else {
      message = String(entry ?? "").trim();
    }
    if (!message || seen.has(message)) {
      return;
    }
    seen.add(message);
    messages.push(message);
  });
  return messages;
}

function normalizeValidationSummary(
  summary: SubmissionValidationSummary | null | undefined,
  validation: Record<string, unknown> | null | undefined,
): SubmissionValidationSummary | null {
  const summaryRecord = summary ?? {};
  const validationRecord = validation ?? {};
  const summaryErrors = toMessageList(summaryRecord.errors);
  const summaryWarnings = toMessageList(summaryRecord.warnings);
  const validationErrors = toMessageList(
    validationRecord.errors ?? validationRecord.validation_errors ?? validationRecord.missing_inputs,
  );
  const validationWarnings = toMessageList(
    validationRecord.warnings ?? validationRecord.validation_warnings,
  );
  const errors = summaryErrors.length > 0 ? summaryErrors : validationErrors;
  const warnings = summaryWarnings.length > 0 ? summaryWarnings : validationWarnings;

  const statusRaw = summaryRecord.status ?? validationRecord.status;
  const status = typeof statusRaw === "string" ? statusRaw.trim() : "";
  const statusUpper = status.toUpperCase();
  let isValid: boolean;
  if (typeof summaryRecord.is_valid === "boolean") {
    isValid = summaryRecord.is_valid;
  } else if (typeof validationRecord.is_valid === "boolean") {
    isValid = Boolean(validationRecord.is_valid);
  } else if (statusUpper === "VALIDATION_OK" || statusUpper === "VALID" || statusUpper === "SUCCESS") {
    isValid = true;
  } else if (statusUpper === "VALIDATION_FAILED" || statusUpper === "INVALID" || statusUpper === "ERROR") {
    isValid = false;
  } else {
    isValid = errors.length === 0;
  }

  if (!status && errors.length === 0 && warnings.length === 0 && summary === null && validation === null) {
    return null;
  }

  const blockingErrorCountRaw = summaryRecord.blocking_error_count;
  const warningCountRaw = summaryRecord.warning_count;
  const blockingErrorCount =
    typeof blockingErrorCountRaw === "number" && Number.isFinite(blockingErrorCountRaw)
      ? Math.max(0, Math.floor(blockingErrorCountRaw))
      : errors.length;
  const warningCount =
    typeof warningCountRaw === "number" && Number.isFinite(warningCountRaw)
      ? Math.max(0, Math.floor(warningCountRaw))
      : warnings.length;
  const normalizedStatus = status || (isValid ? "VALIDATION_OK" : "VALIDATION_FAILED");
  const summaryText =
    typeof summaryRecord.summary_text === "string" && summaryRecord.summary_text.trim()
      ? summaryRecord.summary_text.trim()
      : `Status: ${normalizedStatus} \nBlocking errors: ${blockingErrorCount} \nWarnings: ${warningCount} `;

  return {
    status: normalizedStatus,
    is_valid: isValid,
    blocking_error_count: blockingErrorCount,
    warning_count: warningCount,
    errors,
    warnings,
    summary_text: summaryText,
  };
}

function buildInspectorInputEntries(entries: SubmissionAllInputEntry[]): SubmissionAllInputEntry[] {
  const seen = new Set<string>();
  const filtered: SubmissionAllInputEntry[] = [];
  entries.forEach((entry) => {
    const path = entry.path.trim();
    if (!path) {
      return;
    }
    const normalizedPath = path.toLowerCase();
    if (seen.has(normalizedPath)) {
      return;
    }
    seen.add(normalizedPath);
    filtered.push(entry);
  });

  return filtered.sort((left, right) => left.path.localeCompare(right.path));
}

type NamespaceTreeIndex = {
  namespaces: string[];
  childrenByNamespace: Record<string, string[]>;
  leavesByNamespace: Record<string, SubmissionAllInputEntry[]>;
  atomicEntries: SubmissionAllInputEntry[];
};

function buildNamespaceTreeIndex(
  entries: SubmissionAllInputEntry[],
  specNamespaces: string[] = [],
): NamespaceTreeIndex {
  const namespaceSet = new Set<string>([""]);
  const childrenMap = new Map<string, Set<string>>();
  const leavesMap = new Map<string, SubmissionAllInputEntry[]>();
  const atomicEntries: SubmissionAllInputEntry[] = [];

  const registerNamespace = (namespace: string) => {
    const cleaned = namespace.trim();
    if (cleaned) {
      namespaceSet.add(cleaned);
    }
  };

  const registerChildNamespace = (parent: string, child: string) => {
    const parentKey = parent.trim();
    const childKey = child.trim();
    if (!childKey) {
      return;
    }
    registerNamespace(childKey);
    const parentChildren = childrenMap.get(parentKey) ?? new Set<string>();
    parentChildren.add(childKey);
    childrenMap.set(parentKey, parentChildren);
  };

  const appendLeaf = (namespace: string, entry: SubmissionAllInputEntry) => {
    const current = leavesMap.get(namespace) ?? [];
    current.push(entry);
    leavesMap.set(namespace, current);
  };

  entries.forEach((entry) => {
    const segments = entry.path
      .split(".")
      .map((segment) => segment.trim())
      .filter(Boolean);
    if (segments.length === 0) {
      return;
    }
    if (segments.length === 1) {
      atomicEntries.push(entry);
      appendLeaf("", entry);
      return;
    }

    for (let index = 1; index < segments.length; index += 1) {
      const namespace = segments.slice(0, index).join(".");
      const parent = index === 1 ? "" : segments.slice(0, index - 1).join(".");
      registerChildNamespace(parent, namespace);
    }
    // Correctly nest the leaf under its parent namespace
    const leafNamespace = segments.length > 1 ? segments.slice(0, -1).join(".") : "";
    appendLeaf(leafNamespace, entry);
  });

  specNamespaces.forEach((namespacePath) => {
    const segments = namespacePath
      .split(".")
      .map((segment) => segment.trim())
      .filter(Boolean);
    if (segments.length === 0) {
      return;
    }
    for (let index = 1; index <= segments.length; index += 1) {
      const namespace = segments.slice(0, index).join(".");
      const parent = index === 1 ? "" : segments.slice(0, index - 1).join(".");
      registerChildNamespace(parent, namespace);
    }
  });

  const childrenByNamespace: Record<string, string[]> = {};
  childrenMap.forEach((children, namespace) => {
    childrenByNamespace[namespace] = [...children].sort((left, right) => left.localeCompare(right));
  });

  const leavesByNamespace: Record<string, SubmissionAllInputEntry[]> = {};
  leavesMap.forEach((leaves, namespace) => {
    leavesByNamespace[namespace] = [...leaves].sort((left, right) => left.path.localeCompare(right.path));
  });

  return {
    namespaces: [...namespaceSet].sort((left, right) => {
      if (left === "") {
        return -1;
      }
      if (right === "") {
        return 1;
      }
      const depthDelta = left.split(".").length - right.split(".").length;
      return depthDelta !== 0 ? depthDelta : left.localeCompare(right);
    }),
    childrenByNamespace,
    leavesByNamespace,
    atomicEntries: atomicEntries.sort((left, right) => left.path.localeCompare(right.path)),
  };
}

type NamespaceSidebarItem = {
  path: string;
  depth: number;
};

function flattenNamespaceTree(childrenByNamespace: Record<string, string[]>): NamespaceSidebarItem[] {
  const flattened: NamespaceSidebarItem[] = [];
  const walk = (namespace: string, depth: number) => {
    const children = childrenByNamespace[namespace] ?? [];
    children.forEach((child) => {
      flattened.push({ path: child, depth });
      walk(child, depth + 1);
    });
  };
  walk("", 0);
  return flattened;
}

function collectCodePaths(
  entries: SubmissionAllInputEntry[],
  portSpec: NormalizedPortSpec,
): Set<string> {
  const codePaths = new Set<string>();
  portSpec.codePaths.forEach((path) => codePaths.add(path));
  entries.forEach((entry) => {
    const leaf = entry.path.split(".").pop()?.toLowerCase() ?? "";
    if (leaf === "code") {
      codePaths.add(entry.path);
    }
  });
  return codePaths;
}

function buildEntryValueMap(entries: SubmissionAllInputEntry[]): Record<string, unknown> {
  const values: Record<string, unknown> = {};
  entries.forEach((entry) => {
    const path = entry.path.trim();
    if (path) {
      values[path] = entry.value;
    }
  });
  return values;
}

function findFirstPathByLeafCandidates(
  entries: SubmissionAllInputEntry[],
  candidates: string[],
): string | null {
  if (entries.length === 0 || candidates.length === 0) {
    return null;
  }
  const candidateSet = new Set(candidates.map((candidate) => candidate.trim().toLowerCase()).filter(Boolean));
  const matched = entries
    .filter((entry) => {
      const leaf = entry.path.split(".").pop()?.trim().toLowerCase() ?? "";
      return candidateSet.has(leaf);
    })
    .sort((left, right) => sortPathsByDepth(left.path, right.path));
  return matched[0]?.path ?? null;
}

const METADATA_OPTION_PATHS: Array<{ path: string; parallelKey?: string; fallback: unknown }> = [
  { path: "metadata.options.max_wallclock_seconds", parallelKey: "max_wallclock_seconds", fallback: 3600 },
  { path: "metadata.options.workdir", fallback: "" },
  { path: "metadata.options.queue_name", parallelKey: "queue_name", fallback: "" },
  { path: "metadata.options.account", parallelKey: "account", fallback: "" },
  { path: "metadata.options.qos", parallelKey: "qos", fallback: "" },
  { path: "metadata.options.withmpi", parallelKey: "withmpi", fallback: true },
  { path: "metadata.options.resources.num_machines", parallelKey: "num_machines", fallback: 1 },
  {
    path: "metadata.options.resources.num_mpiprocs_per_machine",
    parallelKey: "num_mpiprocs_per_machine",
    fallback: 1,
  },
  { path: "metadata.options.resources.tot_num_mpiprocs", parallelKey: "tot_num_mpiprocs", fallback: 1 },
  {
    path: "metadata.options.resources.num_cores_per_machine",
    parallelKey: "num_cores_per_machine",
    fallback: 1,
  },
  {
    path: "metadata.options.resources.num_cores_per_mpiproc",
    parallelKey: "num_cores_per_mpiproc",
    fallback: 1,
  },
];

function buildMetadataFallbackEntries(
  entries: SubmissionAllInputEntry[],
  submissionDraft: SubmissionDraftPayload | null,
  portSpec: NormalizedPortSpec | null,
): SubmissionAllInputEntry[] {
  if (!submissionDraft) {
    return entries;
  }

  const hasMetadata = entries.some((entry) => entry.path.toLowerCase().includes("metadata."));
  const namespaces = new Set((portSpec?.namespaces ?? []).map((entry) => entry.trim().toLowerCase()));
  const shouldSeedMetadata =
    hasMetadata ||
    namespaces.has("metadata") ||
    namespaces.has("metadata.options") ||
    namespaces.has("metadata.options.resources");
  if (!shouldSeedMetadata) {
    return entries;
  }

  // Find where to attach the metadata options.
  // We prefer the prefix associated with the primary "code" port if known, 
  // or default to root "" if it's a direct CalcJob.
  let targetPrefix = "";
  if (portSpec && portSpec.codePaths && portSpec.codePaths.size > 0) {
    const codePath = Array.from(portSpec.codePaths).sort(sortPathsByDepth)[0] ?? "";
    if (codePath) {
      const parts = codePath.split(".");
      parts.pop(); // remove "code"
      targetPrefix = parts.join(".");
    }
  } else {
    // Heuristic: if we see "base.pw.code" or "pw.code"
    const codeEntry = entries.find((e) => e.path.toLowerCase().endsWith(".code"));
    if (codeEntry) {
      const parts = codeEntry.path.split(".");
      parts.pop();
      targetPrefix = parts.join(".");
    }
  }

  const existing = new Set(entries.map((entry) => entry.path.toLowerCase()));
  const parallelSettings = asRecord(submissionDraft.meta.parallel_settings) ?? {};
  const additions: SubmissionAllInputEntry[] = [];

  METADATA_OPTION_PATHS.forEach((candidate) => {
    const fullPath = targetPrefix ? `${targetPrefix}.${candidate.path}` : candidate.path;
    const normalized = fullPath.toLowerCase();
    if (existing.has(normalized)) {
      return;
    }
    let value: unknown = candidate.fallback;
    if (candidate.parallelKey) {
      const fromParallel = parallelSettings[candidate.parallelKey];
      if (!isMissingValue(fromParallel)) {
        value = fromParallel;
      }
    }
    additions.push({
      path: fullPath,
      value,
      isRecommended: false,
    });
  });

  if (additions.length === 0) {
    return entries;
  }
  return [...entries, ...additions].sort((left, right) => left.path.localeCompare(right.path));
}

function buildFallbackCodeOptions(
  codePaths: Set<string>,
  entryValueByPath: Record<string, unknown>,
  primaryCodeValue: unknown,
): NormalizedCodeOption[] {
  const options: NormalizedCodeOption[] = [];
  const seen = new Set<string>();
  const append = (rawValue: unknown) => {
    const text = stringifyCompact(rawValue);
    if (!text || seen.has(text)) {
      return;
    }
    seen.add(text);
    const [codeLabel, computerLabelRaw] = text.split("@", 2);
    options.push({
      value: text,
      label: text,
      codeLabel: codeLabel?.trim() || text,
      computerLabel: computerLabelRaw?.trim() || null,
      plugin: null,
      pk: null,
    });
  };

  codePaths.forEach((path) => append(entryValueByPath[path]));
  append(primaryCodeValue);
  return options.sort((left, right) => left.label.localeCompare(right.label));
}

function ensureSpecCodeEntries(
  entries: SubmissionAllInputEntry[],
  specCodePaths: Set<string>,
  fallbackCodeValue: unknown,
): SubmissionAllInputEntry[] {
  if (specCodePaths.size === 0) {
    return entries;
  }

  const existingNormalized = new Set(entries.map((entry) => entry.path.trim().toLowerCase()));
  const firstExistingCodeValue =
    entries.find((entry) => entry.path.split(".").pop()?.toLowerCase() === "code" && !isMissingValue(entry.value))
      ?.value ?? null;
  const seededCodeValue = isMissingValue(firstExistingCodeValue)
    ? isMissingValue(fallbackCodeValue)
      ? ""
      : fallbackCodeValue
    : firstExistingCodeValue;

  const additions: SubmissionAllInputEntry[] = [];
  [...specCodePaths]
    .sort(sortPathsByDepth)
    .forEach((path) => {
      const normalizedPath = path.trim().toLowerCase();
      if (!normalizedPath || existingNormalized.has(normalizedPath)) {
        return;
      }
      existingNormalized.add(normalizedPath);
      additions.push({
        path,
        value: seededCodeValue,
        isRecommended: false,
      });
    });

  if (additions.length === 0) {
    return entries;
  }
  return [...entries, ...additions].sort((left, right) => left.path.localeCompare(right.path));
}

function buildDraftFieldEditorState(
  entries: SubmissionAllInputEntry[],
): Record<string, DraftFieldEditorValue> {
  const editors: Record<string, DraftFieldEditorValue> = {};
  entries.forEach((entry) => {
    const path = entry.path.trim();
    if (!path || editors[path]) {
      return;
    }
    const valueIsMissing = isMissingValue(entry.value);
    const kind = valueIsMissing ? "string" : inferFieldKind(entry.value);
    let nextValue: boolean | string;
    if (valueIsMissing) {
      nextValue = "";
    } else if (kind === "boolean") {
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
    if (!isFieldModified(editor)) {
      return;
    }

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

function setValueByPath(
  target: Record<string, unknown>,
  path: string,
  value: unknown,
  options?: { createMissing?: boolean },
): boolean {
  const segments = path.split(".").map((segment) => segment.trim()).filter(Boolean);
  if (segments.length === 0) {
    return false;
  }
  const createMissing = Boolean(options?.createMissing);
  let cursor: Record<string, unknown> = target;
  for (let index = 0; index < segments.length - 1; index += 1) {
    const segment = segments[index];
    let next = cursor[segment];
    if ((next === undefined || next === null) && createMissing) {
      next = {};
      cursor[segment] = next;
    }
    const nextRecord = asRecord(next);
    if (!nextRecord) {
      return false;
    }
    cursor = nextRecord;
  }
  const leaf = segments[segments.length - 1];
  if (!createMissing && !Object.prototype.hasOwnProperty.call(cursor, leaf)) {
    return false;
  }
  cursor[leaf] = value;
  return true;
}

function setValueByCandidatePaths(target: Record<string, unknown>, path: string, value: unknown): boolean {
  const normalizedPath = path.trim();
  if (!normalizedPath) {
    return false;
  }

  const isProtocolBuilder = Boolean(target.protocol && (target.intent_data || target.overrides));

  const candidates = [
    normalizedPath,
    `inputs.${normalizedPath} `,
    `builder.${normalizedPath} `,
    `draft.${normalizedPath} `,
  ];
  if (isProtocolBuilder) {
    candidates.unshift(`overrides.${normalizedPath} `);
  }

  for (const candidatePath of candidates) {
    if (setValueByPath(target, candidatePath, value, { createMissing: false })) {
      return true;
    }
  }

  if (isProtocolBuilder) {
    if (normalizedPath.includes(".")) {
      if (setValueByPath(target, `overrides.${normalizedPath} `, value, { createMissing: true })) {
        return true;
      }
    } else {
      if (setValueByPath(target, normalizedPath, value, { createMissing: true })) {
        return true;
      }
    }
  }

  const inputsRecord = asRecord(target.inputs);
  if (inputsRecord && setValueByPath(target, `inputs.${normalizedPath} `, value, { createMissing: true })) {
    return true;
  }

  const builderRecord = asRecord(target.builder);
  if (builderRecord && setValueByPath(target, `builder.${normalizedPath} `, value, { createMissing: true })) {
    return true;
  }

  const draftRecord = asRecord(target.draft);
  if (draftRecord && setValueByPath(target, `draft.${normalizedPath} `, value, { createMissing: true })) {
    return true;
  }

  if (setValueByPath(target, normalizedPath, value, { createMissing: true })) {
    return true;
  }
  return false;
}

function mergeEditorValuesIntoDraft(
  draft: Record<string, unknown>,
  valuesByPath: Record<string, unknown>,
): Record<string, unknown> {
  if (Object.keys(valuesByPath).length === 0) {
    return draft;
  }

  const next = cloneDraftRecord(draft);

  Object.entries(valuesByPath).forEach(([path, value]) => {
    const normalizedPath = path.trim();
    if (!normalizedPath) {
      return;
    }
    setValueByCandidatePaths(next, normalizedPath, value);
  });

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
    return `~${minutes} m`;
  }
  const hours = Math.floor(minutes / 60);
  const remainderMinutes = minutes % 60;
  if (remainderMinutes === 0) {
    return `~${hours} h`;
  }
  return `~${hours}h ${remainderMinutes} m`;
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
      return `Space group ${number} `;
    }
  }
  if (typeof candidate === "string" && candidate.trim()) {
    return candidate.trim();
  }
  const numeric = toPositiveInteger(candidate);
  if (numeric !== null) {
    return `Space group ${numeric} `;
  }
  return null;
}

function parseMeshTriplet(value: unknown): [string, string, string] {
  if (Array.isArray(value) && value.length >= 3) {
    return [String(value[0] ?? ""), String(value[1] ?? ""), String(value[2] ?? "")];
  }
  const text = String(value ?? "").trim();
  if (!text) {
    return ["", "", ""];
  }
  if (text.startsWith("[") && text.endsWith("]")) {
    try {
      const parsed = JSON.parse(text);
      if (Array.isArray(parsed) && parsed.length >= 3) {
        return [String(parsed[0] ?? ""), String(parsed[1] ?? ""), String(parsed[2] ?? "")];
      }
    } catch {
      // Fall through to token parsing.
    }
  }
  const tokens = text.split(/[\sx,]+/i).map((token) => token.trim()).filter(Boolean);
  return [tokens[0] ?? "", tokens[1] ?? "", tokens[2] ?? ""];
}

function serializeMeshTriplet(values: [string, string, string]): string {
  const parsed = values.map((value) => {
    const numeric = Number.parseInt(value.trim() || "0", 10);
    return Number.isFinite(numeric) && numeric > 0 ? numeric : 1;
  });
  return JSON.stringify(parsed);
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
        (pk ? `Structure #${pk} ` : `Task ${index + 1} `);
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
        id: `${index} -${pk ?? "none"} `,
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
    ) || (structurePk ? `Structure #${structurePk} ` : `Task ${index + 1} `);
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
      id: `${index} -${structurePk ?? "none"} `,
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
  mode = "modal",
  expanded = true,
  onToggleExpanded,
  onClose,
  onConfirm,
  onCancel,
  onOpenDetail,
}: SubmissionModalProps) {
  const [selectedBatchIds, setSelectedBatchIds] = useState<string[]>([]);
  const [draftState, setDraftState] = useState<Record<string, DraftFieldEditorValue>>({});
  const [draftStateErrors, setDraftStateErrors] = useState<Record<string, string>>({});
  const [expandedJsonFields, setExpandedJsonFields] = useState<Record<string, boolean>>({});
  const [globalOverridePath, setGlobalOverridePath] = useState("");
  const [globalOverrideValue, setGlobalOverrideValue] = useState("");
  const [codeSearchByPath, setCodeSearchByPath] = useState<Record<string, string>>({});
  const [selectedNamespace, setSelectedNamespace] = useState("");
  const [showValidationDetails, setShowValidationDetails] = useState(false);

  useEffect(() => {
    if (!open || mode === "inline") {
      return;
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && state.status !== "submitting") {
        onClose();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [mode, open, onClose, state.status]);

  const pkEntries = useMemo(
    () => normalizePkMapEntries(submissionDraft?.meta.pk_map),
    [submissionDraft],
  );
  const basePrimaryFields = useMemo<SubmissionPrimaryFields>(
    () => (submissionDraft ? extractPrimaryFields(submissionDraft) : { code: null, structure: null, pseudos: null }),
    [submissionDraft],
  );
  const portSpec = useMemo(
    () => normalizePortSpec(submissionDraft?.meta.port_spec),
    [submissionDraft?.meta.port_spec],
  );
  const availableCodeOptions = useMemo(
    () => normalizeCodeOptions(submissionDraft?.meta.available_codes),
    [submissionDraft?.meta.available_codes],
  );
  const allInputEntries = useMemo(
    () => (submissionDraft ? allInputEntriesFromDraft(submissionDraft) : []),
    [submissionDraft],
  );
  const allInputEntriesWithMetadata = useMemo(
    () => buildMetadataFallbackEntries(allInputEntries, submissionDraft ?? null, portSpec),
    [allInputEntries, submissionDraft, portSpec],
  );
  const fallbackCodeValue = useMemo(() => {
    const fromInputs = stringifyCompact(
      findFirstMatchingValue(
        submissionDraft?.inputs ?? {},
        (key) => looksLikeCodeKey(key),
      ),
    );
    if (fromInputs) {
      return fromInputs;
    }
    const primaryCodeRaw = asRecord(submissionDraft?.primary_inputs)?.code;
    const primaryCode = normalizePrimaryField("Code", primaryCodeRaw);
    const fromPrimary = stringifyCompact(primaryCode?.value ?? "");
    if (fromPrimary) {
      return fromPrimary;
    }
    return availableCodeOptions[0]?.value ?? "";
  }, [availableCodeOptions, submissionDraft?.inputs, submissionDraft?.primary_inputs]);
  const inspectorInputEntries = useMemo(
    () =>
      ensureSpecCodeEntries(
        buildInspectorInputEntries(allInputEntriesWithMetadata),
        portSpec.codePaths,
        fallbackCodeValue,
      ),
    [allInputEntriesWithMetadata, fallbackCodeValue, portSpec.codePaths],
  );
  const entryValueByPath = useMemo(
    () => buildEntryValueMap(inspectorInputEntries),
    [inspectorInputEntries],
  );
  const codeFieldPaths = useMemo(
    () => collectCodePaths(inspectorInputEntries, portSpec),
    [inspectorInputEntries, portSpec],
  );
  const codeFieldPathsArray = useMemo(
    () => Array.from(codeFieldPaths).sort(),
    [codeFieldPaths]
  );
  const existingCodePaths = useMemo(() => {
    const existing = new Set<string>();
    inspectorInputEntries.forEach((entry) => {
      const leaf = entry.path.split(".").pop()?.toLowerCase() ?? "";
      if (leaf === "code" || codeFieldPaths.has(entry.path)) {
        existing.add(entry.path);
      }
    });
    return existing;
  }, [codeFieldPathsArray, inspectorInputEntries]); // eslint-disable-line react-hooks/exhaustive-deps
  const primaryCodePath = useMemo(() => {
    const orderedSpecPaths = [...portSpec.codePaths].sort(sortPathsByDepth);
    const requiredSpecPaths = orderedSpecPaths.filter((path) => portSpec.requiredCodePaths.has(path));
    const preferredSpecPaths = requiredSpecPaths.length > 0 ? requiredSpecPaths : orderedSpecPaths;
    for (const specPath of preferredSpecPaths) {
      if (existingCodePaths.has(specPath)) {
        return specPath;
      }
    }
    if (preferredSpecPaths.length > 0) {
      return preferredSpecPaths[0] ?? null;
    }
    const fallbackCandidates = [...existingCodePaths];
    if (fallbackCandidates.length === 0) {
      fallbackCandidates.push(...codeFieldPaths);
    }
    if (fallbackCandidates.length === 0) {
      return null;
    }
    fallbackCandidates.sort(sortPathsByDepth);
    return fallbackCandidates[0] ?? null;
  }, [codeFieldPathsArray, existingCodePaths, portSpec.codePaths, portSpec.requiredCodePaths]); // eslint-disable-line react-hooks/exhaustive-deps
  const primaryCodeValue = useMemo(() => {
    if (!primaryCodePath) {
      return "";
    }
    const editorValue = draftState[primaryCodePath];
    if (editorValue) {
      return String(editorValue.value ?? "").trim();
    }
    return stringifyCompact(entryValueByPath[primaryCodePath] ?? "");
  }, [draftState, entryValueByPath, primaryCodePath]);
  const primaryFields = useMemo<SubmissionPrimaryFields>(() => {
    if (!submissionDraft) {
      return { code: null, structure: null, pseudos: null };
    }
    const resolvedCode = normalizePrimaryField("Code", primaryCodeValue);
    return {
      ...basePrimaryFields,
      code: resolvedCode ?? basePrimaryFields.code,
    };
  }, [basePrimaryFields, primaryCodeValue, submissionDraft]);
  const effectiveCodeOptions = useMemo(() => {
    if (availableCodeOptions.length > 0) {
      return availableCodeOptions;
    }
    return buildFallbackCodeOptions(codeFieldPaths, entryValueByPath, primaryCodeValue);
  }, [availableCodeOptions, codeFieldPathsArray, entryValueByPath, primaryCodeValue]); // eslint-disable-line react-hooks/exhaustive-deps

  const inheritedCodePaths = useMemo(() => {
    const inherited = new Set<string>();
    if (!primaryCodePath) {
      return inherited;
    }
    codeFieldPaths.forEach((path) => {
      if (path === primaryCodePath) {
        return;
      }
      const editorValue = draftState[path];
      const currentValue = editorValue
        ? String(editorValue.value ?? "").trim()
        : stringifyCompact(entryValueByPath[path] ?? "");
      const pathHasField = Boolean(draftState[path]);
      const primaryHasField = Boolean(primaryCodePath && draftState[primaryCodePath]);
      if (pathHasField && primaryHasField && !currentValue) {
        inherited.add(path);
        return;
      }
      if (pathHasField && primaryHasField && primaryCodeValue && currentValue === primaryCodeValue) {
        inherited.add(path);
      }
    });
    return inherited;
  }, [codeFieldPaths, draftState, entryValueByPath, primaryCodePath, primaryCodeValue]);
  const groupedInputSections = useMemo(
    () => (submissionDraft ? buildInputGroupsForModal(submissionDraft, inspectorInputEntries) : []),
    [inspectorInputEntries, submissionDraft],
  );
  const structureSummaryPath = useMemo(
    () => findFirstPathByLeafCandidates(inspectorInputEntries, ["structure", "structure_pk", "structure_id"]),
    [inspectorInputEntries],
  );
  const pseudosSummaryPath = useMemo(
    () =>
      findFirstPathByLeafCandidates(inspectorInputEntries, [
        "pseudos",
        "pseudo",
        "pseudopotentials",
        "pseudo_family",
        "pseudo_family_label",
      ]),
    [inspectorInputEntries],
  );
  const kpointsSummaryPath = useMemo(
    () =>
      findFirstPathByLeafCandidates(inspectorInputEntries, [
        "kpoints",
        "k_points",
        "kpoint_mesh",
        "kpoints_mesh",
        "mesh",
        "kpoints_distance",
        "kpoint_distance",
      ]),
    [inspectorInputEntries],
  );
  const protocolSummaryPath = useMemo(
    () => findFirstPathByLeafCandidates(inspectorInputEntries, ["protocol", "relax_type"]),
    [inspectorInputEntries],
  );
  const namespaceTree = useMemo(
    () => buildNamespaceTreeIndex(inspectorInputEntries, portSpec.namespaces),
    [inspectorInputEntries, portSpec.namespaces],
  );
  const namespaceSidebarItems = useMemo(
    () => flattenNamespaceTree(namespaceTree.childrenByNamespace),
    [namespaceTree.childrenByNamespace],
  );
  const selectedNamespaceChildren = useMemo(
    () => namespaceTree.childrenByNamespace[selectedNamespace] ?? [],
    [namespaceTree.childrenByNamespace, selectedNamespace],
  );
  const selectedNamespaceLeafEntries = useMemo(
    () => namespaceTree.leavesByNamespace[selectedNamespace] ?? [],
    [namespaceTree.leavesByNamespace, selectedNamespace],
  );
  const namespaceBreadcrumb = useMemo(() => {
    if (!selectedNamespace) {
      return [] as Array<{ label: string; path: string }>;
    }
    const segments = selectedNamespace.split(".").filter(Boolean);
    return segments.map((segment, index) => ({
      label: formatSettingKey(segment),
      path: segments.slice(0, index + 1).join("."),
    }));
  }, [selectedNamespace]);
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
  const globalOverrideOptions = useMemo(
    () => allDraftFields.filter((field) => field.kind !== "json"),
    [allDraftFields],
  );
  const validationSummary = useMemo(
    () => normalizeValidationSummary(submissionDraft?.meta.validation_summary, asRecord(submissionDraft?.meta.validation)),
    [submissionDraft],
  );
  const validationErrors = validationSummary?.errors ?? [];
  const validationWarnings = validationSummary?.warnings ?? [];
  const hasValidationIssues = validationErrors.length > 0 || validationWarnings.length > 0;
  const hasValidationBlockingError =
    validationErrors.length > 0 ||
    (validationSummary?.blocking_error_count ?? 0) > 0 ||
    validationSummary?.is_valid === false;
  const metaDraftAny = submissionDraft?.meta.draft as any;
  const isProtocolBuilder = Boolean(metaDraftAny?.protocol && metaDraftAny?.intent_data);
  const protocolHint = useMemo(() => {
    if (!isProtocolBuilder || !metaDraftAny) return null;
    const protocol = metaDraftAny.protocol;
    const intentData = asRecord(metaDraftAny.intent_data) || {};
    const args = Object.entries(intentData)
      .map(([key, value]) => {
        let displayValue = stringifyCompact(value);
        if (typeof value === "object" && value !== null && "pk" in value) {
          displayValue = `Node < ${value.pk}> `;
        } else if (typeof value === "object" && value !== null && "uuid" in value) {
          displayValue = `Node < ${String(value.uuid).split("-")[0]}> `;
        } else if (typeof displayValue === "string" && displayValue.length > 20) {
          displayValue = `"${displayValue.slice(0, 17)}..."`;
        }
        return `${key}=${displayValue} `;
      })
      .join(", ");
    return `get_builder_from_protocol(${args}${args ? ", " : ""}protocol = "${protocol}")`;
  }, [isProtocolBuilder, submissionDraft]);

  const discoveryMetadata = useMemo(() => {
    if (!submissionDraft) return [];
    const raw = asRecord(submissionDraft.inputs) ?? {};
    return Object.entries(raw)
      .filter(([key]) => INTERNAL_METADATA_KEYS.has(key))
      .map(([key, value]) => ({ key: key.trim(), value }));
  }, [submissionDraft]);

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

  const prevTurnIdRef = useRef<number | null>(null);

  useEffect(() => {
    if (!open || !submissionDraft) {
      setDraftState({});
      setDraftStateErrors({});
      setExpandedJsonFields({});
      setGlobalOverridePath("");
      setGlobalOverrideValue("");
      setCodeSearchByPath({});
      setSelectedNamespace("");
      setShowValidationDetails(false);
      prevTurnIdRef.current = turnId;
      return;
    }
    const nextDraftState = buildDraftFieldEditorState(inspectorInputEntries);
    const nextCodeSearch: Record<string, string> = {};
    Object.keys(nextDraftState).forEach((path) => {
      if (codeFieldPaths.has(path)) {
        nextCodeSearch[path] = "";
      }
    });

    setDraftState((current) => {
      if (prevTurnIdRef.current !== turnId) {
        return nextDraftState;
      }
      const merged = { ...nextDraftState };
      Object.keys(current).forEach((key) => {
        if (merged[key] && current[key].value !== merged[key].initialValue) {
          merged[key].value = current[key].value;
        }
      });
      return merged;
    });

    if (prevTurnIdRef.current !== turnId) {
      setDraftStateErrors({});
      setExpandedJsonFields({});
      setCodeSearchByPath(nextCodeSearch);
      const preferredOverride =
        Object.values(nextDraftState).find((field) => field.isRecommended) ?? Object.values(nextDraftState)[0];
      if (preferredOverride) {
        setGlobalOverridePath(preferredOverride.path);
        setGlobalOverrideValue(String(preferredOverride.value));
      } else {
        setGlobalOverridePath("");
        setGlobalOverrideValue("");
      }
      setShowValidationDetails(false);
    }

    prevTurnIdRef.current = turnId;
  }, [codeFieldPathsArray, inspectorInputEntries, open, submissionDraft, turnId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!open) {
      return;
    }
    const available = new Set(namespaceTree.namespaces);
    if (available.has(selectedNamespace)) {
      return;
    }
    setSelectedNamespace(available.has("") ? "" : namespaceTree.namespaces[0] ?? "");
  }, [namespaceTree.namespaces, open, selectedNamespace]);

  const targetComputer =
    typeof submissionDraft?.meta.target_computer === "string" && submissionDraft.meta.target_computer.trim()
      ? submissionDraft.meta.target_computer.trim()
      : null;
  const targetWorkdirPath = useMemo(
    () =>
      findFirstPathByLeafCandidates(inspectorInputEntries, ["workdir", "remote_workdir", "working_directory"]) ??
      null,
    [inspectorInputEntries],
  );
  const targetWorkdirValue = targetWorkdirPath
    ? draftState[targetWorkdirPath]?.value ?? entryValueByPath[targetWorkdirPath]
    : null;
  const targetWorkdirUiType = targetWorkdirPath
    ? inferUiTypeFromPathAndValue(targetWorkdirPath, targetWorkdirValue)
    : "text";
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
      return `Total ${formatRuntimeEstimate(totalSeconds)} `;
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
    const kpoints =
      (kpointsSummaryPath ? draftState[kpointsSummaryPath]?.value ?? entryValueByPath[kpointsSummaryPath] : null) ??
      findFirstNamedValue(submissionDraft?.meta.validation, new Set(["kpoints_distance", "kpoint_distance", "kpoints_mesh", "kpoints"]));
    const protocol =
      (protocolSummaryPath ? draftState[protocolSummaryPath]?.value ?? entryValueByPath[protocolSummaryPath] : null) ??
      findFirstNamedValue(submissionDraft?.meta.validation, new Set(["protocol", "relax_type"]));
    return [
      { label: "K-points", value: kpoints ?? "Default", path: kpointsSummaryPath },
      { label: "Protocol", value: protocol ?? "Default", path: protocolSummaryPath },
    ];
  }, [draftState, entryValueByPath, kpointsSummaryPath, protocolSummaryPath, submissionDraft?.meta.validation]);
  const isInlineMode = mode === "inline";
  const isExpanded = isInlineMode ? expanded : true;
  const canClose = state.status !== "submitting";

  const clearDraftFieldError = (path: string) => {
    setDraftStateErrors((current) => {
      if (!current[path]) {
        return current;
      }
      const next = { ...current };
      delete next[path];
      return next;
    });
  };

  const updateDraftFieldValue = (path: string, nextValue: boolean | string) => {
    setDraftState((current) => {
      const field = current[path];
      if (!field) {
        return current;
      }
      return {
        ...current,
        [path]: {
          ...field,
          value: nextValue,
        },
      };
    });
    clearDraftFieldError(path);
  };

  const handleLaunch = () => {
    if (!submissionDraft) {
      return;
    }
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
  };

  if ((!open && !isInlineMode) || !submissionDraft || turnId === null) {
    return null;
  }

  const renderPrimaryCell = (
    key: string,
    title: string,
    field: SubmissionPrimaryInputField | null,
    missingLabel: string,
    pathHint?: string | null,
  ) => {
    const fieldPk = toPositiveInteger(field?.pk);
    return (
      <div
        key={`${turnId} -primary - ${key} `}
        className="rounded-xl border border-slate-200/85 bg-white/85 px-3 py-3 dark:border-slate-800 dark:bg-slate-950/50"
      >
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">{title}</p>
        {pathHint ? (
          <p className="mt-1 truncate text-[10px] text-slate-500 dark:text-slate-400" title={`inputs.${pathHint} `}>
            inputs.{pathHint}
          </p>
        ) : null}
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
              renderValueNode(field.value, `${turnId} -primary - ${key} `, onOpenDetail)
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

  const renderEditableFieldControl = (
    path: string,
    uiType: string,
    compact = false,
    options?: {
      isCodeField?: boolean;
      isInheritedCode?: boolean;
    },
  ): ReactNode => {
    const field = draftState[path];
    const isCodeField = Boolean(options?.isCodeField);
    const isInheritedCode = Boolean(options?.isInheritedCode);
    if (!field) {
      return (
        <span className="inline-flex rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500 dark:bg-slate-800 dark:text-slate-300">
          Default
        </span>
      );
    }
    const error = draftStateErrors[path];

    if (isCodeField) {
      const currentValue = String(field.value ?? "");
      const searchValue = codeSearchByPath[path] ?? "";
      const normalizedFilter = searchValue.trim().toLowerCase();
      const filteredOptions = effectiveCodeOptions
        .filter((option) =>
          !normalizedFilter ||
          option.label.toLowerCase().includes(normalizedFilter) ||
          option.value.toLowerCase().includes(normalizedFilter),
        )
        .slice(0, 80);
      const hasSelectableOptions = effectiveCodeOptions.length > 0;
      const hasCurrentOption = effectiveCodeOptions.some((option) => option.value === currentValue);
      const codeSelectOptions = [
        ...(!hasCurrentOption && currentValue
          ? [{ value: currentValue, label: `Current: ${currentValue}` }]
          : []),
        ...filteredOptions.map((option) => ({
          value: option.value,
          label: option.plugin ? `${option.label} (${option.plugin})` : option.label,
          description: option.plugin ? option.value : null,
          keywords: [option.plugin ?? "", option.value],
        })),
      ];

      if (hasSelectableOptions) {
        return (
          <div className="min-w-0 space-y-1">
            {isInheritedCode ? (
              <p className="text-[10px] text-slate-500 dark:text-slate-400">
                Inherited from inputs.{primaryCodePath ?? "code"} (edit to override)
              </p>
            ) : null}
            <input
              type="text"
              value={searchValue}
              onChange={(event) =>
                setCodeSearchByPath((current) => ({
                  ...current,
                  [path]: event.currentTarget.value,
                }))
              }
              className={cn(
                "w-full rounded-md border px-2 py-1 text-[11px] text-slate-700 outline-none transition-colors dark:bg-slate-900 dark:text-slate-200",
                error
                  ? "border-rose-300 focus:border-rose-500 dark:border-rose-700"
                  : "border-slate-300 focus:border-blue-500 dark:border-slate-700",
              )}
              placeholder="Search available codes"
            />
            <CommandPaletteSelect
              value={currentValue}
              options={codeSelectOptions}
              placeholder={
                submissionDraft?.meta.required_code_plugin
                  ? `Select ${submissionDraft.meta.required_code_plugin} code`
                  : "Select code label"
              }
              fallbackLabel={currentValue || undefined}
              emptyLabel="No matching codes"
              searchable={false}
              ariaLabel={`Select code for ${path}`}
              className="w-full"
              triggerClassName={cn(
                "flex w-full items-center justify-between rounded-md px-2 py-1.5 text-xs",
                compact && "min-h-8",
                error
                  ? "text-rose-700 hover:bg-rose-50/80 hover:text-rose-800 dark:text-rose-300 dark:hover:bg-rose-950/30 dark:hover:text-rose-200"
                  : "text-slate-700 dark:text-slate-100",
              )}
              onChange={(nextValue) => updateDraftFieldValue(path, nextValue)}
            />
            {error ? (
              <p className="text-[11px] text-rose-600 dark:text-rose-300">{error}</p>
            ) : null}
          </div>
        );
      }

      return (
        <div className="min-w-0">
          {isInheritedCode ? (
            <p className="mb-1 text-[10px] text-slate-500 dark:text-slate-400">
              Inherited from inputs.{primaryCodePath ?? "code"} (edit to override)
            </p>
          ) : null}
          <input
            type="text"
            value={currentValue}
            onChange={(event) => updateDraftFieldValue(path, event.currentTarget.value)}
            className={cn(
              "w-full rounded-md border px-2 py-1.5 text-xs text-slate-800 outline-none transition-colors dark:bg-slate-900 dark:text-slate-100",
              compact ? "h-8" : "h-9",
              error
                ? "border-rose-300 focus:border-rose-500 dark:border-rose-700"
                : "border-slate-300 focus:border-blue-500 dark:border-slate-700",
            )}
            placeholder={
              submissionDraft?.meta.required_code_plugin
                ? `Select ${submissionDraft.meta.required_code_plugin} code`
                : "Select code label"
            }
          />
          <p className="mt-1 text-[10px] text-slate-500 dark:text-slate-400">
            No code list available from worker; manual value is required.
          </p>
          {error ? (
            <p className="mt-1 text-[11px] text-rose-600 dark:text-rose-300">{error}</p>
          ) : null}
        </div>
      );
    }

    if (uiType === "mesh") {
      const [m1, m2, m3] = parseMeshTriplet(field.value);
      const meshValues: [string, string, string] = [m1, m2, m3];
      return (
        <div>
          <div className="inline-flex items-center gap-1">
            {[0, 1, 2].map((index) => (
              <div key={`${path} -mesh - ${index} `} className="inline-flex items-center gap-1">
                <input
                  type="number"
                  min={1}
                  step={1}
                  value={meshValues[index]}
                  onChange={(event) => {
                    const nextValues: [string, string, string] = [...meshValues] as [string, string, string];
                    nextValues[index] = event.currentTarget.value;
                    updateDraftFieldValue(path, serializeMeshTriplet(nextValues));
                  }}
                  className={cn(
                    "w-14 rounded-md border px-1.5 py-1 text-center text-xs text-slate-800 outline-none transition-colors dark:bg-slate-900 dark:text-slate-100",
                    error
                      ? "border-rose-300 focus:border-rose-500 dark:border-rose-700"
                      : "border-slate-300 focus:border-blue-500 dark:border-slate-700",
                  )}
                />
                {index < 2 ? <span className="text-xs text-slate-500">x</span> : null}
              </div>
            ))}
          </div>
          {error ? (
            <p className="mt-1 text-[11px] text-rose-600 dark:text-rose-300">{error}</p>
          ) : null}
        </div>
      );
    }

    if (field.kind === "boolean" || uiType === "toggle") {
      return (
        <button
          type="button"
          className="inline-flex items-center gap-2 text-xs text-slate-700 dark:text-slate-200"
          onClick={() => updateDraftFieldValue(path, !Boolean(field.value))}
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
      );
    }

    if (field.kind === "json" || uiType === "dict") {
      const rawEntryValue = entryValueByPath[path];
      if (isNodeMetadataEnvelope(rawEntryValue) && coerceNodeEnvelopeValue(rawEntryValue) === rawEntryValue) {
        return (
          <span className="inline-flex rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500 dark:bg-slate-800 dark:text-slate-300">
            {summarizeNodeMetadataEnvelope(rawEntryValue)}
          </span>
        );
      }
      const descendantPaths = Object.keys(draftState)
        .filter((candidatePath) => candidatePath.startsWith(`${path}.`) && candidatePath !== path)
        .filter(
          (candidatePath, _index, allPaths) => !allPaths.some((otherPath) => otherPath !== candidatePath && otherPath.startsWith(`${candidatePath}.`)),
        )
        .sort(sortPathsByDepth);
      if (descendantPaths.length > 0) {
        return (
          <div className="min-w-0 rounded-md border border-slate-200/80 bg-slate-50/70 p-2 dark:border-slate-700 dark:bg-slate-900/40">
            <div className="space-y-2">
              {descendantPaths.map((descendantPath) => {
                const relativePath = descendantPath.slice(path.length + 1) || descendantPath;
                const descendantUiType = inferUiTypeFromPathAndValue(descendantPath, entryValueByPath[descendantPath]);
                return (
                  <div
                    key={`${path} -property - ${descendantPath} `}
                    className="grid grid-cols-[minmax(0,1fr)_minmax(180px,1.3fr)] items-start gap-2"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-[11px] font-medium text-slate-700 dark:text-slate-200">
                        {formatSettingKey(relativePath.split(".").pop() ?? relativePath)}
                      </p>
                      <p className="truncate text-[10px] text-slate-500 dark:text-slate-400" title={relativePath}>
                        {relativePath}
                      </p>
                    </div>
                    <div className="min-w-0">
                      {renderEditableFieldControl(descendantPath, descendantUiType, true, {
                        isCodeField: codeFieldPaths.has(descendantPath) || descendantPath.split(".").pop()?.toLowerCase() === "code",
                        isInheritedCode: inheritedCodePaths.has(descendantPath),
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      }
      return (
        <div className="min-w-0">
          <button
            type="button"
            className="rounded-md border border-slate-300 px-2 py-1 text-[11px] text-slate-600 transition-colors hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
            onClick={() =>
              setExpandedJsonFields((current) => ({
                ...current,
                [path]: !Boolean(current[path]),
              }))
            }
          >
            {expandedJsonFields[path] ? "Hide JSON" : "Edit JSON"}
          </button>
          {expandedJsonFields[path] ? (
            <textarea
              className={cn(
                "minimal-scrollbar mt-1 h-24 w-full resize-y rounded-md border px-2 py-1.5 font-mono text-xs text-slate-800 outline-none transition-colors dark:bg-slate-900 dark:text-slate-100",
                error
                  ? "border-rose-300 focus:border-rose-500 dark:border-rose-700"
                  : "border-slate-300 focus:border-blue-500 dark:border-slate-700",
              )}
              value={String(field.value)}
              onChange={(event) => updateDraftFieldValue(path, event.currentTarget.value)}
            />
          ) : null}
          {error ? (
            <p className="mt-1 text-[11px] text-rose-600 dark:text-rose-300">{error}</p>
          ) : null}
        </div>
      );
    }

    return (
      <div className="min-w-0">
        <input
          type={field.kind === "number" ? "number" : "text"}
          step={field.kind === "number" ? "any" : undefined}
          value={String(field.value)}
          onChange={(event) => updateDraftFieldValue(path, event.currentTarget.value)}
          className={cn(
            "w-full rounded-md border px-2 py-1.5 text-xs text-slate-800 outline-none transition-colors dark:bg-slate-900 dark:text-slate-100",
            compact ? "h-8" : "h-9",
            error
              ? "border-rose-300 focus:border-rose-500 dark:border-rose-700"
              : "border-slate-300 focus:border-blue-500 dark:border-slate-700",
          )}
          title={String(field.value)}
        />
        {error ? (
          <p className="mt-1 text-[11px] text-rose-600 dark:text-rose-300">{error}</p>
        ) : null}
      </div>
    );
  };

  return (
    <div
      className={cn(
        isInlineMode
          ? "mt-3"
          : "fixed inset-0 z-[70] flex items-center justify-center bg-slate-950/35 px-4 py-6 backdrop-blur-[1.5px]",
      )}
    >
      {!isInlineMode ? (
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
      ) : null}
      <section
        className={cn(
          isInlineMode
            ? "w-full rounded-2xl border border-slate-200/90 bg-white/95 p-4 dark:border-slate-800 dark:bg-slate-950/70"
            : "relative z-10 h-[80vh] w-full max-w-6xl overflow-y-auto overscroll-contain rounded-2xl border border-slate-200/90 bg-white/95 p-5 shadow-[0_24px_80px_rgba(15,23,42,0.35)] dark:border-slate-800 dark:bg-slate-950/95",
        )}
        style={MODAL_FONT_STYLE}
      >
        <div
          className={cn(
            isInlineMode
              ? "border-b border-slate-200/85 pb-3 dark:border-slate-800"
              : "sticky top-0 z-20 -mx-5 -mt-5 border-b border-slate-200/85 bg-white/95 px-5 py-4 backdrop-blur dark:border-slate-800 dark:bg-slate-950/95",
          )}
        >
          {validationSummary ? (
            <div
              className={cn(
                "mb-3 rounded-lg border px-3 py-2 text-xs",
                !hasValidationIssues
                  ? "border-emerald-300/90 bg-emerald-50/90 text-emerald-800 dark:border-emerald-700/60 dark:bg-emerald-950/35 dark:text-emerald-200"
                  : hasValidationBlockingError
                    ? "border-rose-300/90 bg-rose-50/90 text-rose-800 dark:border-rose-700/60 dark:bg-rose-950/35 dark:text-rose-200"
                    : "border-amber-300/90 bg-amber-50/90 text-amber-800 dark:border-amber-700/60 dark:bg-amber-950/35 dark:text-amber-200",
              )}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  {hasValidationIssues ? (
                    <AlertTriangle className="h-4 w-4 shrink-0" />
                  ) : (
                    <CheckCircle2 className="h-4 w-4 shrink-0" />
                  )}
                  <span className="font-semibold">
                    {hasValidationIssues ? "Validation Error" : "Builder Validated"}
                  </span>
                  <span className="text-[11px] opacity-90">
                    {validationErrors.length} errors, {validationWarnings.length} warnings
                  </span>
                </div>
                {hasValidationIssues ? (
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 rounded-md border border-current/25 px-2 py-0.5 text-[11px] transition-colors hover:bg-white/45 dark:hover:bg-slate-900/30"
                    onClick={() => setShowValidationDetails((current) => !current)}
                    aria-expanded={showValidationDetails}
                  >
                    <span>{showValidationDetails ? "Hide details" : "Show details"}</span>
                    <ChevronDown
                      className={cn(
                        "h-3.5 w-3.5 transition-transform duration-200",
                        showValidationDetails ? "rotate-180" : "rotate-0",
                      )}
                    />
                  </button>
                ) : null}
              </div>
              {hasValidationIssues && showValidationDetails ? (
                <div className="mt-2 space-y-2 border-t border-current/20 pt-2 text-[11px]">
                  {validationErrors.length > 0 ? (
                    <div>
                      <p className="font-semibold uppercase tracking-[0.08em]">Blocking Ports</p>
                      <ul className="mt-1 space-y-1">
                        {validationErrors.map((message, index) => (
                          <li key={`${turnId} -validation - error - ${index} `} className="rounded-md bg-white/60 px-2 py-1 dark:bg-slate-900/45">
                            {renderPkLinkedText(message, `${turnId} -validation - error - ${index} `, onOpenDetail)}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                  {validationWarnings.length > 0 ? (
                    <div>
                      <p className="font-semibold uppercase tracking-[0.08em]">Warnings</p>
                      <ul className="mt-1 space-y-1">
                        {validationWarnings.map((message, index) => (
                          <li key={`${turnId} -validation - warning - ${index} `} className="rounded-md bg-white/55 px-2 py-1 dark:bg-slate-900/40">
                            {renderPkLinkedText(message, `${turnId} -validation - warning - ${index} `, onOpenDetail)}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
          ) : null}
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
                  Structure: {primaryFields.structure?.pk ? `#${primaryFields.structure.pk} ` : "System selected"}
                </span>
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
            <div className="flex items-start gap-2">
              {state.status === "submitted" ? (
                <span className="inline-flex h-9 items-center rounded-md border border-emerald-200 bg-emerald-50 px-2.5 text-xs font-medium text-emerald-700 dark:border-emerald-900/60 dark:bg-emerald-950/40 dark:text-emerald-300">
                  Submitted
                </span>
              ) : null}
              {isInlineMode && onToggleExpanded ? (
                <button
                  type="button"
                  className="inline-flex h-9 items-center gap-1 rounded-md border border-slate-300 bg-white/80 px-2.5 text-xs text-slate-700 transition-colors hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
                  onClick={onToggleExpanded}
                  aria-expanded={isExpanded}
                  aria-label={isExpanded ? "Collapse submission card" : "Expand submission card"}
                >
                  <span>{isExpanded ? "Collapse" : "Expand"}</span>
                  <ChevronDown
                    className={cn(
                      "h-4 w-4 transition-transform duration-200",
                      isExpanded ? "rotate-180" : "rotate-0",
                    )}
                  />
                </button>
              ) : null}
              {!isInlineMode ? (
                <>
                  {state.status !== "submitted" ? (
                    <Button
                      size="sm"
                      className="bg-blue-600 text-white hover:bg-blue-500 dark:bg-blue-500 dark:hover:bg-blue-400"
                      onClick={handleLaunch}
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
                  ) : null}
                  <Button
                    variant="outline"
                    size="sm"
                    className="border-slate-300 bg-white/80 text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800"
                    onClick={state.status === "submitted" ? onClose : onCancel}
                    disabled={state.status === "submitting"}
                  >
                    {state.status === "submitted" ? "Close" : "Cancel"}
                  </Button>
                  <button
                    type="button"
                    className="rounded-lg p-1.5 text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-700 disabled:cursor-not-allowed disabled:opacity-40 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200"
                    onClick={onClose}
                    disabled={!canClose}
                    aria-label="Close modal"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </>
              ) : null}
            </div>
          </div>
        </div>

        {!isExpanded ? (
          <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
            Expand this submission card to review grouped ports and edit K-mesh before launch.
          </p>
        ) : null}
        {isExpanded ? (
          <>
            {!isProtocolBuilder ? (
              <div className="mt-4 grid gap-2 md:grid-cols-3">
                {keyParameterEntries.map((entry) => (
                  <div
                    key={`${turnId} -key - parameter - ${entry.label} `}
                    className="rounded-xl border border-slate-200/85 bg-slate-50/70 px-3 py-2 dark:border-slate-800 dark:bg-slate-900/35"
                  >
                    <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400">
                      {entry.label}
                    </p>
                    {entry.path ? (
                      <p className="mt-1 truncate text-[10px] text-slate-500 dark:text-slate-400" title={`inputs.${entry.path} `}>
                        inputs.{entry.path}
                      </p>
                    ) : null}
                    <p className="mt-1 break-all text-sm text-slate-800 dark:text-slate-100" title={stringifyCompact(entry.value)}>
                      {renderValueNode(entry.value, `${turnId} -key - parameter - ${entry.label} `, onOpenDetail)}
                    </p>
                  </div>
                ))}
              </div>
            ) : null}

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
                      <CommandPaletteSelect
                        value={globalOverridePath}
                        options={globalOverrideOptions.map((field) => ({
                          value: field.path,
                          label: field.label,
                          keywords: [field.path],
                        }))}
                        ariaLabel="Select field to override for all jobs"
                        searchable={globalOverrideOptions.length > 8}
                        className="min-w-[220px]"
                        triggerClassName="flex w-full items-center justify-between rounded-md px-1.5 py-1 text-xs text-slate-700 dark:text-slate-100"
                        onChange={(nextPath) => {
                          setGlobalOverridePath(nextPath);
                          const field = draftState[nextPath];
                          if (field) {
                            setGlobalOverrideValue(String(field.value));
                          }
                        }}
                      />
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
                              key={`${turnId} -batch - ${job.id} `}
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
                                  aria-label={`Select ${job.formula} `}
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
              <>
                {!isProtocolBuilder ? (
                  <div className="mt-4 grid gap-3 sm:grid-cols-3">
                    {renderPrimaryCell(
                      "code",
                      primaryCodePath ? `Code(${primaryCodePath.split(".").pop()})` : "Code",
                      primaryFields.code,
                      "System Selected",
                      primaryCodePath,
                    )}
                    {renderPrimaryCell("structure", "Structure", primaryFields.structure, "Default", structureSummaryPath)}
                    {renderPrimaryCell(
                      "pseudos",
                      "Pseudopotentials",
                      primaryFields.pseudos,
                      "System Selected",
                      pseudosSummaryPath,
                    )}
                  </div>
                ) : null}

                {!isProtocolBuilder ? (
                  <div className={cn("mt-3 rounded-xl border border-slate-200/85 bg-slate-50/70 py-2.5 px-3 dark:border-slate-800 dark:bg-slate-900/35")}>
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400">Computer</p>
                        <div className="text-sm font-medium text-slate-800 dark:text-slate-100">
                          {targetComputer ? (
                            <span className="inline-flex rounded-full bg-slate-200/50 px-2 py-0.5 text-xs text-slate-700 dark:bg-slate-800/80 dark:text-slate-200">{renderValueNode(targetComputer, `${turnId} -target`, onOpenDetail)}</span>
                          ) : (
                            <span className="inline-flex rounded-full bg-slate-200/80 px-2 py-0.5 text-[11px] font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                              System Selected
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="flex w-full sm:w-auto flex-1 items-center justify-end gap-2 max-w-sm">
                        <p className="shrink-0 text-[11px] font-semibold uppercase tracking-[0.1em] text-slate-500 dark:text-slate-400">Workdir</p>
                        <div className="w-full shrink">
                          {targetWorkdirPath ? (
                            renderEditableFieldControl(targetWorkdirPath, targetWorkdirUiType, true)
                          ) : (
                            <span className="inline-flex h-8 items-center rounded-full bg-slate-200/80 px-2.5 text-[11px] font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                              Not available
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                ) : null}
              </>
            )}

            <div className={cn("rounded-xl border border-slate-200/85 bg-slate-50/75 px-3 py-3 dark:border-slate-800 dark:bg-slate-900/35", isProtocolBuilder ? "mt-4" : "mt-3")}>
              <div className="flex flex-col gap-2">
                {protocolHint ? (
                  <div className="rounded-md border border-sky-200 bg-sky-50 px-2 py-1.5 font-mono text-[10px] text-sky-800 dark:border-sky-900/60 dark:bg-sky-950/40 dark:text-sky-300">
                    <span className="font-semibold">Protocol Call: </span>
                    {protocolHint}
                  </div>
                ) : null}
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.13em] text-slate-500 dark:text-slate-400">
                    Builder Port Hierarchy
                  </p>
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="rounded-full bg-white/80 px-2 py-0.5 text-[11px] text-slate-500 dark:bg-slate-800/80 dark:text-slate-300">
                      {recommendedDraftFields.length} recommended
                    </span>
                    <span className="rounded-full bg-white/80 px-2 py-0.5 text-[11px] text-slate-500 dark:bg-slate-800/80 dark:text-slate-300">
                      {allDraftFields.length} editable ports
                    </span>
                    <span className="rounded-full bg-white/80 px-2 py-0.5 text-[11px] text-slate-500 dark:bg-slate-800/80 dark:text-slate-300">
                      {groupedInputSections.length} spec groups
                    </span>
                  </div>
                </div>
              </div>
              <div className="mt-2 grid gap-2 lg:grid-cols-[240px_minmax(0,1fr)]">
                <aside className="minimal-scrollbar max-h-[420px] overflow-y-auto rounded-lg border border-slate-200/85 bg-white/90 p-2 dark:border-slate-800 dark:bg-slate-950/45">
                  <p className="px-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400">
                    Atomic Inputs
                  </p>
                  {namespaceTree.atomicEntries.length > 0 ? (
                    <div className="mt-1.5 space-y-1">
                      {namespaceTree.atomicEntries.map((entry) => {
                        const leaf = entry.path.split(".").pop() ?? entry.path;
                        return (
                          <div
                            key={`${turnId} -atomic - ${entry.path} `}
                            className="rounded-md border border-slate-200/80 bg-slate-50/80 px-2 py-1.5 text-xs dark:border-slate-700 dark:bg-slate-900/50"
                          >
                            <p className="font-semibold text-slate-700 dark:text-slate-200">{formatSettingKey(leaf)}</p>
                            <p className="truncate text-[10px] text-slate-500 dark:text-slate-400" title={entry.path}>
                              {entry.path}
                            </p>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="mt-1.5 px-1 text-[11px] text-slate-500 dark:text-slate-400">
                      No direct scalar inputs at root.
                    </p>
                  )}

                  <div className="mt-3 border-t border-slate-200/80 pt-2 dark:border-slate-800">
                    <p className="px-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400">
                      Namespaces
                    </p>
                    {namespaceSidebarItems.length > 0 ? (
                      <div className="mt-1 space-y-1">
                        {namespaceSidebarItems.map((namespaceItem) => {
                          const label = namespaceItem.path.split(".").pop() ?? namespaceItem.path;
                          const isSelected = namespaceItem.path === selectedNamespace;
                          return (
                            <button
                              key={`${turnId} -namespace - ${namespaceItem.path} `}
                              type="button"
                              className={cn(
                                "flex w-full items-center gap-1.5 rounded-md border px-2 py-1 text-left text-xs transition-colors",
                                isSelected
                                  ? "border-blue-300/90 bg-blue-50 text-blue-700 dark:border-blue-700/70 dark:bg-blue-950/35 dark:text-blue-200"
                                  : "border-transparent text-slate-700 hover:border-slate-200 hover:bg-slate-50 dark:text-slate-200 dark:hover:border-slate-700 dark:hover:bg-slate-900/60",
                              )}
                              onClick={() => setSelectedNamespace(namespaceItem.path)}
                              style={{ paddingLeft: `${0.5 + namespaceItem.depth * 0.65}rem` }}
                            >
                              <Folder className="h-3.5 w-3.5 shrink-0" />
                              <span className="truncate">{formatSettingKey(label)}</span>
                            </button>
                          );
                        })}
                      </div>
                    ) : (
                      <p className="mt-1.5 px-1 text-[11px] text-slate-500 dark:text-slate-400">
                        No nested namespaces detected.
                      </p>
                    )}
                  </div>
                </aside>

                <div className="rounded-lg border border-slate-200/85 bg-white/90 p-2.5 dark:border-slate-800 dark:bg-slate-950/45">
                  <div className="flex flex-wrap items-center gap-1 text-[11px] text-slate-600 dark:text-slate-300">
                    <button
                      type="button"
                      className={cn(
                        "rounded-md px-1.5 py-0.5 font-semibold",
                        selectedNamespace === ""
                          ? "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-200"
                          : "hover:bg-slate-100 dark:hover:bg-slate-800/80",
                      )}
                      onClick={() => setSelectedNamespace("")}
                    >
                      inputs
                    </button>
                    {namespaceBreadcrumb.map((breadcrumb) => (
                      <span key={`${turnId} -breadcrumb - ${breadcrumb.path} `} className="inline-flex items-center gap-1">
                        <ChevronRight className="h-3.5 w-3.5 text-slate-400" />
                        <button
                          type="button"
                          className={cn(
                            "rounded-md px-1.5 py-0.5",
                            breadcrumb.path === selectedNamespace
                              ? "bg-blue-100 font-semibold text-blue-700 dark:bg-blue-900/40 dark:text-blue-200"
                              : "hover:bg-slate-100 dark:hover:bg-slate-800/80",
                          )}
                          onClick={() => setSelectedNamespace(breadcrumb.path)}
                        >
                          {breadcrumb.label}
                        </button>
                      </span>
                    ))}
                  </div>

                  {selectedNamespaceChildren.length > 0 ? (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {selectedNamespaceChildren.map((childPath) => {
                        const childLabel = childPath.split(".").pop() ?? childPath;
                        return (
                          <button
                            key={`${turnId} -namespace - folder - ${childPath} `}
                            type="button"
                            className="inline-flex items-center gap-1 rounded-full border border-slate-300/80 bg-slate-50 px-2 py-0.5 text-[11px] text-slate-700 transition-colors hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900/55 dark:text-slate-200 dark:hover:bg-slate-800"
                            onClick={() => setSelectedNamespace(childPath)}
                          >
                            <Folder className="h-3.5 w-3.5" />
                            <span>{formatSettingKey(childLabel)}</span>
                          </button>
                        );
                      })}
                    </div>
                  ) : null}

                  {selectedNamespaceLeafEntries.length > 0 ? (
                    <div className="minimal-scrollbar mt-2 max-h-[330px] overflow-auto">
                      <table className="w-full min-w-[500px] text-left text-xs">
                        <thead className="sticky top-0 bg-slate-100/95 text-[10px] uppercase tracking-[0.1em] text-slate-500 dark:bg-slate-900/95 dark:text-slate-400">
                          <tr>
                            <th className="w-[44%] px-2 py-1.5 font-semibold">Parameter</th>
                            <th className="px-2 py-1.5 font-semibold">Value</th>
                          </tr>
                        </thead>
                        <tbody>
                          {selectedNamespaceLeafEntries.map((entry) => {
                            const leafKey = entry.path.split(".").pop() ?? entry.path;
                            const uiType = inferUiTypeFromPathAndValue(entry.path, entry.value);
                            const field = draftState[entry.path];
                            const isModified = field ? isFieldModified(field) : false;
                            const isCodeField = codeFieldPaths.has(entry.path) || leafKey.toLowerCase() === "code";
                            const isInheritedCode = isCodeField && inheritedCodePaths.has(entry.path);
                            return (
                              <tr
                                key={`${turnId} -namespace - entry - ${entry.path} `}
                                className="border-t border-slate-200/70 align-top dark:border-slate-800"
                              >
                                <td className="px-2 py-1.5">
                                  <p className="truncate text-[11px] font-semibold text-slate-700 dark:text-slate-200">
                                    {formatSettingKey(leafKey)}
                                  </p>
                                  <p className="truncate text-[10px] text-slate-500 dark:text-slate-400" title={entry.path}>
                                    {entry.path}
                                  </p>
                                  <div className="mt-1 flex flex-wrap items-center gap-1">
                                    {entry.isRecommended ? (
                                      <span className="rounded-full bg-emerald-100 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300">
                                        AI
                                      </span>
                                    ) : null}
                                    {isModified ? (
                                      <span className="rounded-full bg-blue-100 px-1.5 py-0.5 text-[10px] font-medium text-blue-700 dark:bg-blue-900/40 dark:text-blue-300">
                                        Modified
                                      </span>
                                    ) : null}
                                    {isCodeField ? (
                                      <span className="rounded-full bg-violet-100 px-1.5 py-0.5 text-[10px] font-medium text-violet-700 dark:bg-violet-900/40 dark:text-violet-300">
                                        Code
                                      </span>
                                    ) : null}
                                    {isInheritedCode ? (
                                      <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                                        Inherited
                                      </span>
                                    ) : null}
                                  </div>
                                </td>
                                <td className="px-2 py-1.5">
                                  {renderEditableFieldControl(entry.path, uiType, true, {
                                    isCodeField,
                                    isInheritedCode,
                                  })}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                      No direct parameters in this namespace. Select a sub-namespace folder to continue.
                    </p>
                  )}
                </div>
              </div>
            </div>

            {!isBatchDraft && pkEntries.length > 0 ? (
              <div className="mt-3 rounded-xl border border-slate-200/80 bg-slate-50/80 px-3 py-2 dark:border-slate-800 dark:bg-slate-900/30">
                <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400">Input PKs</p>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {pkEntries.map((entry, index) => (
                    <button
                      key={`${turnId} -pk - ${entry.pk} -${index} `}
                      type="button"
                      className="rounded-full border border-sky-200 bg-sky-50 px-2 py-0.5 font-mono text-[11px] font-semibold text-sky-700 transition-colors hover:bg-sky-100 dark:border-sky-900/60 dark:bg-sky-950/40 dark:text-sky-200 dark:hover:bg-sky-900/50"
                      onClick={() => onOpenDetail(entry.pk)}
                      title={entry.path ?? `PK ${entry.pk} `}
                    >
                      #{entry.pk}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}

            {discoveryMetadata.length > 0 && (
              <div className="mt-4 border-t border-slate-200/60 pt-4 dark:border-slate-800/60">
                <details className="group">
                  <summary className="flex cursor-pointer list-none items-center justify-between text-[11px] font-semibold uppercase tracking-[0.13em] text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200">
                    <span className="flex items-center gap-2">
                      <ChevronRight className="h-3.5 w-3.5 transition-transform group-open:rotate-90" />
                      Internal Discovery Metadata (Debug)
                    </span>
                    <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[10px] font-medium text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                      {discoveryMetadata.length} hidden items
                    </span>
                  </summary>
                  <div className="mt-4 overflow-hidden rounded-xl border border-slate-200/80 bg-slate-50/50 p-4 dark:border-slate-800 dark:bg-slate-900/40">
                    <div className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
                      {discoveryMetadata.map(({ key, value }) => (
                        <div key={`${turnId}-meta-${key}`} className="flex flex-col gap-1.5 overflow-hidden">
                          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                            {formatSettingKey(key)}
                          </span>
                          <div className="minimal-scrollbar max-h-[120px] overflow-y-auto font-mono text-[11px] text-slate-700 dark:text-slate-300">
                            {renderValueNode(value, `${turnId}-meta-val-${key}`, onOpenDetail)}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </details>
              </div>
            )}

            <div className="mt-5 border-t border-slate-200/80 pt-4 dark:border-slate-800">
              {isInlineMode && state.status !== "submitted" ? (
                <div className="mb-3 flex flex-wrap items-center gap-2">
                  <Button
                    size="sm"
                    className="bg-blue-600 text-white hover:bg-blue-500 dark:bg-blue-500 dark:hover:bg-blue-400"
                    onClick={handleLaunch}
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
              ) : null}
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
                              key={`${turnId} -submitted - ${pk} `}
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
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Review grouped inputs above and launch when ready.
                </p>
              )}
              {state.status === "error" && state.errorText ? (
                <p className="mt-2 text-xs text-rose-600 dark:text-rose-300">{state.errorText}</p>
              ) : null}
            </div>
          </>
        ) : null}
      </section>
    </div>
  );
}
