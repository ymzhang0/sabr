import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  CHAT_STREAM_URL,
  LOGS_STREAM_URL,
  PROCESS_EVENTS_URL,
  activateChatSession,
  addNodesToGroup,
  cancelPendingSubmission,
  createChatProject,
  createChatSession,
  createGroup,
  deleteGroup,
  exportGroup,
  getBootstrap,
  getChatMessages,
  getChatSessionWorkspace,
  getChatSessions,
  getGroups,
  getLogs,
  getProcessCloneDraft,
  getProcesses,
  renameGroup,
  sendChat,
  softDeleteNode,
  stopChat,
  submitPreviewDraft,
  uploadArchive,
  updateChatSession,
} from "@/lib/api";
import { ChatPanel } from "@/components/dashboard/chat-panel";
import { HistorySidebar } from "@/components/dashboard/history-sidebar";
import { ProcessDetailDrawer } from "@/components/dashboard/process-detail-drawer";
import { RuntimeTerminal } from "@/components/dashboard/runtime-terminal";
import { Sidebar } from "@/components/dashboard/sidebar";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  SubmissionModal,
  type SubmissionDraftPayload,
  type SubmissionModalState,
  type SubmissionSubmitDraft,
} from "@/components/dashboard/submission-modal";
import type {
  ChatMessage,
  ChatSessionSnapshot,
  ChatSessionSummary,
  ChatSessionWorkspaceResponse,
  ChatSnapshot,
  FocusNode,
  GroupItem,
  ProcessItem,
  ResourceAttachment,
  SendChatRequest,
  SessionParameter,
} from "@/types/aiida";
import { Database, History, PlusSquare } from "lucide-react";

const THEME_STORAGE_KEY = "sabr.dashboard.theme";
const CURRENT_SESSION_STORAGE_KEY = "current_session_id";
const CHAT_POLL_INTERVAL_MS = 350;

function initialTheme(): "light" | "dark" {
  const saved = window.localStorage.getItem(THEME_STORAGE_KEY);
  return saved === "light" ? "light" : "dark";
}

function readStoredSessionId(): string | null {
  return normalizeSessionId(window.localStorage.getItem(CURRENT_SESSION_STORAGE_KEY));
}

function isAbortError(error: unknown): boolean {
  if (error instanceof DOMException && error.name === "AbortError") {
    return true;
  }
  if (typeof error === "object" && error !== null) {
    const maybeError = error as { name?: string; code?: string };
    return maybeError.name === "AbortError" || maybeError.code === "ERR_CANCELED";
  }
  return false;
}

function isTurnFinalized(messages: ChatMessage[], turnId: number): boolean {
  return messages.some(
    (message, index) =>
      (message.turn_id > 0 ? message.turn_id : index + 1) === turnId &&
      message.role !== "user" &&
      message.status !== "thinking",
  );
}

function scoreChatMessages(messages: ChatMessage[]): number {
  const finalizedCount = messages.reduce((count, message) => {
    if (message.role === "user") {
      return count;
    }
    return count + (message.status !== "thinking" ? 1 : 0);
  }, 0);
  const totalChars = messages.reduce((count, message) => count + (message.text?.length ?? 0), 0);
  return finalizedCount * 1_000_000 + messages.length * 10_000 + totalChars;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function normalizeTurnId(message: ChatMessage, index: number): number {
  return message.turn_id > 0 ? message.turn_id : index + 1;
}

function normalizeSessionId(sessionId: string | null | undefined): string | null {
  const cleaned = String(sessionId || "").trim();
  return cleaned || null;
}

function dedupeFocusNodes(nodes: FocusNode[]): FocusNode[] {
  const seen = new Set<number>();
  return nodes.filter((node) => {
    if (!node || !Number.isInteger(node.pk) || node.pk <= 0 || seen.has(node.pk)) {
      return false;
    }
    seen.add(node.pk);
    return true;
  });
}

function normalizeSessionParameters(raw: unknown): SessionParameter[] {
  if (!Array.isArray(raw)) {
    return [];
  }
  const seen = new Set<string>();
  return raw
    .map((entry) => {
      const record = asRecord(entry);
      if (!record) {
        return null;
      }
      const key = typeof record.key === "string" ? record.key.trim() : "";
      const value = typeof record.value === "string" ? record.value.trim() : "";
      if (!key || !value) {
        return null;
      }
      const normalizedKey = key.toLowerCase();
      if (seen.has(normalizedKey)) {
        return null;
      }
      seen.add(normalizedKey);
      return { key, value };
    })
    .filter((entry): entry is SessionParameter => Boolean(entry));
}

function normalizeChatSessionSnapshot(snapshot: ChatSessionSnapshot | null | undefined): ChatSessionSnapshot {
  const contextNodes = Array.isArray(snapshot?.context_nodes)
    ? dedupeFocusNodes(
        snapshot.context_nodes.map((node) => ({
          pk: Number(node.pk),
          label: String(node.label || `#${node.pk}`),
          formula: node.formula ?? null,
          node_type: String(node.node_type || "Unknown"),
        })),
      )
    : [];
  const pinnedNodes = Array.isArray(snapshot?.pinned_nodes)
    ? dedupeFocusNodes(
        snapshot.pinned_nodes.map((node) => ({
          pk: Number(node.pk),
          label: String(node.label || `#${node.pk}`),
          formula: node.formula ?? null,
          node_type: String(node.node_type || "Unknown"),
        })),
      )
    : [];
  const selectedGroup =
    typeof snapshot?.selected_group === "string" && snapshot.selected_group.trim()
      ? snapshot.selected_group.trim()
      : null;
  const selectedModel =
    typeof snapshot?.selected_model === "string" && snapshot.selected_model.trim()
      ? snapshot.selected_model.trim()
      : null;
  const sessionEnvironment =
    typeof snapshot?.session_environment === "string" && snapshot.session_environment.trim()
      ? snapshot.session_environment.trim().toLowerCase()
      : null;
  const promptOverride =
    typeof snapshot?.prompt_override === "string" && snapshot.prompt_override.trim()
      ? snapshot.prompt_override.trim()
      : null;
  return {
    context_nodes: contextNodes,
    pinned_nodes: pinnedNodes,
    selected_group: selectedGroup,
    selected_model: selectedModel,
    session_environment: sessionEnvironment,
    session_environment_auto: snapshot?.session_environment_auto !== false,
    prompt_override: promptOverride,
    session_parameters: normalizeSessionParameters(snapshot?.session_parameters),
  };
}

function buildChatSessionSnapshotPayload(params: {
  contextNodes: FocusNode[];
  pinnedNodes: FocusNode[];
  selectedGroup: string;
  selectedModel: string;
  sessionEnvironment: string | null;
  sessionEnvironmentAuto: boolean;
  promptOverride: string;
  sessionParameters: SessionParameter[];
}): Record<string, unknown> {
  return {
    context_nodes: dedupeFocusNodes(params.contextNodes).map((node) => ({
      pk: node.pk,
      label: node.label,
      formula: node.formula,
      node_type: node.node_type,
    })),
    pinned_nodes: dedupeFocusNodes(params.pinnedNodes).map((node) => ({
      pk: node.pk,
      label: node.label,
      formula: node.formula,
      node_type: node.node_type,
    })),
    selected_group: params.selectedGroup.trim() || null,
    selected_model: params.selectedModel.trim() || null,
    session_environment: params.sessionEnvironment?.trim().toLowerCase() || null,
    session_environment_auto: params.sessionEnvironmentAuto,
    prompt_override: params.promptOverride.trim() || null,
    session_parameters: normalizeSessionParameters(params.sessionParameters),
  };
}

type MergeIndexedMessage = {
  key: string;
  message: ChatMessage;
};

function buildMergeIndexedMessages(messages: ChatMessage[]): MergeIndexedMessage[] {
  const counters = new Map<string, number>();
  return messages.map((message, index) => {
    const mergeBase = `${normalizeTurnId(message, index)}|${message.role}`;
    const occurrence = counters.get(mergeBase) ?? 0;
    counters.set(mergeBase, occurrence + 1);
    return {
      key: `${mergeBase}|${occurrence}`,
      message,
    };
  });
}

function isToolStatusText(text: string): boolean {
  const lines = text
    .split(/\r?\n/g)
    .map((line) => line.trim())
    .filter(Boolean);
  if (lines.length === 0) {
    return false;
  }
  return lines.every((line) =>
    /^(thinking:|running:|step:|\u2699\uFE0F\s*\[step\]\s*:)/i.test(line),
  );
}

function hasActiveAiidaAgentStep(
  messages: ChatMessage[],
  activeTurnId: number | null,
  isChatLoading: boolean,
): boolean {
  if (!isChatLoading || messages.length === 0) {
    return false;
  }

  const fallbackTurnId = messages.reduce<number | null>((latest, message, index) => {
    if (message.role !== "assistant" || message.status !== "thinking") {
      return latest;
    }
    return normalizeTurnId(message, index);
  }, null);
  const targetTurnId = activeTurnId ?? fallbackTurnId;
  if (targetTurnId === null) {
    return false;
  }

  return messages.some((message, index) => {
    if (message.role !== "assistant" || message.status !== "thinking") {
      return false;
    }
    if (normalizeTurnId(message, index) !== targetTurnId) {
      return false;
    }

    const payload = asRecord(message.payload);
    const payloadStatus = asRecord(payload?.status);
    const toolCalls = Array.isArray(payload?.tool_calls)
      ? payload.tool_calls.map((entry) => String(entry ?? "").trim()).filter(Boolean)
      : [];
    const statusSteps = Array.isArray(payloadStatus?.steps)
      ? payloadStatus.steps.map((entry) => String(entry ?? "").trim()).filter(Boolean)
      : [];
    const currentStep =
      typeof payloadStatus?.current_step === "string" ? payloadStatus.current_step.trim() : "";
    const text = String(message.text ?? "").trim();

    return (
      toolCalls.some((entry) => entry.toLowerCase().includes("aiida.agent.step")) ||
      statusSteps.length > 0 ||
      Boolean(currentStep) ||
      /^(thinking:|running:|step:|\u2699\uFE0F\s*\[step\]\s*:)/i.test(text)
    );
  });
}

function extractToolCalls(payload: Record<string, unknown> | null): string[] {
  if (!payload || !Array.isArray(payload.tool_calls)) {
    return [];
  }
  return payload.tool_calls
    .map((value) => String(value ?? "").trim())
    .filter(Boolean);
}

function mergeToolCalls(previousCalls: string[], incomingCalls: string[]): string[] {
  if (previousCalls.length === 0) {
    return incomingCalls;
  }
  if (incomingCalls.length === 0) {
    return previousCalls;
  }
  const merged: string[] = [];
  const seen = new Set<string>();
  [...previousCalls, ...incomingCalls].forEach((call) => {
    if (seen.has(call)) {
      return;
    }
    seen.add(call);
    merged.push(call);
  });
  return merged;
}

function mergeMessagePayload(
  previousPayload: Record<string, unknown> | null | undefined,
  incomingPayload: Record<string, unknown> | null | undefined,
): Record<string, unknown> | null | undefined {
  const previousRecord = asRecord(previousPayload);
  const incomingRecord = asRecord(incomingPayload);

  if (!previousRecord && !incomingRecord) {
    return incomingPayload ?? previousPayload;
  }
  if (!previousRecord) {
    return incomingRecord;
  }
  if (!incomingRecord) {
    return previousRecord;
  }

  const merged = { ...previousRecord, ...incomingRecord };
  const mergedToolCalls = mergeToolCalls(
    extractToolCalls(previousRecord),
    extractToolCalls(incomingRecord),
  );
  if (mergedToolCalls.length > 0) {
    merged.tool_calls = mergedToolCalls;
  }
  return merged;
}

function mergeMessageText(previous: ChatMessage, incoming: ChatMessage): string {
  const previousText = typeof previous.text === "string" ? previous.text : "";
  const incomingText = typeof incoming.text === "string" ? incoming.text : "";
  const previousTrimmed = previousText.trim();
  const incomingTrimmed = incomingText.trim();

  if (!incomingTrimmed && previousTrimmed) {
    return previousText;
  }

  const incomingLooksLikeToolStatus = isToolStatusText(incomingText);
  const previousLooksLikeToolStatus = isToolStatusText(previousText);
  if (incoming.status === "thinking" && previousTrimmed) {
    if (!previousLooksLikeToolStatus && (incomingLooksLikeToolStatus || !incomingTrimmed)) {
      return previousText;
    }
    if (previousLooksLikeToolStatus && incomingLooksLikeToolStatus && previousText.length > incomingText.length) {
      return previousText;
    }
    if (!previousLooksLikeToolStatus && incomingTrimmed.length <= previousTrimmed.length) {
      return previousText;
    }
  }

  if (incomingLooksLikeToolStatus && previousTrimmed && !previousLooksLikeToolStatus) {
    return previousText;
  }

  if (incoming.status !== "thinking" && !incomingTrimmed && previousTrimmed) {
    return previousText;
  }

  return incomingText;
}

function mergeChatMessages(previous: ChatMessage[], incoming: ChatMessage[]): ChatMessage[] {
  const previousByKey = new Map<string, ChatMessage[]>();
  buildMergeIndexedMessages(previous).forEach(({ key, message }) => {
    const bucket = previousByKey.get(key) ?? [];
    bucket.push(message);
    previousByKey.set(key, bucket);
  });

  return buildMergeIndexedMessages(incoming).map(({ key, message: incomingMessage }) => {
    const bucket = previousByKey.get(key);
    const previousMessage = bucket?.shift();
    if (!previousMessage) {
      return incomingMessage;
    }

    const mergedText = mergeMessageText(previousMessage, incomingMessage);
    const mergedPayload = mergeMessagePayload(previousMessage.payload, incomingMessage.payload);
    const preserveDoneStatus =
      previousMessage.status !== "thinking" &&
      incomingMessage.status === "thinking" &&
      mergedText.trim().length > 0 &&
      mergedText === previousMessage.text;
    const mergedMessage: ChatMessage = {
      ...incomingMessage,
      text: mergedText,
      status: preserveDoneStatus ? previousMessage.status : incomingMessage.status,
    };
    if (mergedPayload !== undefined) {
      mergedMessage.payload = mergedPayload;
    }
    return mergedMessage;
  });
}

function extractPkReferences(text: string): number[] {
  const seen = new Set<number>();
  const matches = text.matchAll(/#\s*(\d+)\b/g);
  for (const match of matches) {
    const raw = match[1];
    if (!raw) {
      continue;
    }
    const parsed = Number.parseInt(raw, 10);
    if (!Number.isFinite(parsed) || parsed <= 0 || seen.has(parsed)) {
      continue;
    }
    seen.add(parsed);
  }
  return [...seen];
}

function mergeUniquePks(...sources: number[][]): number[] {
  const merged: number[] = [];
  const seen = new Set<number>();
  sources.flat().forEach((pk) => {
    if (!Number.isFinite(pk) || pk <= 0 || seen.has(pk)) {
      return;
    }
    seen.add(pk);
    merged.push(pk);
  });
  return merged;
}

function normalizeGroups(raw: unknown): GroupItem[] {
  if (!Array.isArray(raw)) {
    return [];
  }
  const seen = new Set<number>();
  const groups: GroupItem[] = [];
  raw.forEach((entry) => {
    if (!entry || typeof entry !== "object") {
      return;
    }
    const item = entry as Record<string, unknown>;
    const label = String(item.label ?? "").trim();
    const pk = Number.parseInt(String(item.pk ?? ""), 10);
    const count = Number.parseInt(String(item.count ?? 0), 10);
    if (!label || Number.isNaN(pk) || pk <= 0 || seen.has(pk)) {
      return;
    }
    seen.add(pk);
    groups.push({
      pk,
      label,
      count: Number.isNaN(count) || count < 0 ? 0 : count,
      type_string:
        typeof item.type_string === "string" && item.type_string.trim() ? item.type_string.trim() : null,
    });
  });
  return groups;
}

export default function App() {
  const queryClient = useQueryClient();
  const [theme, setTheme] = useState<"light" | "dark">(initialTheme);
  const [sidebarView, setSidebarView] = useState<"explorer" | "history">("explorer");
  const [selectedModel, setSelectedModel] = useState("");
  const [selectedGroup, setSelectedGroup] = useState("");
  const [nodeTypeFilter, setNodeTypeFilter] = useState<"all" | "structures" | "tasks" | "failed">("all");
  const [processLimit, setProcessLimit] = useState(15);
  const [pendingProcessLimit, setPendingProcessLimit] = useState<number | null>(null);
  const [contextNodes, setContextNodes] = useState<FocusNode[]>([]);
  const [pinnedNodes, setPinnedNodes] = useState<FocusNode[]>([]);
  const [sessionEnvironment, setSessionEnvironment] = useState<string | null>(null);
  const [sessionEnvironmentAuto, setSessionEnvironmentAuto] = useState(true);
  const [promptOverride, setPromptOverride] = useState("");
  const [sessionParameters, setSessionParameters] = useState<SessionParameter[]>([]);
  const [activeProcess, setActiveProcess] = useState<ProcessItem | null>(null);
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [activeTurnId, setActiveTurnId] = useState<number | null>(null);
  const [activeChatSessionId, setActiveChatSessionId] = useState<string | null>(null);
  const [composerResetVersion, setComposerResetVersion] = useState(0);
  const [streamedLogs, setStreamedLogs] = useState<{ version: number; lines: string[] } | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [activeWorkspace, setActiveWorkspace] = useState<ChatSessionWorkspaceResponse | null>(null);
  const [cloneDraft, setCloneDraft] = useState<SubmissionDraftPayload | null>(null);
  const [cloneTurnId, setCloneTurnId] = useState<number | null>(null);
  const [cloneModalState, setCloneModalState] = useState<SubmissionModalState>({ status: "idle" });
  const [isCloneDraftLoading, setIsCloneDraftLoading] = useState(false);
  const sendAbortControllerRef = useRef<AbortController | null>(null);
  const requestInFlightRef = useRef(false);
  const chatVersionRef = useRef(-1);
  const activeChatSessionRef = useRef<string | null>(null);
  const lastPersistedSnapshotRef = useRef<string>("");
  const hasAttemptedSessionRestoreRef = useRef(false);
  const restoringSessionIdRef = useRef<string | null>(null);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  const bootstrapQuery = useQuery({
    queryKey: ["bootstrap"],
    queryFn: getBootstrap,
    refetchOnWindowFocus: false,
  });

  const processesQuery = useQuery({
    queryKey: ["processes", selectedGroup, processLimit, nodeTypeFilter],
    queryFn: () => {
      let nodeType: string | undefined;
      if (nodeTypeFilter === "tasks" || nodeTypeFilter === "failed") nodeType = "ProcessNode";
      if (nodeTypeFilter === "structures") nodeType = "StructureData";
      return getProcesses(processLimit, selectedGroup || undefined, nodeType);
    },
    enabled: bootstrapQuery.isSuccess,
    refetchInterval: 3_000,
  });

  const groupsQuery = useQuery({
    queryKey: ["groups"],
    queryFn: getGroups,
    enabled: bootstrapQuery.isSuccess,
    refetchInterval: 20_000,
  });

  const logsQuery = useQuery({
    queryKey: ["logs"],
    queryFn: () => getLogs(260),
    enabled: bootstrapQuery.isSuccess,
    refetchInterval: 1_500,
  });

  const chatQuery = useQuery({
    queryKey: ["chat"],
    queryFn: getChatMessages,
    enabled: bootstrapQuery.isSuccess,
    refetchInterval: isChatLoading ? CHAT_POLL_INTERVAL_MS : 900,
  });

  const chatSessionsQuery = useQuery({
    queryKey: ["chat-sessions"],
    queryFn: getChatSessions,
    enabled: bootstrapQuery.isSuccess,
    refetchOnWindowFocus: false,
    refetchInterval: isChatLoading ? 1_500 : 5_000,
  });

  const defaultSelectedModel = bootstrapQuery.data?.selected_model ?? bootstrapQuery.data?.models?.[0] ?? "";

  const applyChatSnapshot = useCallback((snapshot: ChatSnapshot | null | undefined) => {
    if (!snapshot || !Array.isArray(snapshot.messages)) {
      return;
    }

    const incomingSessionId = normalizeSessionId(snapshot.session_id);
    const isSessionChanged = incomingSessionId !== activeChatSessionRef.current;
    const incomingVersion = Number.isFinite(snapshot.version) ? snapshot.version : -1;
    const normalizedSnapshot = normalizeChatSessionSnapshot(snapshot.snapshot);

    setActiveChatSessionId(incomingSessionId);
    if (isSessionChanged) {
      activeChatSessionRef.current = incomingSessionId;
      chatVersionRef.current = incomingVersion;
      setMessages(snapshot.messages);
      setContextNodes(normalizedSnapshot.context_nodes);
      setPinnedNodes(normalizedSnapshot.pinned_nodes);
      setSelectedGroup(normalizedSnapshot.selected_group ?? "");
      setSelectedModel(normalizedSnapshot.selected_model ?? defaultSelectedModel);
      setSessionEnvironment(normalizedSnapshot.session_environment);
      setSessionEnvironmentAuto(normalizedSnapshot.session_environment_auto);
      setPromptOverride(normalizedSnapshot.prompt_override ?? "");
      setSessionParameters(normalizedSnapshot.session_parameters);
      lastPersistedSnapshotRef.current = JSON.stringify(normalizedSnapshot);
      return;
    }

    setMessages((previous) => {
      const currentVersion = chatVersionRef.current;
      if (incomingVersion < currentVersion) {
        return previous;
      }
      const mergedMessages = mergeChatMessages(previous, snapshot.messages);
      if (incomingVersion === currentVersion) {
        const nextScore = scoreChatMessages(mergedMessages);
        const prevScore = scoreChatMessages(previous);
        if (nextScore < prevScore) {
          return previous;
        }
      }

      chatVersionRef.current = incomingVersion;
      return mergedMessages;
    });
  }, [defaultSelectedModel]);

  useEffect(() => {
    if (!bootstrapQuery.isSuccess) {
      return;
    }

    const source = new EventSource(LOGS_STREAM_URL);

    const applySnapshot = (payload: string) => {
      try {
        const parsed = JSON.parse(payload) as { version?: number; lines?: string[] };
        if (Array.isArray(parsed.lines)) {
          setStreamedLogs({
            version: Number.isFinite(parsed.version) ? Number(parsed.version) : -1,
            lines: parsed.lines,
          });
        }
      } catch (error) {
        console.error("Failed to parse runtime log stream payload", error);
      }
    };

    source.addEventListener("logs", (event) => {
      applySnapshot((event as MessageEvent<string>).data);
    });
    source.onmessage = (event) => {
      applySnapshot(event.data);
    };

    return () => {
      source.close();
    };
  }, [bootstrapQuery.isSuccess]);

  useEffect(() => {
    if (!bootstrapQuery.data?.chat) {
      return;
    }
    applyChatSnapshot(bootstrapQuery.data.chat);
  }, [applyChatSnapshot, bootstrapQuery.data?.chat]);

  useEffect(() => {
    if (!chatQuery.data) {
      return;
    }
    applyChatSnapshot(chatQuery.data);
  }, [applyChatSnapshot, chatQuery.data]);

  useEffect(() => {
    if (!bootstrapQuery.isSuccess) {
      return;
    }

    const source = new EventSource(CHAT_STREAM_URL);
    const applySnapshot = (payload: string) => {
      try {
        const parsed = JSON.parse(payload) as ChatSnapshot;
        applyChatSnapshot(parsed);
      } catch (error) {
        console.error("Failed to parse chat stream payload", error);
      }
    };

    source.addEventListener("chat", (event) => {
      applySnapshot((event as MessageEvent<string>).data);
    });
    source.onmessage = (event) => {
      applySnapshot(event.data);
    };

    return () => {
      source.close();
    };
  }, [applyChatSnapshot, bootstrapQuery.isSuccess]);

  // \u2500\u2500 SSE: Real-time process state changes \u2500\u2500
  useEffect(() => {
    if (!bootstrapQuery.isSuccess) {
      return;
    }

    const source = new EventSource(PROCESS_EVENTS_URL);

    source.addEventListener("process_state_change", () => {
      queryClient.invalidateQueries({ queryKey: ["processes"] });
    });
    source.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.event === "process_state_change" || data.pk) {
          queryClient.invalidateQueries({ queryKey: ["processes"] });
        }
      } catch {
        // ignore unparseable keepalive messages
      }
    };

    return () => {
      source.close();
    };
  }, [bootstrapQuery.isSuccess, queryClient]);

  useEffect(() => {
    if (selectedModel) {
      return;
    }
    const fallback = bootstrapQuery.data?.selected_model ?? bootstrapQuery.data?.models?.[0] ?? "";
    if (fallback) {
      setSelectedModel(fallback);
    }
  }, [bootstrapQuery.data, selectedModel]);

  useEffect(() => {
    if (!bootstrapQuery.isSuccess) {
      return;
    }
    const sessionId = normalizeSessionId(activeChatSessionId);
    if (sessionId) {
      window.localStorage.setItem(CURRENT_SESSION_STORAGE_KEY, sessionId);
      return;
    }
    if (!hasAttemptedSessionRestoreRef.current) {
      return;
    }
    window.localStorage.removeItem(CURRENT_SESSION_STORAGE_KEY);
  }, [activeChatSessionId, bootstrapQuery.isSuccess]);

  useEffect(() => {
    if (!bootstrapQuery.isSuccess || !chatSessionsQuery.isSuccess || hasAttemptedSessionRestoreRef.current) {
      return;
    }

    const storedSessionId = readStoredSessionId();
    if (!storedSessionId) {
      hasAttemptedSessionRestoreRef.current = true;
      return;
    }

    const matchingSession = chatSessionsQuery.data.items.find((session) => session.id === storedSessionId);
    if (!matchingSession) {
      window.localStorage.removeItem(CURRENT_SESSION_STORAGE_KEY);
      hasAttemptedSessionRestoreRef.current = true;
      return;
    }

    const backendActiveSessionId = normalizeSessionId(chatSessionsQuery.data.active_session_id);
    if (storedSessionId === backendActiveSessionId || storedSessionId === activeChatSessionId) {
      hasAttemptedSessionRestoreRef.current = true;
      return;
    }
    if (restoringSessionIdRef.current === storedSessionId) {
      return;
    }

    restoringSessionIdRef.current = storedSessionId;
    void (async () => {
      try {
        const response = await activateChatSession(storedSessionId);
        applyChatSnapshot(response.chat);
        setComposerResetVersion((current) => current + 1);
        await queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
        await queryClient.invalidateQueries({ queryKey: ["chat"] });
      } catch (error) {
        console.error("Failed to restore stored chat session", error);
        window.localStorage.removeItem(CURRENT_SESSION_STORAGE_KEY);
      } finally {
        hasAttemptedSessionRestoreRef.current = true;
        restoringSessionIdRef.current = null;
      }
    })();
  }, [
    activeChatSessionId,
    applyChatSnapshot,
    bootstrapQuery.isSuccess,
    chatSessionsQuery.data,
    chatSessionsQuery.isSuccess,
    queryClient,
  ]);

  const uploadMutation = useMutation({
    mutationFn: uploadArchive,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["groups"] });
      queryClient.invalidateQueries({ queryKey: ["processes"] });
    },
  });

  const createProjectMutation = useMutation({
    mutationFn: ({ name, rootPath }: { name: string; rootPath: string }) =>
      createChatProject({
        name,
        root_path: rootPath.trim() || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
    },
  });

  const openWorkspaceMutation = useMutation({
    mutationFn: ({ sessionId, relativePath }: { sessionId: string; relativePath?: string }) =>
      getChatSessionWorkspace(sessionId, relativePath),
    onSuccess: (workspace) => {
      setActiveWorkspace(workspace);
    },
  });

  const createGroupMutation = useMutation({
    mutationFn: (label: string) => createGroup(label),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["groups"] });
    },
  });

  const renameGroupMutation = useMutation({
    mutationFn: ({ pk, label }: { pk: number; label: string }) => renameGroup(pk, label),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["groups"] });
    },
  });

  const deleteGroupMutation = useMutation({
    mutationFn: (pk: number) => deleteGroup(pk),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["groups"] });
      queryClient.invalidateQueries({ queryKey: ["processes"] });
    },
  });

  const addNodesToGroupMutation = useMutation({
    mutationFn: ({ groupPk, nodePks }: { groupPk: number; nodePks: number[] }) => addNodesToGroup(groupPk, nodePks),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["groups"] });
      queryClient.invalidateQueries({ queryKey: ["processes"] });
    },
  });

  const softDeleteNodeMutation = useMutation({
    mutationFn: (pk: number) => softDeleteNode(pk, true),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["processes"] });
      queryClient.invalidateQueries({ queryKey: ["groups"] });
    },
  });

  const processes = processesQuery.data?.items ?? bootstrapQuery.data?.processes ?? [];
  const groups = normalizeGroups(groupsQuery.data?.items ?? bootstrapQuery.data?.groups ?? []);
  const polledLogsVersion = logsQuery.data?.version ?? bootstrapQuery.data?.logs.version ?? -1;
  const polledLogs = logsQuery.data?.lines ?? bootstrapQuery.data?.logs.lines ?? [];
  const logs =
    streamedLogs && streamedLogs.version >= polledLogsVersion
      ? streamedLogs.lines
      : polledLogs;
  const chatMessages = messages;
  const models = bootstrapQuery.data?.models ?? [];
  const isReady = bootstrapQuery.isSuccess;
  const contextNodeIds = useMemo(() => contextNodes.map((node) => node.pk), [contextNodes]);
  const isChatBusy = isChatLoading;
  const hasPendingAgentStep = useMemo(
    () => hasActiveAiidaAgentStep(chatMessages, activeTurnId, isChatBusy),
    [activeTurnId, chatMessages, isChatBusy],
  );
  const chatSessions = chatSessionsQuery.data?.items ?? [];
  const chatProjects = chatSessionsQuery.data?.projects ?? [];
  const activeProjectId = chatSessionsQuery.data?.active_project_id ?? null;
  const activeChatSession = useMemo(
    () => chatSessions.find((session) => session.id === activeChatSessionId) ?? null,
    [activeChatSessionId, chatSessions],
  );

  useEffect(() => {
    setActiveWorkspace((current) => (current?.session_id === activeChatSessionId ? current : null));
  }, [activeChatSessionId]);
  const sessionSnapshotPayload = useMemo(
    () =>
      buildChatSessionSnapshotPayload({
        contextNodes,
        pinnedNodes,
        selectedGroup,
        selectedModel,
        sessionEnvironment,
        sessionEnvironmentAuto,
        promptOverride,
        sessionParameters,
      }),
    [
      contextNodes,
      pinnedNodes,
      promptOverride,
      selectedGroup,
      selectedModel,
      sessionEnvironment,
      sessionEnvironmentAuto,
      sessionParameters,
    ],
  );
  const sessionSnapshotSignature = useMemo(
    () => JSON.stringify(sessionSnapshotPayload),
    [sessionSnapshotPayload],
  );

  useEffect(() => {
    if (!bootstrapQuery.isSuccess || !activeChatSessionId) {
      return;
    }
    if (sessionSnapshotSignature === lastPersistedSnapshotRef.current) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      lastPersistedSnapshotRef.current = sessionSnapshotSignature;
      void updateChatSession(activeChatSessionId, { snapshot: sessionSnapshotPayload }).catch((error) => {
        console.error("Failed to persist chat session snapshot", error);
        lastPersistedSnapshotRef.current = "";
      });
    }, 220);

    return () => window.clearTimeout(timeoutId);
  }, [activeChatSessionId, bootstrapQuery.isSuccess, sessionSnapshotPayload, sessionSnapshotSignature]);

  const appendContextNode = useCallback((node: FocusNode) => {
    setContextNodes((current) => {
      if (current.some((existing) => existing.pk === node.pk)) {
        return current;
      }
      return [...current, node];
    });
  }, []);

  const handleAddContextNode = useCallback((process: ProcessItem) => {
    appendContextNode({
      pk: process.pk,
      label: process.label,
      formula: process.formula ?? null,
      node_type: process.node_type,
    });
  }, [appendContextNode]);

  const handleRemoveContextNode = useCallback((pk: number) => {
    setContextNodes((current) => current.filter((node) => node.pk !== pk));
  }, []);

  const handleRestoreContextNodes = useCallback((nodes: FocusNode[]) => {
    setContextNodes(dedupeFocusNodes(nodes));
  }, []);

  const handlePinNode = useCallback((node: FocusNode) => {
    setPinnedNodes((current) => dedupeFocusNodes([...current, node]));
  }, []);

  const handleUnpinNode = useCallback((pk: number) => {
    setPinnedNodes((current) => current.filter((node) => node.pk !== pk));
  }, []);

  const stopActiveChatTurn = useCallback(async () => {
    if (!isChatBusy) {
      return;
    }

    sendAbortControllerRef.current?.abort();
    sendAbortControllerRef.current = null;
    requestInFlightRef.current = false;
    setIsChatLoading(false);
    const turnIdToStop = activeTurnId;
    setActiveTurnId(null);

    try {
      await stopChat(turnIdToStop ?? undefined);
    } catch (error) {
      if (!isAbortError(error)) {
        console.error("Failed to stop chat request", error);
      }
    } finally {
      await queryClient.invalidateQueries({ queryKey: ["chat"] });
      await queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
    }
  }, [activeTurnId, isChatBusy, queryClient]);

  const handleCreateChatSession = useCallback(async (projectId?: string) => {
    if (hasPendingAgentStep) {
      const confirmed = window.confirm(
        "An AiiDA agent step is still running. Starting a new conversation will stop it, archive the current session, and open a fresh one. Continue?",
      );
      if (!confirmed) {
        return;
      }
    }

    if (isChatBusy) {
      await stopActiveChatTurn();
    }

    window.localStorage.removeItem(CURRENT_SESSION_STORAGE_KEY);
    const response = await createChatSession({
      archive_session_id: activeChatSessionId ?? undefined,
      project_id: projectId,
    });
    applyChatSnapshot(response.chat);
    setActiveWorkspace(null);
    setComposerResetVersion((current) => current + 1);
    setSidebarView("explorer");
    await queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
    await queryClient.invalidateQueries({ queryKey: ["chat"] });
  }, [activeChatSessionId, applyChatSnapshot, hasPendingAgentStep, isChatBusy, queryClient, stopActiveChatTurn]);

  const handleActivateChatSession = useCallback(
    async (sessionId: string) => {
      if (isChatBusy || !sessionId || sessionId === activeChatSessionId) {
        return;
      }
      const response = await activateChatSession(sessionId);
      applyChatSnapshot(response.chat);
      setComposerResetVersion((current) => current + 1);
      await queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
      await queryClient.invalidateQueries({ queryKey: ["chat"] });
    },
    [activeChatSessionId, applyChatSnapshot, isChatBusy, queryClient],
  );

  const handleUpdateChatSessionTags = useCallback(
    async (sessionId: string, tags: string[]) => {
      if (!sessionId) {
        return;
      }
      const response = await updateChatSession(sessionId, { tags });
      applyChatSnapshot(response.chat);
      await queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
    },
    [applyChatSnapshot, queryClient],
  );

  const handleCreateProject = useCallback(
    async ({ name, rootPath }: { name: string; rootPath: string }) => {
      const response = await createProjectMutation.mutateAsync({ name, rootPath });
      await handleCreateChatSession(response.project.id);
      setSidebarView("history");
    },
    [createProjectMutation, handleCreateChatSession],
  );

  const handleOpenWorkspace = useCallback(
    async (sessionId: string) => {
      if (!sessionId) {
        return;
      }
      try {
        await openWorkspaceMutation.mutateAsync({ sessionId });
      } catch (error) {
        console.error("Failed to open workspace", error);
      }
    },
    [openWorkspaceMutation],
  );

  const handleOpenDetail = useCallback((pk: number) => {
    setActiveProcess({
      pk,
      label: `Process #${pk}`,
      state: "submitted",
      status_color: "running",
      node_type: "ProcessNode",
      process_state: null,
      formula: null,
    });
  }, []);

  useEffect(() => {
    if (!selectedGroup) {
      return;
    }
    if (!groups.some((group) => group.label === selectedGroup)) {
      setSelectedGroup("");
    }
  }, [groups, selectedGroup]);

  useEffect(() => {
    if (pendingProcessLimit === null) {
      return;
    }
    if (!processesQuery.isFetching && !processesQuery.isPending) {
      setPendingProcessLimit(null);
    }
  }, [pendingProcessLimit, processesQuery.isFetching, processesQuery.isPending]);

  useEffect(() => {
    return () => {
      sendAbortControllerRef.current?.abort();
      sendAbortControllerRef.current = null;
      requestInFlightRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (!isChatLoading || activeTurnId === null) {
      return;
    }
    if (isTurnFinalized(chatMessages, activeTurnId)) {
      setIsChatLoading(false);
      setActiveTurnId(null);
      requestInFlightRef.current = false;
      sendAbortControllerRef.current = null;
    }
  }, [activeTurnId, chatMessages, isChatLoading]);

  const loadingMessage = useMemo(() => {
    if (bootstrapQuery.isLoading) {
      return "Initializing dashboard...";
    }
    if (bootstrapQuery.isError) {
      return "Unable to connect to backend bridge.";
    }
    return "";
  }, [bootstrapQuery.isError, bootstrapQuery.isLoading]);

  const handleSendMessage = useCallback(
    async (text: string, options?: { resourceAttachments?: ResourceAttachment[] }) => {
      const intent = text.trim();
      if (!intent || isChatBusy || requestInFlightRef.current) {
        return;
      }
      const rawResourceAttachments = Array.isArray(options?.resourceAttachments) ? options.resourceAttachments : [];
      const resourceAttachmentMap = new Map<string, ResourceAttachment>();
      rawResourceAttachments.forEach((attachment) => {
        const kind = typeof attachment.kind === "string" ? attachment.kind.trim().toLowerCase() : "";
        const value = typeof attachment.value === "string" ? attachment.value.trim() : "";
        if (!value || (kind !== "computer" && kind !== "code" && kind !== "plugin")) {
          return;
        }
        const key = `${kind}:${value.toLowerCase()}`;
        if (resourceAttachmentMap.has(key)) {
          return;
        }
        resourceAttachmentMap.set(key, {
          kind,
          value,
          label: typeof attachment.label === "string" && attachment.label.trim() ? attachment.label.trim() : value,
          plugin:
            typeof attachment.plugin === "string" && attachment.plugin.trim() ? attachment.plugin.trim() : null,
          computerLabel:
            typeof attachment.computerLabel === "string" && attachment.computerLabel.trim()
              ? attachment.computerLabel.trim()
              : null,
          hostname:
            typeof attachment.hostname === "string" && attachment.hostname.trim() ? attachment.hostname.trim() : null,
        });
      });
      const resourceAttachments = [...resourceAttachmentMap.values()];
      const selectedContextNodes = dedupeFocusNodes([...pinnedNodes, ...contextNodes]);
      const contextPks = selectedContextNodes.map((node) => node.pk);
      const textReferencedPks = extractPkReferences(intent);
      const mergedContextPks = mergeUniquePks(contextPks, textReferencedPks);

      const controller = new AbortController();
      sendAbortControllerRef.current = controller;
      requestInFlightRef.current = true;
      setIsChatLoading(true);
      setActiveTurnId(null);

      try {
        const payload: SendChatRequest = {
          intent,
          model_name: selectedModel || undefined,
          context_node_ids: mergedContextPks,
          context_pks: mergedContextPks,
          metadata: {
            selected_group: selectedGroup || null,
            session_environment: sessionEnvironment,
            session_environment_auto: sessionEnvironmentAuto,
            prompt_override: promptOverride.trim() || null,
            context_pks: mergedContextPks,
            context_node_pks: mergedContextPks,
            context_nodes: selectedContextNodes.map((node) => ({
              pk: node.pk,
              label: node.label,
              formula: node.formula,
              node_type: node.node_type,
            })),
            pinned_nodes: pinnedNodes.map((node) => ({
              pk: node.pk,
              label: node.label,
              formula: node.formula,
              node_type: node.node_type,
            })),
            session_parameters: normalizeSessionParameters(sessionParameters),
            resource_attachments: resourceAttachments.map((attachment) => ({
              kind: attachment.kind,
              value: attachment.value,
              label: attachment.label,
              plugin: attachment.plugin,
              computer_label: attachment.computerLabel,
              hostname: attachment.hostname,
            })),
          },
        };
        const { turn_id: turnId } = await sendChat(payload, controller.signal);
        setActiveTurnId(turnId);
        setContextNodes([]);
        setComposerResetVersion((current) => current + 1);
        void queryClient.invalidateQueries({ queryKey: ["chat"] });
        void queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
      } catch (error) {
        setIsChatLoading(false);
        setActiveTurnId(null);
        if (!isAbortError(error)) {
          console.error("Chat request failed", error);
        }
      } finally {
        sendAbortControllerRef.current = null;
        requestInFlightRef.current = false;
      }
    },
    [
      contextNodes,
      isChatBusy,
      pinnedNodes,
      promptOverride,
      queryClient,
      selectedGroup,
      selectedModel,
      sessionEnvironment,
      sessionEnvironmentAuto,
      sessionParameters,
    ],
  );

  const handleStopResponse = useCallback(() => {
    void stopActiveChatTurn();
  }, [stopActiveChatTurn]);

  const handleCreateGroup = useCallback(async (label: string) => {
    await createGroupMutation.mutateAsync(label);
  }, [createGroupMutation]);

  const handleRenameGroup = useCallback(async (pk: number, label: string) => {
    await renameGroupMutation.mutateAsync({ pk, label });
  }, [renameGroupMutation]);

  const handleDeleteGroup = useCallback(async (pk: number) => {
    const deletedGroup = groups.find((group) => group.pk === pk) ?? null;
    await deleteGroupMutation.mutateAsync(pk);
    if (deletedGroup && selectedGroup === deletedGroup.label) {
      setSelectedGroup("");
    }
  }, [deleteGroupMutation, groups, selectedGroup]);

  const handleAssignNodesToGroup = useCallback(async (groupPk: number, nodePks: number[]) => {
    await addNodesToGroupMutation.mutateAsync({ groupPk, nodePks });
  }, [addNodesToGroupMutation]);

  const handleSoftDeleteNode = useCallback(async (pk: number) => {
    await softDeleteNodeMutation.mutateAsync(pk);
    setContextNodes((current) => current.filter((node) => node.pk !== pk));
  }, [softDeleteNodeMutation]);

  const handleExportGroup = useCallback(async (group: GroupItem) => {
    const payload = await exportGroup(group.pk);
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    try {
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${group.label.replace(/[^\w.-]+/g, "_") || `group-${group.pk}`}.json`;
      anchor.click();
    } finally {
      URL.revokeObjectURL(url);
    }
  }, []);

  const handleConsultFailedProcess = useCallback((process: ProcessItem) => {
    const prompt = `Please diagnose failed process #${process.pk} (${process.label || process.node_type}). Explain the likely root cause and propose concrete next actions.`;
    void handleSendMessage(prompt);
  }, [handleSendMessage]);

  const handleCloneProcess = useCallback(async (process: ProcessItem) => {
    setIsCloneDraftLoading(true);
    try {
      const payload = await getProcessCloneDraft(process.pk);
      setCloneDraft(payload as SubmissionDraftPayload);
      setCloneTurnId(process.pk);
      setCloneModalState({ status: "idle", processPk: null, processPks: [], errorText: null });
    } catch (error) {
      const message = error instanceof Error ? error.message : `Failed to clone process #${process.pk}.`;
      window.alert(message);
    } finally {
      setIsCloneDraftLoading(false);
    }
  }, []);

  const handleCloseCloneModal = useCallback(() => {
    if (cloneModalState.status === "submitting") {
      return;
    }
    setCloneDraft(null);
    setCloneTurnId(null);
    setCloneModalState({ status: "idle", processPk: null, processPks: [], errorText: null });
  }, [cloneModalState.status]);

  const handleConfirmCloneDraft = useCallback(
    async (draftPayload: SubmissionSubmitDraft) => {
      if (!cloneDraft || cloneTurnId === null) {
        return;
      }
      setCloneModalState({ status: "submitting", processPk: null, processPks: [], errorText: null });
      try {
        const response = await submitPreviewDraft(draftPayload);
        const rawSubmitted = response.submitted_pks ?? response.process_pks ?? response.pk;
        const processPks = Array.isArray(rawSubmitted)
          ? rawSubmitted.map((value) => Number.parseInt(String(value), 10)).filter((value) => Number.isFinite(value) && value > 0)
          : (() => {
              const parsed = Number.parseInt(String(rawSubmitted ?? ""), 10);
              return Number.isFinite(parsed) && parsed > 0 ? [parsed] : [];
            })();
        setCloneModalState({
          status: "submitted",
          processPk: processPks[0] ?? null,
          processPks,
          errorText: null,
        });
        void queryClient.invalidateQueries({ queryKey: ["processes"] });
      } catch (error) {
        const errorText = error instanceof Error ? error.message : "Failed to submit cloned workflow.";
        setCloneModalState({ status: "error", processPk: null, processPks: [], errorText });
      }
    },
    [cloneDraft, cloneTurnId, queryClient],
  );

  const handleCancelCloneDraft = useCallback(async () => {
    setCloneModalState({ status: "cancelled", processPk: null, processPks: [], errorText: null });
    try {
      await cancelPendingSubmission();
    } catch (error) {
      console.error("Failed to clear pending submission", error);
    }
  }, []);

  return (
    <main className="dashboard-shell h-screen overflow-hidden p-2">
      <div className="mx-auto flex h-full min-h-0 w-full max-w-[1600px] flex-col gap-2 xl:flex-row">
        <section className="flex h-full min-h-0 w-full shrink-0 overflow-hidden rounded-[26px] border border-white/40 bg-white/72 shadow-glass backdrop-blur lg:w-[420px] dark:border-white/10 dark:bg-zinc-950/40">
          <div className="flex h-full w-12 flex-col items-center justify-between border-r border-zinc-200/70 bg-zinc-50/85 px-1.5 py-3 dark:border-zinc-800/70 dark:bg-zinc-900/60">
            <div className="flex flex-col items-center gap-2">
              <Button
                variant="ghost"
                size="icon"
                className={cn(
                  "h-9 w-9 rounded-xl text-zinc-500 hover:bg-white hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100",
                  sidebarView === "explorer" &&
                    "bg-white text-zinc-900 shadow-[0_10px_20px_-16px_rgba(15,23,42,0.45)] dark:bg-zinc-800 dark:text-zinc-100",
                )}
                onClick={() => setSidebarView("explorer")}
                aria-label="AiiDA Explorer"
              >
                <Database className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className={cn(
                  "h-9 w-9 rounded-xl text-zinc-500 hover:bg-white hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100",
                  sidebarView === "history" &&
                    "bg-white text-zinc-900 shadow-[0_10px_20px_-16px_rgba(15,23,42,0.45)] dark:bg-zinc-800 dark:text-zinc-100",
                )}
                onClick={() => setSidebarView("history")}
                aria-label="Chat History"
              >
                <History className="h-4 w-4" />
              </Button>
            </div>
            <div className="h-9 w-9" />
          </div>

          <div className="flex min-w-0 flex-1 flex-col bg-transparent">
            <div className="border-b border-zinc-200/70 px-3 py-3 dark:border-zinc-800/70">
              <Button
                className="h-10 w-full justify-start gap-2 rounded-xl"
                onClick={() => {
                  void handleCreateChatSession();
                }}
              >
                <PlusSquare className="h-4 w-4" />
                New Conversation
              </Button>
            </div>
            {sidebarView === "explorer" ? (
              <Sidebar
                processes={processes}
                groups={groups}
                selectedGroup={selectedGroup}
                processLimit={processLimit}
                contextNodeIds={contextNodeIds}
                isUpdatingProcessLimit={pendingProcessLimit !== null}
                isDarkMode={theme === "dark"}
                onToggleTheme={() => setTheme((value) => (value === "dark" ? "light" : "dark"))}
                onGroupChange={setSelectedGroup}
                nodeTypeFilter={nodeTypeFilter}
                onNodeTypeFilterChange={setNodeTypeFilter}
                onProcessLimitChange={(nextLimit) => {
                  if (nextLimit === processLimit) {
                    return;
                  }
                  setProcessLimit(nextLimit);
                  setPendingProcessLimit(nextLimit);
                }}
                onAddContextNode={handleAddContextNode}
                onOpenProcessDetail={setActiveProcess}
                onCreateGroup={handleCreateGroup}
                onRenameGroup={handleRenameGroup}
                onDeleteGroup={handleDeleteGroup}
                onAssignNodesToGroup={handleAssignNodesToGroup}
                onSoftDeleteNode={handleSoftDeleteNode}
                onExportGroup={handleExportGroup}
                onConsultFailedProcess={handleConsultFailedProcess}
                onCloneProcess={handleCloneProcess}
              />
            ) : (
              <HistorySidebar
                projects={chatProjects}
                sessions={chatSessions}
                activeProjectId={activeProjectId}
                activeSessionId={activeChatSessionId}
                activeSession={activeChatSession}
                activeWorkspace={activeWorkspace}
                isWorkspaceLoading={openWorkspaceMutation.isPending}
                isBusy={isChatBusy}
                isDarkMode={theme === "dark"}
                onToggleTheme={() => setTheme((value) => (value === "dark" ? "light" : "dark"))}
                onActivateSession={(sessionId) => {
                  void handleActivateChatSession(sessionId);
                }}
                onUpdateSessionTags={(sessionId, tags) => {
                  void handleUpdateChatSessionTags(sessionId, tags);
                }}
                onCreateProject={({ name, rootPath }) => {
                  void handleCreateProject({ name, rootPath });
                }}
                onOpenWorkspace={(sessionId) => {
                  void handleOpenWorkspace(sessionId);
                }}
              />
            )}
          </div>
        </section>

        <section className="flex h-full min-h-0 min-w-0 flex-1 flex-col gap-2 overflow-x-hidden xl:pt-10">
          {isReady ? (
            <ChatPanel
              messages={chatMessages}
              models={models}
              selectedModel={selectedModel}
              composerResetVersion={composerResetVersion}
              isLoading={isChatBusy}
              activeTurnId={activeTurnId}
              contextNodes={contextNodes}
              pinnedNodes={pinnedNodes}
              sessionEnvironment={sessionEnvironment}
              sessionEnvironmentAuto={sessionEnvironmentAuto}
              promptOverride={promptOverride}
              sessionParameters={sessionParameters}
              selectedGroup={selectedGroup}
              onSendMessage={handleSendMessage}
              onStopResponse={handleStopResponse}
              onModelChange={setSelectedModel}
              onAttachFile={(file) => uploadMutation.mutate(file)}
              onAddContextNode={appendContextNode}
              onPinNode={handlePinNode}
              onUnpinNode={handleUnpinNode}
              onRemoveContextNode={handleRemoveContextNode}
              onOpenDetail={handleOpenDetail}
              onRestoreContextNodes={handleRestoreContextNodes}
              onSessionEnvironmentChange={setSessionEnvironment}
              onSessionEnvironmentAutoChange={setSessionEnvironmentAuto}
              onPromptOverrideChange={setPromptOverride}
              onSessionParametersChange={setSessionParameters}
            />
          ) : (
            <section className="flex flex-1 items-center justify-center rounded-2xl border border-white/40 bg-white/70 shadow-glass backdrop-blur dark:border-white/10 dark:bg-zinc-950/40">
              <p className="text-sm text-zinc-600 dark:text-zinc-300">{loadingMessage}</p>
            </section>
          )}

          <RuntimeTerminal lines={logs} />
        </section>
      </div>
      <ProcessDetailDrawer
        process={activeProcess}
        onClose={() => setActiveProcess(null)}
        onAddContextNode={appendContextNode}
      />
      <SubmissionModal
        open={Boolean(cloneDraft) && cloneTurnId !== null}
        turnId={cloneTurnId}
        submissionDraft={cloneDraft}
        state={cloneModalState}
        isBusy={isCloneDraftLoading || cloneModalState.status === "submitting"}
        onToggleExpanded={undefined}
        onClose={handleCloseCloneModal}
        onConfirm={(draftPayload) => {
          void handleConfirmCloneDraft(draftPayload);
        }}
        onCancel={() => {
          void handleCancelCloneDraft();
        }}
        onOpenDetail={handleOpenDetail}
      />
    </main>
  );
}
