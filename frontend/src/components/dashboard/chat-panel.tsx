import { Bot, ChevronDown, Code2, Copy, Cpu, Paperclip, PlugZap, RotateCcw, SendHorizontal, Square, X } from "lucide-react";
import { type DragEvent, type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  SubmissionModal,
  type SubmissionModalState,
  type SubmissionDraftPayload,
  type SubmissionSubmitDraft,
} from "@/components/dashboard/submission-modal";
import { ThinkingIndicator, type ProcessLogEntry } from "@/components/dashboard/thinking-indicator";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import { cancelPendingSubmission, getNodeHoverMetadata, submitPreviewDraft } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { ChatMessage, FocusNode, NodeHoverMetadataResponse, ResourceAttachment } from "@/types/aiida";

type ChatTurn = {
  turnId: number;
  userText?: string;
  userPayload?: Record<string, unknown> | null;
  thinkingText?: string;
  thinkingPayload?: Record<string, unknown> | null;
  assistantText?: string;
  assistantStatus?: string;
  assistantPayload?: Record<string, unknown> | null;
};

type SubmissionDraftPreview = {
  submissionDraft: SubmissionDraftPayload;
  submitDraft: SubmissionSubmitDraft;
};

type SubmissionDraftTagParseResult = {
  preview: SubmissionDraftPreview | null;
  cleanText: string;
  bufferedFragment: string | null;
};

type SubmittedPreviewSummary = {
  processLabel: string;
  processPks: number[];
};

type NodeHoverMetadataState = {
  status: "loading" | "loaded" | "error";
  data: NodeHoverMetadataResponse | null;
};

const SUBMISSION_DRAFT_TAG = "[SUBMISSION_DRAFT]";
const SUBMISSION_DRAFT_JSON_GLOBAL_REGEX = /(?:\[SUBMISSION_DRAFT\])\s*(\{[\s\S]*?\})/gis;
const CONTEXT_NODE_DRAG_MIME = "application/x-sabr-context-node";
const RESOURCE_ATTACHMENT_DRAG_MIME = "application/x-sabr-resource-attachment";

const FRIENDLY_TOOL_STEP_MAP: Record<string, string> = {
  inspect_process: "Inspecting process details...",
  query_nodes: "Searching AiiDA database...",
  submit_job: "Submitting calculation to cluster...",
  validate_job: "Validating submission...",
};
const STRUCTURE_NODE_TYPE = "StructureData";

type QuickActionKind = "relax" | "band" | "full" | "pseudo" | "generic";

function inferQuickActionKind(label: string, prompt: string): QuickActionKind {
  const text = `${label} ${prompt}`.toLowerCase();
  if (
    text.includes("relax+band") ||
    text.includes("then use the optimized structure") ||
    (text.includes("vc-relax") && text.includes("band structure"))
  ) {
    return "full";
  }
  if (
    text.includes("structure relaxation") ||
    text.includes("vc-relax") ||
    text.includes("几何优化")
  ) {
    return "relax";
  }
  if (text.includes("band structure")) {
    return "band";
  }
  if (text.includes("pseudo") || text.includes("pseudopotential")) {
    return "pseudo";
  }
  return "generic";
}

function quickActionIcon(kind: QuickActionKind): string {
  if (kind === "relax") {
    return "🧪";
  }
  if (kind === "band") {
    return "📈";
  }
  if (kind === "full") {
    return "🔄";
  }
  if (kind === "pseudo") {
    return "📚";
  }
  return "⚙️";
}

function quickActionRequiresStructure(kind: QuickActionKind): boolean {
  return kind === "relax" || kind === "band" || kind === "full";
}

function buildQuickActionIntent(
  label: string,
  prompt: string,
  structurePks: number[],
): string {
  const kind = inferQuickActionKind(label, prompt);
  if (kind !== "relax") {
    return prompt;
  }
  if (structurePks.length === 0) {
    return prompt;
  }
  if (/#\d+|\bpk\s*\d+\b/i.test(prompt)) {
    return prompt;
  }
  const targets = structurePks.map((pk) => `#${pk}`).join(", ");
  return `${prompt.trim()} for structures ${targets}`;
}

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

function normalizeSubmissionPkMap(raw: unknown): Array<{ pk: number; path?: string; label?: string }> {
  if (!Array.isArray(raw)) {
    return [];
  }
  const seen = new Set<number>();
  const entries: Array<{ pk: number; path?: string; label?: string }> = [];
  raw.forEach((entry) => {
    const record = asRecord(entry);
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

function normalizeSubmissionDraftPreview(rawSubmissionDraft: Record<string, unknown> | null): SubmissionDraftPreview | null {
  if (!rawSubmissionDraft) {
    return null;
  }

  const processLabelRaw = rawSubmissionDraft.process_label;
  const processLabel =
    typeof processLabelRaw === "string" && processLabelRaw.trim()
      ? processLabelRaw.trim()
      : "AiiDA Workflow";
  const inputs = asRecord(rawSubmissionDraft.inputs) ?? {};
  const metaRecord = asRecord(rawSubmissionDraft.meta) ?? {};
  const batchCandidates = [
    metaRecord.draft,
    rawSubmissionDraft.jobs,
    rawSubmissionDraft.tasks,
    rawSubmissionDraft.submissions,
    rawSubmissionDraft.drafts,
  ];
  const submitDraftArray = batchCandidates
    .map((candidate) => toRecordArray(candidate))
    .find((candidate) => candidate.length > 0);
  const submitDraftRecord = asRecord(metaRecord.draft);
  const submitDraft: SubmissionSubmitDraft = submitDraftArray ?? submitDraftRecord ?? inputs;
  const rawPrimaryInputs = asRecord(rawSubmissionDraft.primary_inputs);
  const rawRecommendedInputs =
    asRecord(rawSubmissionDraft.recommended_inputs) ??
    asRecord(metaRecord.recommended_inputs);
  const rawAllInputs = asRecord(rawSubmissionDraft.all_inputs) ?? asRecord(metaRecord.all_inputs);
  const rawAdvancedSettings = asRecord(rawSubmissionDraft.advanced_settings);
  const rawInputGroups = Array.isArray(rawSubmissionDraft.input_groups)
    ? rawSubmissionDraft.input_groups
    : Array.isArray(metaRecord.input_groups)
      ? metaRecord.input_groups
      : [];
  const submissionDraft: SubmissionDraftPayload = {
    process_label: processLabel,
    inputs,
    input_groups: rawInputGroups,
    primary_inputs: rawPrimaryInputs ?? {},
    recommended_inputs: rawRecommendedInputs ?? rawAdvancedSettings ?? {},
    all_inputs: rawAllInputs ?? {},
    advanced_settings: rawAdvancedSettings ?? {},
    meta: {
      pk_map: normalizeSubmissionPkMap(metaRecord.pk_map),
      target_computer:
        typeof metaRecord.target_computer === "string" && metaRecord.target_computer.trim()
          ? metaRecord.target_computer.trim()
          : null,
      parallel_settings: asRecord(metaRecord.parallel_settings) ?? {},
      validation_summary: asRecord(metaRecord.validation_summary),
      validation: asRecord(metaRecord.validation),
      draft: submitDraft,
      recommended_inputs: rawRecommendedInputs ?? rawAdvancedSettings ?? {},
      all_inputs: rawAllInputs ?? {},
      input_groups: rawInputGroups,
      structure_metadata: Array.isArray(metaRecord.structure_metadata) ? metaRecord.structure_metadata : [],
      available_codes: Array.isArray(metaRecord.available_codes) ? metaRecord.available_codes : [],
      required_code_plugin:
        typeof metaRecord.required_code_plugin === "string" && metaRecord.required_code_plugin.trim()
          ? metaRecord.required_code_plugin.trim()
          : null,
      port_spec: asRecord(metaRecord.port_spec),
    },
  };

  return { submissionDraft, submitDraft };
}

function isSubmissionDraftLikePayload(value: Record<string, unknown> | null): boolean {
  if (!value) {
    return false;
  }
  if (typeof value.process_label === "string" && value.process_label.trim()) {
    return true;
  }
  if (
    asRecord(value.inputs) ||
    asRecord(value.primary_inputs) ||
    asRecord(value.recommended_inputs) ||
    asRecord(value.all_inputs) ||
    Array.isArray(value.input_groups) ||
    asRecord(value.advanced_settings) ||
    asRecord(value.meta)
  ) {
    return true;
  }
  return false;
}

function findSubmissionDraftCandidate(value: unknown, depth = 0): Record<string, unknown> | null {
  if (depth > 8) {
    return null;
  }
  if (Array.isArray(value)) {
    for (const item of value) {
      const nested = findSubmissionDraftCandidate(item, depth + 1);
      if (nested) {
        return nested;
      }
    }
    return null;
  }
  const record = asRecord(value);
  if (!record) {
    return null;
  }
  const nestedDraft = asRecord(record.submission_draft);
  if (nestedDraft) {
    return nestedDraft;
  }
  if (isSubmissionDraftLikePayload(record)) {
    return record;
  }
  for (const nestedValue of Object.values(record)) {
    const nested = findSubmissionDraftCandidate(nestedValue, depth + 1);
    if (nested) {
      return nested;
    }
  }
  return null;
}

function extractSubmissionDraft(payload: Record<string, unknown> | null | undefined): SubmissionDraftPreview | null {
  const root = asRecord(payload);
  if (!root) {
    return null;
  }
  const dataPayload = asRecord(root.data_payload);
  const recursiveCandidate = findSubmissionDraftCandidate(root);
  const candidates = [root, dataPayload, recursiveCandidate].filter(
    (item): item is Record<string, unknown> => Boolean(item),
  );

  for (const candidate of candidates) {
    const typeRaw = candidate.type;
    const normalizedType =
      typeof typeRaw === "string" && typeRaw.trim() ? typeRaw.trim().toUpperCase() : "";
    if (normalizedType && normalizedType !== "SUBMISSION_DRAFT") {
      continue;
    }

    const fromNested = normalizeSubmissionDraftPreview(asRecord(candidate.submission_draft));
    if (fromNested) {
      return fromNested;
    }

    if (normalizedType !== "SUBMISSION_DRAFT" && !isSubmissionDraftLikePayload(candidate)) {
      continue;
    }
    const fromDirect = normalizeSubmissionDraftPreview(candidate);
    if (fromDirect && isSubmissionDraftLikePayload(asRecord(fromDirect.submissionDraft))) {
      return fromDirect;
    }
  }

  return null;
}

function mergeSubmissionDraftBuffer(previous: string | undefined, fragment: string): string {
  const next = fragment.trimStart();
  if (!previous || !previous.trim()) {
    return next;
  }
  const current = previous.trimStart();
  if (next.startsWith(current)) {
    return next;
  }
  if (current.startsWith(next)) {
    return current;
  }
  return `${current}\n${next}`;
}

function mergeTurnTextBuffer(previous: string | undefined, incoming: string): string {
  const next = incoming ?? "";
  if (!next.trim()) {
    return previous ?? "";
  }
  if (!previous || !previous.trim()) {
    return next;
  }
  const current = previous;
  if (next.startsWith(current) || next.includes(current)) {
    return next;
  }
  if (current.startsWith(next) || current.includes(next)) {
    return current;
  }
  return `${current}\n${next}`;
}

function extractBalancedJsonObject(fragment: string): { jsonText: string | null; remainder: string; incomplete: boolean } {
  const start = fragment.indexOf("{");
  if (start < 0) {
    return { jsonText: null, remainder: fragment, incomplete: true };
  }

  let depth = 0;
  let inString = false;
  let escaped = false;
  for (let index = start; index < fragment.length; index += 1) {
    const char = fragment[index];
    if (inString) {
      if (escaped) {
        escaped = false;
      } else if (char === "\\") {
        escaped = true;
      } else if (char === "\"") {
        inString = false;
      }
      continue;
    }

    if (char === "\"") {
      inString = true;
      continue;
    }
    if (char === "{") {
      depth += 1;
      continue;
    }
    if (char !== "}") {
      continue;
    }

    depth -= 1;
    if (depth === 0) {
      return {
        jsonText: fragment.slice(start, index + 1),
        remainder: fragment.slice(index + 1),
        incomplete: false,
      };
    }
  }

  return { jsonText: fragment.slice(start), remainder: "", incomplete: true };
}

function parseSubmissionDraftTag(
  text: string,
  previousBufferedFragment?: string,
): SubmissionDraftTagParseResult {
  const rawText = text ?? "";
  const tagIndex = rawText.toUpperCase().lastIndexOf(SUBMISSION_DRAFT_TAG);
  if (tagIndex < 0) {
    return {
      preview: null,
      cleanText: rawText,
      bufferedFragment:
        previousBufferedFragment && previousBufferedFragment.trim().length > 0
          ? previousBufferedFragment
          : null,
    };
  }

  const regexMatches = [...rawText.matchAll(SUBMISSION_DRAFT_JSON_GLOBAL_REGEX)];
  for (let index = regexMatches.length - 1; index >= 0; index -= 1) {
    const regexMatch = regexMatches[index];
    if (!regexMatch || typeof regexMatch.index !== "number") {
      continue;
    }
    const regexJsonText = regexMatch[1];
    try {
      const parsed = asRecord(JSON.parse(regexJsonText));
      const rawSubmissionDraft = asRecord(parsed?.submission_draft) ?? parsed;
      const preview = normalizeSubmissionDraftPreview(rawSubmissionDraft);
      const regexBeforeTag = rawText.slice(0, regexMatch.index).trimEnd();
      const trailingText = rawText
        .slice(regexMatch.index + regexMatch[0].length)
        .replace(/^\s*```(?:json)?/i, "")
        .replace(/```\s*$/i, "")
        .trim();
      const cleanText = [regexBeforeTag, trailingText].filter(Boolean).join("\n\n");
      return {
        preview,
        cleanText,
        bufferedFragment: null,
      };
    } catch {
      // Continue scanning older matches if the latest is malformed/incomplete.
    }
  }

  const beforeTag = rawText.slice(0, tagIndex).trimEnd();
  const fragment = rawText.slice(tagIndex + SUBMISSION_DRAFT_TAG.length);
  const mergedFragment = mergeSubmissionDraftBuffer(previousBufferedFragment, fragment);
  const { jsonText, remainder, incomplete } = extractBalancedJsonObject(mergedFragment);
  if (!jsonText || incomplete) {
    return {
      preview: null,
      cleanText: beforeTag,
      bufferedFragment: mergedFragment,
    };
  }

  let preview: SubmissionDraftPreview | null = null;
  try {
    const parsed = asRecord(JSON.parse(jsonText));
    const rawSubmissionDraft = asRecord(parsed?.submission_draft) ?? parsed;
    preview = normalizeSubmissionDraftPreview(rawSubmissionDraft);
  } catch (error) {
    console.error("Failed to parse [SUBMISSION_DRAFT] JSON block.", {
      error,
      jsonText,
      rawText: rawText.slice(Math.max(0, tagIndex), tagIndex + 1200),
    });
    return {
      preview: null,
      cleanText: beforeTag,
      bufferedFragment: mergedFragment,
    };
  }

  const trailingText = remainder.replace(/^\s*```(?:json)?/i, "").replace(/```\s*$/i, "").trim();
  const cleanText = [beforeTag, trailingText].filter(Boolean).join("\n\n");
  return {
    preview,
    cleanText,
    bufferedFragment: null,
  };
}

function stripSubmissionDraftBlocks(text: string): string {
  let clean = text ?? "";
  for (let pass = 0; pass < 4; pass += 1) {
    if (!clean.toUpperCase().includes(SUBMISSION_DRAFT_TAG)) {
      break;
    }
    const parsed = parseSubmissionDraftTag(clean);
    if (parsed.cleanText === clean) {
      clean = clean.replace(/\[SUBMISSION_DRAFT\][\s\S]*$/gi, "").trimEnd();
      break;
    }
    clean = parsed.cleanText;
  }
  return clean;
}

function resolveTurnSubmissionDraft(
  turn: ChatTurn,
  bufferedFragment?: string,
): SubmissionDraftPreview | null {
  return (
    extractSubmissionDraft(turn.assistantPayload) ??
    parseSubmissionDraftTag(turn.assistantText ?? "", bufferedFragment).preview
  );
}

function submissionDraftSignature(preview: SubmissionDraftPreview): string {
  const primaryInputsCount = Object.keys(asRecord(preview.submissionDraft.primary_inputs) ?? {}).length;
  const recommendedInputsCount = Object.keys(asRecord(preview.submissionDraft.recommended_inputs) ?? {}).length;
  const allInputsCount = Object.keys(asRecord(preview.submissionDraft.all_inputs) ?? {}).length;
  const inputGroupsCount = Array.isArray(preview.submissionDraft.input_groups)
    ? preview.submissionDraft.input_groups.length
    : 0;
  const advancedSettingsCount = Object.keys(asRecord(preview.submissionDraft.advanced_settings) ?? {}).length;
  const pkCount = Array.isArray(preview.submissionDraft.meta.pk_map)
    ? preview.submissionDraft.meta.pk_map.length
    : 0;
  return [
    preview.submissionDraft.process_label,
    primaryInputsCount,
    recommendedInputsCount,
    allInputsCount,
    inputGroupsCount,
    advancedSettingsCount,
    pkCount,
  ].join("|");
}

function extractProcessPks(payload: unknown): number[] {
  const preferredScalarKeys = new Set([
    "pk",
    "process_pk",
    "process_id",
    "submitted_pk",
    "workflow_pk",
    "process_node_pk",
  ]);
  const preferredArrayKeys = new Set([
    "submitted_pks",
    "process_pks",
    "workflow_pks",
    "pks",
  ]);

  const seen = new Set<number>();
  const appendPk = (value: unknown) => {
    const candidate = toPositiveInteger(value);
    if (candidate === null || seen.has(candidate)) {
      return;
    }
    seen.add(candidate);
  };

  appendPk(payload);
  const queue: unknown[] = [payload];
  while (queue.length > 0) {
    const current = queue.shift();
    if (Array.isArray(current)) {
      current.forEach((value) => appendPk(value));
      queue.push(...current);
      continue;
    }
    const record = asRecord(current);
    if (!record) {
      continue;
    }
    for (const [key, value] of Object.entries(record)) {
      const normalized = key.toLowerCase();
      if (preferredScalarKeys.has(normalized)) {
        appendPk(value);
      }
      if (preferredArrayKeys.has(normalized) && Array.isArray(value)) {
        value.forEach((entry) => appendPk(entry));
      }
    }
    for (const [key, value] of Object.entries(record)) {
      const normalized = key.toLowerCase();
      if (normalized === "draft" || normalized === "builder") {
        continue;
      }
      queue.push(value);
    }
  }
  return [...seen];
}

function extractContextPks(payload: Record<string, unknown> | null | undefined): number[] {
  const rawValues = asRecord(payload)?.context_pks;
  if (!Array.isArray(rawValues)) {
    return [];
  }
  const seen = new Set<number>();
  const pks: number[] = [];
  rawValues.forEach((value) => {
    const pk = toPositiveInteger(value);
    if (pk === null || seen.has(pk)) {
      return;
    }
    seen.add(pk);
    pks.push(pk);
  });
  return pks;
}

function extractContextNodes(payload: Record<string, unknown> | null | undefined): FocusNode[] {
  const nodes = asRecord(payload)?.context_nodes;
  if (!Array.isArray(nodes)) {
    return [];
  }
  const seen = new Set<number>();
  const normalized: FocusNode[] = [];
  nodes.forEach((entry) => {
    const record = asRecord(entry);
    if (!record) {
      return;
    }
    const pk = toPositiveInteger(record.pk);
    if (pk === null || seen.has(pk)) {
      return;
    }
    seen.add(pk);
    normalized.push({
      pk,
      label: typeof record.label === "string" && record.label.trim() ? record.label.trim() : `#${pk}`,
      formula: typeof record.formula === "string" && record.formula.trim() ? record.formula.trim() : null,
      node_type:
        typeof record.node_type === "string" && record.node_type.trim() ? record.node_type.trim() : "Unknown",
    });
  });
  return normalized;
}

function extractToolCalls(payload: Record<string, unknown> | null | undefined): string[] {
  const record = asRecord(payload);
  if (!record) {
    return [];
  }
  const directRaw = record.tool_calls;
  const nestedStatus = asRecord(record.status);
  const statusRaw = nestedStatus?.tool_calls;
  const values = [
    ...(Array.isArray(directRaw) ? directRaw : []),
    ...(Array.isArray(statusRaw) ? statusRaw : []),
  ];
  return values
    .map((value) => String(value ?? "").trim())
    .filter((value, index, array) => Boolean(value) && array.indexOf(value) === index);
}

function inferToolKey(toolName: string): string {
  const normalized = toolName.trim().toLowerCase();
  if (!normalized) {
    return "unknown_tool";
  }
  if (normalized.includes("inspect_process") || normalized.includes("process.{id}") || normalized.includes("process/")) {
    return "inspect_process";
  }
  if (
    normalized.includes("query_nodes") ||
    normalized.includes("recent-nodes") ||
    normalized.includes("management.groups") ||
    normalized.includes("management.statistics") ||
    normalized.includes("database.summary")
  ) {
    return "query_nodes";
  }
  if (normalized.includes("submit_job") || normalized.includes("submission.submit")) {
    return "submit_job";
  }
  if (normalized.includes("validate_job") || normalized.includes("submission.validate")) {
    return "validate_job";
  }
  return normalized.replace(/\s+/g, "_");
}

function friendlyStepForTool(toolName: string): string {
  const key = inferToolKey(toolName);
  if (FRIENDLY_TOOL_STEP_MAP[key]) {
    return FRIENDLY_TOOL_STEP_MAP[key];
  }
  return `Running ${toolName}...`;
}

function parseToolLine(line: string): { toolName: string; args?: string | null; result?: string | null; raw: string } | null {
  const cleaned = line.trim();
  if (!cleaned) {
    return null;
  }

  const runningMatch = cleaned.match(/^Running:\s*(.+?)(?:\.\.\.)?$/i);
  if (runningMatch) {
    return {
      toolName: runningMatch[1].trim(),
      raw: cleaned,
    };
  }

  const stepMatch = cleaned.match(/^⚙️\s*\[Step\]:\s*(.+)$/i) || cleaned.match(/^Step:\s*(.+)$/i);
  if (stepMatch) {
    return {
      toolName: stepMatch[1].trim(),
      raw: cleaned,
    };
  }

  const callToolMatch = cleaned.match(/call_tool\s*\((.+)\)/i);
  if (callToolMatch) {
    const body = callToolMatch[1];
    const nameMatch = body.match(/(?:name|tool)\s*[:=]\s*["']?([a-zA-Z0-9_.\/-]+)["']?/i);
    const argsMatch = body.match(/(?:args|arguments)\s*[:=]\s*(\{.*\}|\[.*\]|".*?"|'.*?'|[^,]+)(?:,|$)/i);
    const resultMatch = body.match(/(?:result|output)\s*[:=]\s*(.+)$/i);
    return {
      toolName: (nameMatch?.[1] || "call_tool").trim(),
      args: argsMatch?.[1]?.trim() || null,
      result: resultMatch?.[1]?.trim() || null,
      raw: cleaned,
    };
  }

  const toolJsonMatch = cleaned.match(/"(?:tool|name)"\s*:\s*"([^"]+)"/i);
  if (toolJsonMatch) {
    const argsJsonMatch = cleaned.match(/"(?:args|arguments)"\s*:\s*(\{.*\}|\[.*\])/i);
    const resultJsonMatch = cleaned.match(/"(?:result|output)"\s*:\s*(\{.*\}|\[.*\]|"[^"]+"|[^,}]+)/i);
    return {
      toolName: toolJsonMatch[1].trim(),
      args: argsJsonMatch?.[1]?.trim() || null,
      result: resultJsonMatch?.[1]?.trim() || null,
      raw: cleaned,
    };
  }

  return null;
}

function buildProcessLogEntries(thinkingText: string, toolCalls: string[]): ProcessLogEntry[] {
  const entries: ProcessLogEntry[] = [];
  const seen = new Set<string>();

  const append = (
    seed: string,
    toolName: string,
    raw: string,
    args?: string | null,
    result?: string | null,
  ) => {
    const normalizedTool = toolName.trim();
    if (!normalizedTool) {
      return;
    }
    const key = `${normalizedTool}|${args ?? ""}|${result ?? ""}|${raw}`;
    if (seen.has(key)) {
      return;
    }
    seen.add(key);
    const nextIndex = entries.length;
    entries.push({
      id: `${seed}-${nextIndex}`,
      toolName: normalizedTool,
      friendlyStep: friendlyStepForTool(normalizedTool),
      args: args ?? null,
      result: result ?? null,
      raw,
    });
  };

  thinkingText
    .split(/\r?\n/g)
    .map((line) => line.trim())
    .filter(Boolean)
    .forEach((line) => {
      const parsed = parseToolLine(line);
      if (!parsed) {
        return;
      }
      append("stream", parsed.toolName, parsed.raw, parsed.args, parsed.result);
    });

  toolCalls.forEach((toolName) => {
    append("payload", toolName, toolName, null, null);
  });

  return entries;
}

function extractStatusSteps(payload: Record<string, unknown> | null | undefined): string[] {
  const record = asRecord(payload);
  if (!record) {
    return [];
  }
  const statusRecord = asRecord(record.status);
  const rawSteps = statusRecord?.steps;
  if (!Array.isArray(rawSteps)) {
    return [];
  }
  return rawSteps
    .map((value) => String(value ?? "").trim())
    .filter((value, index, array) => Boolean(value) && array.indexOf(value) === index);
}

function mergeUniqueToolCalls(...sources: string[][]): string[] {
  const merged: string[] = [];
  const seen = new Set<string>();
  sources.flat().forEach((entry) => {
    const cleaned = String(entry ?? "").trim();
    if (!cleaned || seen.has(cleaned)) {
      return;
    }
    seen.add(cleaned);
    merged.push(cleaned);
  });
  return merged;
}

function areProcessLogsEqual(
  current: Record<number, ProcessLogEntry[]>,
  next: Record<number, ProcessLogEntry[]>,
): boolean {
  const currentKeys = Object.keys(current);
  const nextKeys = Object.keys(next);
  if (currentKeys.length !== nextKeys.length) {
    return false;
  }
  for (const key of nextKeys) {
    const turnId = Number.parseInt(key, 10);
    const currentEntries = current[turnId] ?? [];
    const nextEntries = next[turnId] ?? [];
    if (currentEntries.length !== nextEntries.length) {
      return false;
    }
    for (let index = 0; index < nextEntries.length; index += 1) {
      const a = currentEntries[index];
      const b = nextEntries[index];
      if (
        a?.toolName !== b?.toolName ||
        a?.friendlyStep !== b?.friendlyStep ||
        a?.args !== b?.args ||
        a?.result !== b?.result ||
        a?.raw !== b?.raw
      ) {
        return false;
      }
    }
  }
  return true;
}

function areSubmissionBuffersEqual(
  current: Record<number, string>,
  next: Record<number, string>,
): boolean {
  const currentKeys = Object.keys(current);
  const nextKeys = Object.keys(next);
  if (currentKeys.length !== nextKeys.length) {
    return false;
  }
  for (const key of nextKeys) {
    const turnId = Number.parseInt(key, 10);
    if ((current[turnId] ?? "") !== (next[turnId] ?? "")) {
      return false;
    }
  }
  return true;
}

function areTextMapsEqual(
  current: Record<number, string>,
  next: Record<number, string>,
): boolean {
  const currentKeys = Object.keys(current);
  const nextKeys = Object.keys(next);
  if (currentKeys.length !== nextKeys.length) {
    return false;
  }
  for (const key of nextKeys) {
    const turnId = Number.parseInt(key, 10);
    if ((current[turnId] ?? "") !== (next[turnId] ?? "")) {
      return false;
    }
  }
  return true;
}

function arePreviewMapsEqual(
  current: Record<number, SubmissionDraftPreview>,
  next: Record<number, SubmissionDraftPreview>,
): boolean {
  const currentKeys = Object.keys(current);
  const nextKeys = Object.keys(next);
  if (currentKeys.length !== nextKeys.length) {
    return false;
  }
  for (const key of nextKeys) {
    const turnId = Number.parseInt(key, 10);
    const currentPreview = current[turnId];
    const nextPreview = next[turnId];
    if (!currentPreview || !nextPreview) {
      return false;
    }
    if (submissionDraftSignature(currentPreview) !== submissionDraftSignature(nextPreview)) {
      return false;
    }
  }
  return true;
}

type PkCitationLinkProps = {
  label: string;
  pk: number;
  showHoverCard: boolean;
  onOpenDetail: (pk: number) => void;
  onEnsureHoverMetadata: (pk: number) => void;
  hoverMetadata?: NodeHoverMetadataState;
};

function formatMetadataValue(value: string | null | undefined): string {
  const text = typeof value === "string" ? value.trim() : "";
  return text || "N/A";
}

function PkCitationLink({
  label,
  pk,
  showHoverCard,
  onOpenDetail,
  onEnsureHoverMetadata,
  hoverMetadata,
}: PkCitationLinkProps) {
  const [isTooltipVisible, setIsTooltipVisible] = useState(false);

  const handleShowTooltip = () => {
    setIsTooltipVisible(true);
    if (showHoverCard) {
      onEnsureHoverMetadata(pk);
    }
  };

  const handleHideTooltip = () => {
    setIsTooltipVisible(false);
  };

  const formula = formatMetadataValue(hoverMetadata?.data?.formula);
  const spacegroup = formatMetadataValue(hoverMetadata?.data?.spacegroup);
  const nodeType = formatMetadataValue(hoverMetadata?.data?.node_type);

  return (
    <span className="relative inline-flex align-baseline">
      <span
        role="button"
        tabIndex={0}
        className="font-mono text-sky-600 underline decoration-dotted underline-offset-2 transition-colors hover:text-sky-700 dark:text-sky-400 dark:hover:text-sky-300"
        onClick={() => onOpenDetail(pk)}
        onMouseEnter={handleShowTooltip}
        onMouseLeave={handleHideTooltip}
        onFocus={handleShowTooltip}
        onBlur={handleHideTooltip}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            onOpenDetail(pk);
          }
        }}
      >
        {label}
      </span>
      {showHoverCard && isTooltipVisible ? (
        <span
          role="status"
          className="pointer-events-none absolute left-0 top-full z-40 mt-1.5 w-56 rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-xs text-zinc-100 shadow-2xl"
        >
          <p className="mb-2 font-mono text-[11px] text-zinc-300">Node #{pk}</p>
          {hoverMetadata?.status === "loading" ? (
            <p className="text-zinc-200">Loading metadata...</p>
          ) : hoverMetadata?.status === "error" ? (
            <p className="text-zinc-200">Metadata unavailable.</p>
          ) : (
            <div className="space-y-1.5">
              <p className="flex items-start justify-between gap-2">
                <span className="uppercase tracking-[0.08em] text-zinc-400">Formula</span>
                <span className="text-right text-zinc-100">{formula}</span>
              </p>
              <p className="flex items-start justify-between gap-2">
                <span className="uppercase tracking-[0.08em] text-zinc-400">Spacegroup</span>
                <span className="text-right text-zinc-100">{spacegroup}</span>
              </p>
              <p className="flex items-start justify-between gap-2">
                <span className="uppercase tracking-[0.08em] text-zinc-400">Node Type</span>
                <span className="text-right text-zinc-100">{nodeType}</span>
              </p>
            </div>
          )}
        </span>
      ) : null}
    </span>
  );
}

function renderTextWithSmartCitations(
  text: string,
  handleOpenDetail: (pk: number) => void,
  hoverMetadataByPk: Record<number, NodeHoverMetadataState>,
  ensureHoverMetadata: (pk: number) => void,
): ReactNode[] {
  const nodes: ReactNode[] = [];
  const pattern = /#\s*(\d+)\b|\b(?:PK|Node|structure)\s*(\d+)\b/gi;
  let cursor = 0;
  let match = pattern.exec(text);

  while (match) {
    const [full] = match;
    const pk = toPositiveInteger(match[1] ?? match[2]);
    const start = match.index;
    const end = start + full.length;
    if (start > cursor) {
      nodes.push(text.slice(cursor, start));
    }
    if (pk !== null) {
      const isHashToken = Boolean(match[1]);
      nodes.push(
        <PkCitationLink
          key={`pk-link-${start}-${pk}`}
          label={full}
          pk={pk}
          showHoverCard={isHashToken}
          onOpenDetail={handleOpenDetail}
          onEnsureHoverMetadata={ensureHoverMetadata}
          hoverMetadata={hoverMetadataByPk[pk]}
        />,
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

async function copyTextToClipboard(text: string): Promise<void> {
  if (!text.trim()) {
    return;
  }
  try {
    await navigator.clipboard.writeText(text);
  } catch (error) {
    console.error("Failed to copy message text", error);
  }
}

function groupMessages(messages: ChatMessage[]): ChatTurn[] {
  const grouped = new Map<number, ChatTurn>();

  messages.forEach((message, index) => {
    const turnId = message.turn_id > 0 ? message.turn_id : index + 1;
    const turn = grouped.get(turnId) ?? { turnId };

    if (message.role === "user") {
      turn.userText = message.text;
      turn.userPayload = asRecord(message.payload);
    } else if (message.status === "thinking") {
      turn.thinkingText = message.text;
      turn.thinkingPayload = asRecord(message.payload);
      turn.assistantStatus = "thinking";
    } else {
      turn.assistantText = message.text;
      turn.assistantStatus = message.status;
      turn.assistantPayload = asRecord(message.payload);
    }

    grouped.set(turnId, turn);
  });

  return [...grouped.values()].sort((a, b) => a.turnId - b.turnId);
}

type ChatPanelProps = {
  messages: ChatMessage[];
  models: string[];
  selectedModel: string;
  composerResetVersion: number;
  quickPrompts: Array<{ label: string; prompt: string }>;
  contextNodes: FocusNode[];
  isLoading: boolean;
  activeTurnId: number | null;
  onSendMessage: (text: string, options?: { resourceAttachments?: ResourceAttachment[] }) => void;
  onStopResponse: () => void;
  onModelChange: (model: string) => void;
  onAttachFile: (file: File) => void;
  onAddContextNode: (node: FocusNode) => void;
  onRemoveContextNode: (pk: number) => void;
  onOpenDetail: (pk: number) => void;
  onRestoreContextNodes: (nodes: FocusNode[]) => void;
};

function normalizeDroppedContextNode(raw: unknown): FocusNode | null {
  const record = asRecord(raw);
  if (!record) {
    return null;
  }
  const pk = toPositiveInteger(record.pk);
  if (pk === null) {
    return null;
  }
  const label = typeof record.label === "string" && record.label.trim() ? record.label.trim() : `#${pk}`;
  const formula = typeof record.formula === "string" && record.formula.trim() ? record.formula.trim() : null;
  const nodeType =
    typeof record.node_type === "string" && record.node_type.trim() ? record.node_type.trim() : "Unknown";
  return { pk, label, formula, node_type: nodeType };
}

function parseDroppedContextNode(event: DragEvent<HTMLElement>): FocusNode | null {
  const rawPayload = event.dataTransfer.getData(CONTEXT_NODE_DRAG_MIME);
  if (rawPayload) {
    try {
      const parsed = JSON.parse(rawPayload);
      const node = normalizeDroppedContextNode(parsed);
      if (node) {
        return node;
      }
    } catch {
      // Ignore malformed drag payload and fall back to plain text parsing.
    }
  }

  const plainText = event.dataTransfer.getData("text/plain");
  const match = plainText.match(/#\s*(\d+)\b/);
  const pk = toPositiveInteger(match?.[1]);
  if (pk === null) {
    return null;
  }
  return {
    pk,
    label: `#${pk}`,
    formula: null,
    node_type: "Unknown",
  };
}

function normalizeDroppedResourceAttachment(raw: unknown): ResourceAttachment | null {
  const record = asRecord(raw);
  if (!record) {
    return null;
  }
  const rawKind = typeof record.kind === "string" ? record.kind.trim().toLowerCase() : "";
  if (rawKind !== "computer" && rawKind !== "code" && rawKind !== "plugin") {
    return null;
  }
  const value = typeof record.value === "string" ? record.value.trim() : "";
  if (!value) {
    return null;
  }
  const label =
    typeof record.label === "string" && record.label.trim() ? record.label.trim() : value;
  const plugin =
    typeof record.plugin === "string" && record.plugin.trim() ? record.plugin.trim() : null;
  const computerLabel =
    typeof record.computerLabel === "string" && record.computerLabel.trim()
      ? record.computerLabel.trim()
      : typeof record.computer_label === "string" && record.computer_label.trim()
        ? record.computer_label.trim()
        : null;
  const hostname =
    typeof record.hostname === "string" && record.hostname.trim() ? record.hostname.trim() : null;
  return {
    kind: rawKind,
    value,
    label,
    plugin,
    computerLabel,
    hostname,
  };
}

function parseDroppedResourceAttachment(event: DragEvent<HTMLElement>): ResourceAttachment | null {
  const rawPayload = event.dataTransfer.getData(RESOURCE_ATTACHMENT_DRAG_MIME);
  if (!rawPayload) {
    return null;
  }
  try {
    const parsed = JSON.parse(rawPayload);
    return normalizeDroppedResourceAttachment(parsed);
  } catch {
    return null;
  }
}

function insertPkTokenAtSelection(
  text: string,
  pk: number,
  selectionStart: number,
  selectionEnd: number,
): { value: string; caret: number } {
  const token = `#${pk}`;
  const start = Math.max(0, Math.min(selectionStart, text.length));
  const end = Math.max(start, Math.min(selectionEnd, text.length));
  const prefix = text.slice(0, start);
  const suffix = text.slice(end);
  const needsLeadingSpace = prefix.length > 0 && !/\s$/.test(prefix);
  const needsTrailingSpace = suffix.length > 0 && !/^\s/.test(suffix);
  const inserted = `${needsLeadingSpace ? " " : ""}${token}${needsTrailingSpace ? " " : ""}`;
  const value = `${prefix}${inserted}${suffix}`;
  return { value, caret: prefix.length + inserted.length };
}

function resourceAttachmentIcon(kind: ResourceAttachment["kind"]) {
  if (kind === "computer") {
    return <Cpu className="h-3 w-3" />;
  }
  if (kind === "code") {
    return <Code2 className="h-3 w-3" />;
  }
  return <PlugZap className="h-3 w-3" />;
}

function resourceAttachmentKey(attachment: ResourceAttachment): string {
  return `${attachment.kind}:${attachment.value.trim().toLowerCase()}`;
}

export function ChatPanel({
  messages,
  models,
  selectedModel,
  composerResetVersion,
  quickPrompts,
  contextNodes,
  isLoading,
  activeTurnId,
  onSendMessage,
  onStopResponse,
  onModelChange,
  onAttachFile,
  onAddContextNode,
  onRemoveContextNode,
  onOpenDetail,
  onRestoreContextNodes,
}: ChatPanelProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const modelMenuRef = useRef<HTMLDivElement | null>(null);
  const messagesContainerRef = useRef<HTMLDivElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const scrollRafRef = useRef<number | null>(null);
  const [draft, setDraft] = useState("");
  const [resourceAttachments, setResourceAttachments] = useState<ResourceAttachment[]>([]);
  const [isModelMenuOpen, setIsModelMenuOpen] = useState(false);
  const [avatarFailed, setAvatarFailed] = useState(false);
  const [isAutoScrollEnabled, setIsAutoScrollEnabled] = useState(true);
  const [dragOverZone, setDragOverZone] = useState<"textarea" | "attachment" | null>(null);
  const [previewStateByTurn, setPreviewStateByTurn] = useState<Record<number, SubmissionModalState>>({});
  const [submittedPreviewByTurn, setSubmittedPreviewByTurn] = useState<Record<number, SubmittedPreviewSummary>>({});
  const [expandedSubmissionByTurn, setExpandedSubmissionByTurn] = useState<Record<number, boolean>>({});
  const [currentStep, setCurrentStep] = useState("");
  const [currentStepTurnId, setCurrentStepTurnId] = useState<number | null>(null);
  const [processLogByTurn, setProcessLogByTurn] = useState<Record<number, ProcessLogEntry[]>>({});
  const [submissionDraftBufferByTurn, setSubmissionDraftBufferByTurn] = useState<Record<number, string>>({});
  const [turnTextBufferByTurn, setTurnTextBufferByTurn] = useState<Record<number, string>>({});
  const [stableThinkingTextByTurn, setStableThinkingTextByTurn] = useState<Record<number, string>>({});
  const [stableAssistantTextByTurn, setStableAssistantTextByTurn] = useState<Record<number, string>>({});
  const [stableSubmissionDraftByTurn, setStableSubmissionDraftByTurn] = useState<
    Record<number, SubmissionDraftPreview>
  >({});
  const [nodeHoverMetadataByPk, setNodeHoverMetadataByPk] = useState<Record<number, NodeHoverMetadataState>>({});
  const nodeHoverMetadataRef = useRef<Record<number, NodeHoverMetadataState>>({});

  const turns = useMemo(() => groupMessages(messages), [messages]);
  const latestTurnId = turns.length > 0 ? turns[turns.length - 1].turnId : null;
  const latestTurnSignature = useMemo(() => {
    if (turns.length === 0) {
      return "empty";
    }
    const latestTurn = turns[turns.length - 1];
    return [
      turns.length,
      latestTurn.turnId,
      latestTurn.thinkingText ?? "",
      latestTurn.assistantText ?? "",
      latestTurn.assistantStatus ?? "",
    ].join("|");
  }, [turns]);
  const isNearBottom = useCallback(() => {
    const container = messagesContainerRef.current;
    if (!container) {
      return true;
    }
    const remainingDistance = container.scrollHeight - container.scrollTop - container.clientHeight;
    return remainingDistance <= 96;
  }, []);
  const scrollToBottom = useCallback((behavior: ScrollBehavior = "smooth") => {
    if (!messagesEndRef.current) {
      return;
    }
    if (scrollRafRef.current !== null) {
      window.cancelAnimationFrame(scrollRafRef.current);
    }
    scrollRafRef.current = window.requestAnimationFrame(() => {
      messagesEndRef.current?.scrollIntoView({ behavior, block: "end" });
      scrollRafRef.current = null;
    });
  }, []);

  useEffect(() => {
    nodeHoverMetadataRef.current = nodeHoverMetadataByPk;
  }, [nodeHoverMetadataByPk]);

  const ensureNodeHoverMetadata = useCallback((pk: number) => {
    if (!Number.isInteger(pk) || pk <= 0) {
      return;
    }
    const currentState = nodeHoverMetadataRef.current[pk];
    if (currentState?.status === "loading" || currentState?.status === "loaded") {
      return;
    }

    setNodeHoverMetadataByPk((current) => ({
      ...current,
      [pk]: { status: "loading", data: null },
    }));

    void getNodeHoverMetadata(pk)
      .then((metadata) => {
        setNodeHoverMetadataByPk((current) => ({
          ...current,
          [pk]: { status: "loaded", data: metadata },
        }));
      })
      .catch(() => {
        setNodeHoverMetadataByPk((current) => ({
          ...current,
          [pk]: { status: "error", data: null },
        }));
      });
  }, []);

  useEffect(() => {
    const handleOutside = (event: MouseEvent) => {
      if (!modelMenuRef.current) {
        return;
      }
      if (!modelMenuRef.current.contains(event.target as Node)) {
        setIsModelMenuOpen(false);
      }
    };

    window.addEventListener("mousedown", handleOutside);
    return () => window.removeEventListener("mousedown", handleOutside);
  }, []);

  useEffect(() => {
    return () => {
      if (scrollRafRef.current !== null) {
        window.cancelAnimationFrame(scrollRafRef.current);
      }
    };
  }, []);

  useEffect(() => {
    const clearDragZone = () => setDragOverZone(null);
    window.addEventListener("dragend", clearDragZone);
    window.addEventListener("drop", clearDragZone);
    return () => {
      window.removeEventListener("dragend", clearDragZone);
      window.removeEventListener("drop", clearDragZone);
    };
  }, []);

  useEffect(() => {
    if (!isAutoScrollEnabled) {
      return;
    }
    scrollToBottom("smooth");
  }, [isAutoScrollEnabled, isLoading, latestTurnSignature, scrollToBottom]);

  useEffect(() => {
    if (!isLoading) {
      return;
    }
    if (isNearBottom()) {
      setIsAutoScrollEnabled(true);
    }
  }, [isLoading, isNearBottom]);

  useEffect(() => {
    const turnIds = new Set(turns.map((turn) => turn.turnId));
    setPreviewStateByTurn((current) => {
      const next: Record<number, SubmissionModalState> = {};
      let changed = false;
      for (const [turnKey, state] of Object.entries(current)) {
        const turnId = Number.parseInt(turnKey, 10);
        if (turnIds.has(turnId)) {
          next[turnId] = state;
          continue;
        }
        changed = true;
      }
      return changed ? next : current;
    });
    setSubmittedPreviewByTurn((current) => {
      const next: Record<number, SubmittedPreviewSummary> = {};
      let changed = false;
      for (const [turnKey, summary] of Object.entries(current)) {
        const turnId = Number.parseInt(turnKey, 10);
        if (turnIds.has(turnId)) {
          next[turnId] = summary;
          continue;
        }
        changed = true;
      }
      return changed ? next : current;
    });
    setExpandedSubmissionByTurn((current) => {
      const next: Record<number, boolean> = {};
      let changed = false;
      Object.entries(current).forEach(([turnKey, expanded]) => {
        const turnId = Number.parseInt(turnKey, 10);
        if (turnIds.has(turnId)) {
          next[turnId] = expanded;
          return;
        }
        changed = true;
      });
      return changed ? next : current;
    });
  }, [turns]);

  useEffect(() => {
    setExpandedSubmissionByTurn((current) => {
      const next = { ...current };
      let changed = false;
      turns.forEach((turn) => {
        const assistantText = turnTextBufferByTurn[turn.turnId] ?? turn.assistantText ?? "";
        const hasSubmissionTag = assistantText.toUpperCase().includes(SUBMISSION_DRAFT_TAG);
        const hasSubmissionPayload = Boolean(extractSubmissionDraft(turn.assistantPayload));
        const hasSubmissionSignal = hasSubmissionTag || hasSubmissionPayload || Boolean(stableSubmissionDraftByTurn[turn.turnId]);
        if (!hasSubmissionSignal || Object.prototype.hasOwnProperty.call(next, turn.turnId)) {
          return;
        }
        next[turn.turnId] = true;
        changed = true;
      });
      return changed ? next : current;
    });
  }, [stableSubmissionDraftByTurn, turnTextBufferByTurn, turns]);

  useEffect(() => {
    const next: Record<number, ProcessLogEntry[]> = {};
    turns.forEach((turn) => {
      const thinkingToolCalls = extractToolCalls(turn.thinkingPayload);
      const assistantToolCalls = extractToolCalls(turn.assistantPayload);
      const statusSteps = extractStatusSteps(turn.thinkingPayload);
      const turnToolCalls = mergeUniqueToolCalls(thinkingToolCalls, assistantToolCalls, statusSteps);
      const turnProcessLog = buildProcessLogEntries(turn.thinkingText ?? "", turnToolCalls);
      if (turnProcessLog.length > 0) {
        next[turn.turnId] = turnProcessLog;
      }
    });
    setProcessLogByTurn((current) => (areProcessLogsEqual(current, next) ? current : next));
  }, [turns]);

  useEffect(() => {
    const turnIds = new Set(turns.map((turn) => turn.turnId));
    setTurnTextBufferByTurn((current) => {
      const next: Record<number, string> = {};
      turns.forEach((turn) => {
        const merged = mergeTurnTextBuffer(current[turn.turnId], turn.assistantText ?? "");
        if (merged.trim()) {
          next[turn.turnId] = merged;
          return;
        }
        if (current[turn.turnId]) {
          next[turn.turnId] = current[turn.turnId];
        }
      });
      for (const key of Object.keys(next)) {
        const turnId = Number.parseInt(key, 10);
        if (!turnIds.has(turnId)) {
          delete next[turnId];
        }
      }
      return areTextMapsEqual(current, next) ? current : next;
    });
  }, [turns]);

  useEffect(() => {
    setSubmissionDraftBufferByTurn((current) => {
      const next: Record<number, string> = {};
      turns.forEach((turn) => {
        const sourceText = turnTextBufferByTurn[turn.turnId] ?? turn.assistantText ?? "";
        const parsed = parseSubmissionDraftTag(sourceText, current[turn.turnId]);
        if (parsed.bufferedFragment) {
          next[turn.turnId] = parsed.bufferedFragment;
        }
      });
      return areSubmissionBuffersEqual(current, next) ? current : next;
    });
  }, [turnTextBufferByTurn, turns]);

  useEffect(() => {
    const turnIds = new Set(turns.map((turn) => turn.turnId));
    setStableThinkingTextByTurn((current) => {
      const next: Record<number, string> = {};
      turns.forEach((turn) => {
        const thinkingText = turn.thinkingText ?? "";
        if (thinkingText.trim()) {
          next[turn.turnId] = thinkingText;
          return;
        }
        if (current[turn.turnId]) {
          next[turn.turnId] = current[turn.turnId];
        }
      });
      for (const key of Object.keys(next)) {
        const turnId = Number.parseInt(key, 10);
        if (!turnIds.has(turnId)) {
          delete next[turnId];
        }
      }
      return areTextMapsEqual(current, next) ? current : next;
    });

    setStableAssistantTextByTurn((current) => {
      const next: Record<number, string> = {};
      turns.forEach((turn) => {
        const sourceText = turnTextBufferByTurn[turn.turnId] ?? turn.assistantText ?? "";
        const parsed = parseSubmissionDraftTag(
          sourceText,
          submissionDraftBufferByTurn[turn.turnId],
        );
        const clean = parsed.cleanText ?? "";
        if (clean.trim()) {
          next[turn.turnId] = clean;
          return;
        }
        if (current[turn.turnId]) {
          next[turn.turnId] = current[turn.turnId];
        }
      });
      for (const key of Object.keys(next)) {
        const turnId = Number.parseInt(key, 10);
        if (!turnIds.has(turnId)) {
          delete next[turnId];
        }
      }
      return areTextMapsEqual(current, next) ? current : next;
    });

    setStableSubmissionDraftByTurn((current) => {
      const next: Record<number, SubmissionDraftPreview> = {};
      turns.forEach((turn) => {
        const sourceText = turnTextBufferByTurn[turn.turnId] ?? turn.assistantText ?? "";
        const preview = resolveTurnSubmissionDraft(
          { ...turn, assistantText: sourceText },
          submissionDraftBufferByTurn[turn.turnId],
        );
        if (preview) {
          next[turn.turnId] = preview;
          return;
        }
        if (current[turn.turnId]) {
          next[turn.turnId] = current[turn.turnId];
        }
      });
      for (const key of Object.keys(next)) {
        const turnId = Number.parseInt(key, 10);
        if (!turnIds.has(turnId)) {
          delete next[turnId];
        }
      }
      return arePreviewMapsEqual(current, next) ? current : next;
    });
  }, [submissionDraftBufferByTurn, turnTextBufferByTurn, turns]);

  useEffect(() => {
    const thinkingTurnId = activeTurnId ?? latestTurnId;
    if (!isLoading || thinkingTurnId === null) {
      setCurrentStep("");
      setCurrentStepTurnId(null);
      return;
    }

    const activeTurn = turns.find((turn) => turn.turnId === thinkingTurnId);
    if (!activeTurn) {
      setCurrentStep("");
      setCurrentStepTurnId(null);
      return;
    }

    const hasFinalAssistantState = Boolean(activeTurn.assistantStatus) && activeTurn.assistantStatus !== "thinking";
    const activeThinkingToolCalls = extractToolCalls(activeTurn.thinkingPayload);
    const activeAssistantToolCalls = extractToolCalls(activeTurn.assistantPayload);
    const activeStatusSteps = extractStatusSteps(activeTurn.thinkingPayload);
    const activeToolCalls = mergeUniqueToolCalls(activeThinkingToolCalls, activeAssistantToolCalls, activeStatusSteps);
    const processLog =
      processLogByTurn[thinkingTurnId] ??
      buildProcessLogEntries(activeTurn.thinkingText ?? "", activeToolCalls);
    const isThinkingTurn =
      !hasFinalAssistantState &&
      (Boolean(activeTurn.thinkingText) || processLog.length > 0);
    if (!isThinkingTurn) {
      setCurrentStep("");
      setCurrentStepTurnId(null);
      return;
    }

    const nextStep = processLog.length > 0 ? processLog[processLog.length - 1].friendlyStep : "";
    setCurrentStepTurnId(thinkingTurnId);
    setCurrentStep((previous) => (previous === nextStep ? previous : nextStep));
  }, [activeTurnId, isLoading, latestTurnId, processLogByTurn, turns]);

  const updateTextareaHeight = (target: HTMLTextAreaElement) => {
    target.style.height = "0px";
    target.style.height = `${Math.min(target.scrollHeight, 220)}px`;
  };

  const handleSubmit = () => {
    if (isLoading) {
      return;
    }
    const text = draft.trim();
    if (!text) {
      return;
    }
    setIsAutoScrollEnabled(true);
    scrollToBottom("smooth");
    onSendMessage(text, { resourceAttachments });
  };

  const isDraftEmpty = !draft.trim();
  const hasContextNodes = contextNodes.length > 0;
  const hasResourceAttachments = resourceAttachments.length > 0;
  const hasAnyAttachments = hasContextNodes || hasResourceAttachments;
  const structureContextNodes = useMemo(
    () => contextNodes.filter((node) => node.node_type === STRUCTURE_NODE_TYPE),
    [contextNodes],
  );
  const hasStructureContext = structureContextNodes.length > 0;
  const structureContextPks = useMemo(
    () => structureContextNodes.map((node) => node.pk),
    [structureContextNodes],
  );

  const handleConfirmPreview = useCallback(
    async (turnId: number, preview: SubmissionDraftPreview, draftPayload?: SubmissionSubmitDraft) => {
      setPreviewStateByTurn((current) => ({
        ...current,
        [turnId]: { status: "submitting", processPk: null, processPks: [], errorText: null },
      }));
      try {
        const response = await submitPreviewDraft(draftPayload ?? preview.submitDraft);
        const processPks = extractProcessPks(response);
        const processPk = processPks[0] ?? null;
        setPreviewStateByTurn((current) => ({
          ...current,
          [turnId]: { status: "submitted", processPk, processPks, errorText: null },
        }));
        setSubmittedPreviewByTurn((current) => ({
          ...current,
          [turnId]: {
            processLabel: preview.submissionDraft.process_label || "AiiDA Workflow",
            processPks,
          },
        }));
      } catch (error) {
        const errorText = error instanceof Error ? error.message : "Failed to submit workflow.";
        setPreviewStateByTurn((current) => ({
          ...current,
          [turnId]: { status: "error", processPk: null, processPks: [], errorText },
        }));
      }
    },
    [],
  );

  const handleCancelPreview = useCallback(async (turnId: number) => {
    setPreviewStateByTurn((current) => ({
      ...current,
      [turnId]: { status: "cancelled", processPk: null, processPks: [], errorText: null },
    }));
    try {
      await cancelPendingSubmission();
    } catch (error) {
      console.error("Failed to clear pending submission", error);
    }
  }, []);

  const handleReaskMessage = useCallback(
    (text: string, contextFromMessage: FocusNode[]) => {
      const cleaned = text.trim();
      if (!cleaned) {
        return;
      }
      setDraft(cleaned);
      onRestoreContextNodes(contextFromMessage);
      window.requestAnimationFrame(() => {
        const target = textareaRef.current;
        if (!target) {
          return;
        }
        target.focus();
        updateTextareaHeight(target);
      });
    },
    [onRestoreContextNodes],
  );

  const handleQuickActionPrompt = useCallback(
    (label: string, prompt: string) => {
      const kind = inferQuickActionKind(label, prompt);
      if (quickActionRequiresStructure(kind) && structureContextPks.length === 0) {
        return;
      }
      const intent = buildQuickActionIntent(label, prompt, structureContextPks);
      setIsAutoScrollEnabled(true);
      scrollToBottom("smooth");
      onSendMessage(intent, { resourceAttachments });
    },
    [onSendMessage, resourceAttachments, scrollToBottom, structureContextPks],
  );

  const handleAttachResource = useCallback((attachment: ResourceAttachment) => {
    const normalizedValue = attachment.value.trim();
    if (!normalizedValue) {
      return;
    }
    setResourceAttachments((current) => {
      const key = resourceAttachmentKey(attachment);
      if (current.some((item) => resourceAttachmentKey(item) === key)) {
        return current;
      }
      return [...current, { ...attachment, value: normalizedValue }];
    });
  }, []);

  const handleRemoveResourceAttachment = useCallback((attachment: ResourceAttachment) => {
    const key = resourceAttachmentKey(attachment);
    setResourceAttachments((current) => current.filter((item) => resourceAttachmentKey(item) !== key));
  }, []);

  useEffect(() => {
    setDraft("");
    setResourceAttachments([]);
    setDragOverZone(null);
    if (textareaRef.current) {
      textareaRef.current.style.height = "56px";
    }
  }, [composerResetVersion]);

  return (
    <Panel className="flex h-full min-h-0 min-w-0 flex-1 flex-col gap-2 overflow-x-hidden p-0">
      <div
        ref={messagesContainerRef}
        className="minimal-scrollbar min-h-0 flex-1 space-y-5 overflow-x-hidden overflow-y-auto px-5 pb-6 pt-5 md:px-8"
        onScroll={() => {
          const nearBottom = isNearBottom();
          setIsAutoScrollEnabled((current) => (current === nearBottom ? current : nearBottom));
        }}
      >
        {turns.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <p className="text-3xl font-medium tracking-tight text-zinc-900 dark:text-zinc-100">
              Ask SABR about your AiiDA workflow
            </p>
            <p className="mt-2 max-w-xl text-sm text-zinc-500 dark:text-zinc-400">
              Profile-aware assistant with live process telemetry and runtime logs.
            </p>
          </div>
        ) : (
          turns.map((turn) => {
            const assistantStreamText = turnTextBufferByTurn[turn.turnId] ?? turn.assistantText ?? "";
            const thinkingText = (turn.thinkingText ?? "").trim()
              ? (turn.thinkingText ?? "")
              : (stableThinkingTextByTurn[turn.turnId] ?? "");
            const taggedSubmissionDraft = parseSubmissionDraftTag(
              assistantStreamText,
              submissionDraftBufferByTurn[turn.turnId],
            );
            const assistantSubmissionDraft = extractSubmissionDraft(turn.assistantPayload);
            const submissionDraft =
              assistantSubmissionDraft ??
              taggedSubmissionDraft.preview ??
              stableSubmissionDraftByTurn[turn.turnId] ??
              null;
            const assistantText =
              taggedSubmissionDraft.cleanText.trim().length > 0
                ? taggedSubmissionDraft.cleanText
                : (stableAssistantTextByTurn[turn.turnId] ?? taggedSubmissionDraft.cleanText);
            const visibleAssistantText = stripSubmissionDraftBlocks(assistantText);
            const hasAssistantText = Boolean(visibleAssistantText.trim());
            const hasFinalAssistantState =
              Boolean(turn.assistantStatus) &&
              turn.assistantStatus !== "thinking" &&
              (hasAssistantText || turn.assistantStatus === "error" || Boolean(submissionDraft));
            const thinkingToolCalls = extractToolCalls(turn.thinkingPayload);
            const assistantToolCalls = extractToolCalls(turn.assistantPayload);
            const statusSteps = extractStatusSteps(turn.thinkingPayload);
            const turnToolCalls = mergeUniqueToolCalls(thinkingToolCalls, assistantToolCalls, statusSteps);
            const processLog =
              processLogByTurn[turn.turnId] ?? buildProcessLogEntries(thinkingText, turnToolCalls);
            const turnCurrentStep =
              currentStepTurnId === turn.turnId
                ? currentStep
                : processLog.length > 0
                  ? processLog[processLog.length - 1].friendlyStep
                  : "";
            const thinkingTurnId = activeTurnId ?? latestTurnId;
            const isTurnActivelyThinking =
              turn.assistantStatus === "thinking" ||
              (isLoading && turn.turnId === thinkingTurnId);
            const hasThinkingSignal =
              Boolean(thinkingText.trim()) || processLog.length > 0 || Boolean(turnCurrentStep);
            const showThinking =
              hasThinkingSignal &&
              (isTurnActivelyThinking || !hasFinalAssistantState);
            const showAssistant = hasAssistantText || turn.assistantStatus === "error" || Boolean(submissionDraft);
            const hasAssistantRowSignal =
              showThinking ||
              showAssistant ||
              Boolean(stableAssistantTextByTurn[turn.turnId]) ||
              Boolean(stableThinkingTextByTurn[turn.turnId]) ||
              isTurnActivelyThinking;
            const userContextPks = extractContextPks(turn.userPayload);
            const userContextNodesRaw = extractContextNodes(turn.userPayload);
            const userContextNodes =
              userContextNodesRaw.length > 0
                ? userContextNodesRaw
                : userContextPks.map((pk) => ({
                    pk,
                    label: `#${pk}`,
                    formula: null,
                    node_type: "Unknown",
                  }));
            const previewState = previewStateByTurn[turn.turnId] ?? { status: "idle" as const };
            const submittedPreview = submittedPreviewByTurn[turn.turnId];
            const isSubmissionExpanded = expandedSubmissionByTurn[turn.turnId] ?? true;

            return (
              <article key={turn.turnId} className="space-y-3">
                {turn.userText ? (
                  <div className="flex justify-end">
                    <div className="group relative max-w-[78%] rounded-2xl border border-zinc-200/80 bg-white/90 px-4 py-3 text-sm leading-6 text-zinc-900 shadow-sm dark:border-zinc-800 dark:bg-zinc-900/80 dark:text-zinc-100">
                      <p className="whitespace-pre-wrap">
                        {renderTextWithSmartCitations(
                          turn.userText,
                          onOpenDetail,
                          nodeHoverMetadataByPk,
                          ensureNodeHoverMetadata,
                        )}
                      </p>
                      {userContextPks.length > 0 ? (
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {userContextPks.map((pk) => (
                            <span
                              key={`${turn.turnId}-ctx-${pk}`}
                              className="rounded-full border border-zinc-300/80 bg-zinc-100/90 px-2 py-0.5 font-mono text-[10px] text-zinc-600 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300"
                            >
                              PK {pk}
                            </span>
                          ))}
                        </div>
                      ) : null}
                      <div className="pointer-events-none absolute -top-2 right-2 flex items-center gap-1 rounded-md border border-zinc-200/80 bg-white/95 px-1.5 py-1 opacity-0 shadow-sm transition-opacity duration-150 group-hover:pointer-events-auto group-hover:opacity-100 dark:border-zinc-700 dark:bg-zinc-950/95">
                        <button
                          type="button"
                          className="inline-flex h-6 w-6 items-center justify-center rounded text-zinc-500 transition-colors hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
                          onClick={() => void copyTextToClipboard(turn.userText ?? "")}
                          aria-label="Copy message"
                        >
                          <Copy className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          className="inline-flex h-6 w-6 items-center justify-center rounded text-zinc-500 transition-colors hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
                          onClick={() => handleReaskMessage(turn.userText ?? "", userContextNodes)}
                          aria-label="Re-ask message"
                        >
                          <RotateCcw className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>
                ) : null}

                {hasAssistantRowSignal ? (
                  <div className="flex items-start gap-3">
                    {avatarFailed ? (
                      <div className="mt-0.5 flex h-7 w-7 items-center justify-center rounded-full border border-zinc-200/80 bg-white dark:border-zinc-800 dark:bg-zinc-900">
                        <Bot className="h-4 w-4 text-zinc-500 dark:text-zinc-400" />
                      </div>
                    ) : (
                      <img
                        src="/static/image/aiida-icon.svg"
                        alt="AiiDA"
                        className="mt-0.5 h-7 w-7 rounded-full border border-zinc-200/80 bg-white object-contain p-1 dark:border-zinc-800 dark:bg-zinc-900"
                        onError={() => setAvatarFailed(true)}
                      />
                    )}

                    <div className="min-w-0 max-w-[86%] space-y-2">
                      {showThinking ? (
                        <ThinkingIndicator
                          currentStep={turnCurrentStep || null}
                          processLog={processLog}
                          fallbackText="Thinking..."
                        />
                      ) : null}

                      {showAssistant ? (
                        <div
                          className={cn(
                            "group relative rounded-2xl border bg-zinc-50/80 px-4 py-3 text-sm leading-6 text-zinc-800 transition-colors duration-200 dark:bg-zinc-900/60 dark:text-zinc-100",
                            turn.assistantStatus === "error"
                              ? "border-rose-200/80 dark:border-rose-800/60"
                              : "border-zinc-200/80 dark:border-zinc-800",
                          )}
                        >
                          {processLog.length > 0 ? (
                            <ul className="mb-2 space-y-1 rounded-lg border border-zinc-200/80 bg-zinc-100/75 px-2.5 py-2 text-[11px] text-zinc-600 dark:border-zinc-700 dark:bg-zinc-900/75 dark:text-zinc-300">
                              {processLog.map((entry, index) => {
                                const isLatest = index === processLog.length - 1;
                                return (
                                  <li
                                    key={`${turn.turnId}-tool-${entry.id}`}
                                    className={cn(
                                      "flex items-center justify-between gap-2 truncate rounded px-1.5 py-0.5",
                                      isLatest && "bg-white/70 font-medium text-slate-700 dark:bg-zinc-800/70 dark:text-slate-100",
                                    )}
                                  >
                                    <span className="truncate">{entry.friendlyStep}</span>
                                    <span className="shrink-0 font-mono text-[10px] opacity-80">{entry.toolName}</span>
                                  </li>
                                );
                              })}
                            </ul>
                          ) : null}
                          {visibleAssistantText.trim() ? (
                            <p className="whitespace-pre-wrap">
                              {renderTextWithSmartCitations(
                                visibleAssistantText,
                                onOpenDetail,
                                nodeHoverMetadataByPk,
                                ensureNodeHoverMetadata,
                              )}
                            </p>
                          ) : null}
                          {turn.assistantStatus === "error" ? (
                            <p className="mt-2 text-xs text-rose-500">Response ended with error.</p>
                          ) : null}
                          {submissionDraft ? (
                            <SubmissionModal
                              open
                              mode="inline"
                              expanded={isSubmissionExpanded}
                              onToggleExpanded={() =>
                                setExpandedSubmissionByTurn((current) => ({
                                  ...current,
                                  [turn.turnId]: !isSubmissionExpanded,
                                }))
                              }
                              turnId={turn.turnId}
                              submissionDraft={submissionDraft.submissionDraft}
                              state={previewState}
                              isBusy={isLoading}
                              onClose={() => {}}
                              onConfirm={(draftPayload) => {
                                void handleConfirmPreview(turn.turnId, submissionDraft, draftPayload);
                              }}
                              onCancel={() => {
                                void handleCancelPreview(turn.turnId);
                              }}
                              onOpenDetail={onOpenDetail}
                            />
                          ) : null}
                          <div className="pointer-events-none absolute -top-2 right-2 flex items-center gap-1 rounded-md border border-zinc-200/80 bg-white/95 px-1.5 py-1 opacity-0 shadow-sm transition-opacity duration-150 group-hover:pointer-events-auto group-hover:opacity-100 dark:border-zinc-700 dark:bg-zinc-950/95">
                            <button
                              type="button"
                              className="inline-flex h-6 w-6 items-center justify-center rounded text-zinc-500 transition-colors hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
                              onClick={() => void copyTextToClipboard(visibleAssistantText)}
                              aria-label="Copy message"
                            >
                              <Copy className="h-3.5 w-3.5" />
                            </button>
                            <button
                              type="button"
                              className="inline-flex h-6 w-6 items-center justify-center rounded text-zinc-500 transition-colors hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
                              onClick={() => handleReaskMessage(visibleAssistantText, userContextNodes)}
                              aria-label="Re-ask message"
                            >
                              <RotateCcw className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        </div>
                      ) : null}
                    </div>
                  </div>
                ) : null}
                {submittedPreview ? (
                  <div className="ml-10 max-w-[86%] rounded-xl border border-emerald-200/80 bg-emerald-50/85 px-3 py-2 text-sm text-emerald-800 dark:border-emerald-900/50 dark:bg-emerald-950/30 dark:text-emerald-200">
                    <p className="font-medium">
                      🚀 Job Submitted: {submittedPreview.processLabel}{" "}
                      {submittedPreview.processPks.length > 0 ? `(${submittedPreview.processPks.length} jobs)` : "(PK pending)"}
                    </p>
                    {submittedPreview.processPks.length > 0 ? (
                      <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                        {submittedPreview.processPks.slice(0, 6).map((pk) => (
                          <button
                            key={`${turn.turnId}-submitted-mini-${pk}`}
                            type="button"
                            className="rounded-full bg-emerald-100 px-2 py-0.5 font-mono text-xs font-semibold underline underline-offset-2 dark:bg-emerald-900/45"
                            onClick={() => onOpenDetail(pk)}
                          >
                            #{pk}
                          </button>
                        ))}
                        {submittedPreview.processPks.length > 6 ? (
                          <span className="text-xs">+{submittedPreview.processPks.length - 6} more</span>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </article>
            );
          })
        )}
        <div ref={messagesEndRef} className="h-2" aria-hidden />
      </div>

      <div className="bg-white/75 px-4 pb-4 pt-3 backdrop-blur dark:bg-zinc-950/35 md:px-6">
        <div className="pt-2">
          <div className="rounded-2xl border border-zinc-200/80 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-950/70">
            {quickPrompts.length > 0 ? (
              <div className="mb-2 border-b border-zinc-200/70 pb-2 dark:border-zinc-800/80">
                <div className="mb-1 flex items-center justify-between gap-2">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-zinc-500 dark:text-zinc-400">
                    Research Actions
                  </p>
                  <p className="text-[10px] text-zinc-400 dark:text-zinc-500">
                    {hasStructureContext
                      ? `Structure context: ${structureContextPks.map((pk) => `#${pk}`).join(", ")}`
                      : "Select StructureData to enable relax/band workflows"}
                  </p>
                </div>
                <div className="minimal-scrollbar -mx-1 overflow-x-auto px-1">
                  <div className="flex w-max min-w-full gap-2 pb-0.5">
                    {quickPrompts.map((quickPrompt) => {
                      const kind = inferQuickActionKind(quickPrompt.label, quickPrompt.prompt);
                      const needsStructure = quickActionRequiresStructure(kind);
                      const disabled = isLoading || (needsStructure && !hasStructureContext);
                      const highlighted = needsStructure && hasStructureContext;
                      return (
                        <button
                          key={`${quickPrompt.label}-${quickPrompt.prompt}`}
                          type="button"
                          className={cn(
                            "inline-flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors duration-200",
                            highlighted
                              ? "border-sky-300/90 bg-sky-50 text-sky-700 hover:bg-sky-100 dark:border-sky-800/70 dark:bg-sky-950/35 dark:text-sky-200 dark:hover:bg-sky-900/50"
                              : "border-zinc-300/70 bg-zinc-50 text-zinc-700 hover:bg-zinc-100 dark:border-zinc-800 dark:bg-zinc-900/60 dark:text-zinc-300 dark:hover:bg-zinc-800/80",
                            disabled && "cursor-not-allowed opacity-45 hover:bg-inherit dark:hover:bg-inherit",
                          )}
                          onClick={() => handleQuickActionPrompt(quickPrompt.label, quickPrompt.prompt)}
                          disabled={disabled}
                          title={quickPrompt.prompt}
                        >
                          <span aria-hidden>{quickActionIcon(kind)}</span>
                          <span className="whitespace-nowrap">{quickPrompt.label}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            ) : null}
            <textarea
              ref={textareaRef}
              rows={2}
              value={draft}
              placeholder="Message SABR..."
              className={cn(
                "max-h-[220px] min-h-[56px] w-full resize-none rounded-lg border border-transparent bg-transparent text-sm text-zinc-900 outline-none placeholder:text-zinc-400 transition-colors dark:text-zinc-100",
                dragOverZone === "textarea" &&
                  "border-dashed border-sky-400/80 bg-sky-50/45 dark:border-sky-700/80 dark:bg-sky-950/30",
              )}
              disabled={isLoading}
              onChange={(event) => {
                setDraft(event.target.value);
                updateTextareaHeight(event.currentTarget);
              }}
              onDragOver={(event) => {
                event.preventDefault();
                event.dataTransfer.dropEffect = "copy";
                if (dragOverZone !== "textarea") {
                  setDragOverZone("textarea");
                }
              }}
              onDragLeave={() => {
                if (dragOverZone === "textarea") {
                  setDragOverZone(null);
                }
              }}
              onDrop={(event) => {
                event.preventDefault();
                if (isLoading) {
                  return;
                }
                const droppedResource = parseDroppedResourceAttachment(event);
                if (droppedResource) {
                  handleAttachResource(droppedResource);
                  setDragOverZone(null);
                  return;
                }
                const droppedNode = parseDroppedContextNode(event);
                if (!droppedNode) {
                  setDragOverZone(null);
                  return;
                }
                const textarea = event.currentTarget;
                const { value, caret } = insertPkTokenAtSelection(
                  textarea.value,
                  droppedNode.pk,
                  textarea.selectionStart ?? textarea.value.length,
                  textarea.selectionEnd ?? textarea.value.length,
                );
                setDraft(value);
                setDragOverZone(null);
                window.requestAnimationFrame(() => {
                  const target = textareaRef.current;
                  if (!target) {
                    return;
                  }
                  target.setSelectionRange(caret, caret);
                  updateTextareaHeight(target);
                  target.focus();
                });
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
                  event.preventDefault();
                  handleSubmit();
                }
              }}
            />

            <div
              className={cn(
                "minimal-scrollbar mt-2 flex h-7 items-center gap-1 overflow-x-auto rounded-md border border-dashed px-1.5",
                dragOverZone === "attachment"
                  ? "border-sky-400/80 bg-sky-50/70 dark:border-sky-700/80 dark:bg-sky-950/35"
                  : "border-zinc-200/75 bg-zinc-50/60 dark:border-zinc-800/85 dark:bg-zinc-900/45",
              )}
              onDragOver={(event) => {
                event.preventDefault();
                event.dataTransfer.dropEffect = "copy";
                if (dragOverZone !== "attachment") {
                  setDragOverZone("attachment");
                }
              }}
              onDragLeave={() => {
                if (dragOverZone === "attachment") {
                  setDragOverZone(null);
                }
              }}
              onDrop={(event) => {
                event.preventDefault();
                if (isLoading) {
                  setDragOverZone(null);
                  return;
                }
                const droppedResource = parseDroppedResourceAttachment(event);
                if (droppedResource) {
                  handleAttachResource(droppedResource);
                  setDragOverZone(null);
                  return;
                }
                const droppedNode = parseDroppedContextNode(event);
                if (!droppedNode) {
                  setDragOverZone(null);
                  return;
                }
                onAddContextNode(droppedNode);
                setDragOverZone(null);
              }}
            >
              {hasAnyAttachments ? (
                <>
                  {resourceAttachments.map((attachment) => (
                    <span
                      key={`resource-chip-${resourceAttachmentKey(attachment)}`}
                      className="inline-flex h-5 shrink-0 items-center gap-1 rounded-full border border-sky-300/80 bg-sky-50/95 px-1.5 text-[10px] text-sky-700 dark:border-sky-800/70 dark:bg-sky-950/40 dark:text-sky-200"
                      title={attachment.label}
                    >
                      <span aria-hidden>{resourceAttachmentIcon(attachment.kind)}</span>
                      <span className="max-w-[180px] truncate">{attachment.value}</span>
                      <button
                        type="button"
                        className="inline-flex h-3.5 w-3.5 items-center justify-center rounded-full text-sky-600 transition-colors hover:bg-sky-200/90 hover:text-sky-900 dark:text-sky-300 dark:hover:bg-sky-800 dark:hover:text-sky-100"
                        onClick={() => handleRemoveResourceAttachment(attachment)}
                        aria-label={`Remove ${attachment.kind} attachment ${attachment.value}`}
                      >
                        <X className="h-2.5 w-2.5" />
                      </button>
                    </span>
                  ))}
                  {contextNodes.map((node) => (
                    <span
                      key={`context-chip-${node.pk}`}
                      className="inline-flex h-5 shrink-0 items-center gap-1 rounded-full border border-zinc-300/80 bg-white/95 px-1.5 text-[10px] text-zinc-700 dark:border-zinc-700 dark:bg-zinc-900/85 dark:text-zinc-200"
                    >
                      <span aria-hidden>⚛️</span>
                      <span className="font-mono">#{node.pk}</span>
                      <button
                        type="button"
                        className="inline-flex h-3.5 w-3.5 items-center justify-center rounded-full text-zinc-500 transition-colors hover:bg-zinc-200/90 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-700 dark:hover:text-zinc-100"
                        onClick={() => onRemoveContextNode(node.pk)}
                        aria-label={`Remove node ${node.pk} from context`}
                      >
                        <X className="h-2.5 w-2.5" />
                      </button>
                    </span>
                  ))}
                </>
              ) : (
                <p className="truncate text-[10px] text-zinc-500 dark:text-zinc-400">
                  Drop node/resource here to attach context
                </p>
              )}
            </div>

            <div className="mt-3 flex flex-row items-center justify-between gap-2">
              <div className="flex flex-row items-center gap-2">
                <Button
                  variant="outline"
                  size="icon"
                  className="border-zinc-200/80 bg-transparent transition-colors duration-200 hover:bg-zinc-100/70 dark:border-zinc-800 dark:hover:bg-zinc-900/70"
                  onClick={() => fileInputRef.current?.click()}
                  aria-label="Attach file"
                >
                  <Paperclip className="h-4 w-4" />
                </Button>
                <input
                  ref={fileInputRef}
                  type="file"
                  className="hidden"
                  accept=".aiida,.zip"
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) {
                      onAttachFile(file);
                    }
                    event.target.value = "";
                  }}
                />

                <div ref={modelMenuRef} className="relative">
                  <button
                    type="button"
                    className="inline-flex h-9 max-w-[220px] items-center gap-2 rounded-lg border border-zinc-200/70 bg-zinc-50/80 px-3 text-sm text-zinc-700 transition-all duration-200 hover:border-zinc-300 hover:bg-zinc-50 focus:border-zinc-400 focus:outline-none dark:border-zinc-800 dark:bg-zinc-900/50 dark:text-zinc-200 dark:hover:border-zinc-700 dark:hover:bg-zinc-900/65 dark:focus:border-zinc-600"
                    onClick={() => setIsModelMenuOpen((open) => !open)}
                  >
                    <span className="truncate">{selectedModel || "Select model"}</span>
                    <ChevronDown
                      className={cn(
                        "h-4 w-4 shrink-0 transition-transform duration-200",
                        isModelMenuOpen && "rotate-180",
                      )}
                    />
                  </button>

                  {isModelMenuOpen ? (
                    <div className="absolute bottom-full left-0 z-20 mb-2 w-64 overflow-hidden rounded-lg border border-zinc-200/80 bg-zinc-50/95 shadow-lg backdrop-blur dark:border-zinc-800 dark:bg-zinc-900/95">
                      <div className="minimal-scrollbar max-h-60 overflow-y-auto p-1">
                        {models.map((model) => (
                          <button
                            key={model}
                            type="button"
                            className={cn(
                              "flex w-full items-center rounded-md px-2.5 py-2 text-left text-sm transition-colors duration-200",
                              model === selectedModel
                                ? "bg-zinc-200/70 text-zinc-900 dark:bg-zinc-800 dark:text-zinc-100"
                                : "text-zinc-700 hover:bg-zinc-200/50 dark:text-zinc-300 dark:hover:bg-zinc-800/80",
                            )}
                            onClick={() => {
                              onModelChange(model);
                              setIsModelMenuOpen(false);
                            }}
                          >
                            <span className="truncate">{model}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
              </div>

              <Button
                size="icon"
                onClick={() => {
                  if (isLoading) {
                    onStopResponse();
                    return;
                  }
                  handleSubmit();
                }}
                disabled={!isLoading && isDraftEmpty}
                className={cn(
                  "transition-all duration-200",
                  isLoading &&
                    "bg-rose-600 text-white hover:bg-rose-500 dark:bg-rose-500 dark:text-white dark:hover:bg-rose-400",
                )}
                aria-label={isLoading ? "Stop response" : "Send message"}
              >
                {isLoading ? <Square className="h-4 w-4" /> : <SendHorizontal className="h-4 w-4" />}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </Panel>
  );
}
