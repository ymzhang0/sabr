import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  CHAT_STREAM_URL,
  LOGS_STREAM_URL,
  getBootstrap,
  getChatMessages,
  getGroups,
  getLogs,
  getProcesses,
  sendChat,
  stopChat,
  uploadArchive,
} from "@/lib/api";
import { ChatPanel } from "@/components/dashboard/chat-panel";
import { ProcessDetailDrawer } from "@/components/dashboard/process-detail-drawer";
import { RuntimeTerminal } from "@/components/dashboard/runtime-terminal";
import { Sidebar } from "@/components/dashboard/sidebar";
import type {
  ChatMessage,
  ChatSnapshot,
  FocusNode,
  ProcessItem,
  SendChatRequest,
} from "@/types/aiida";

const THEME_STORAGE_KEY = "sabr.dashboard.theme";
const CHAT_POLL_INTERVAL_MS = 350;

function initialTheme(): "light" | "dark" {
  const saved = window.localStorage.getItem(THEME_STORAGE_KEY);
  return saved === "light" ? "light" : "dark";
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
    /^(thinking:|running:|step:|⚙️\s*\[step\]\s*:)/i.test(line),
  );
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

export default function App() {
  const queryClient = useQueryClient();
  const [theme, setTheme] = useState<"light" | "dark">(initialTheme);
  const [selectedModel, setSelectedModel] = useState("");
  const [selectedGroup, setSelectedGroup] = useState("");
  const [selectedType, setSelectedType] = useState("");
  const [processLimit, setProcessLimit] = useState(15);
  const [pendingProcessLimit, setPendingProcessLimit] = useState<number | null>(null);
  const [contextNodes, setContextNodes] = useState<FocusNode[]>([]);
  const [activeProcess, setActiveProcess] = useState<ProcessItem | null>(null);
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [activeTurnId, setActiveTurnId] = useState<number | null>(null);
  const [streamedLogs, setStreamedLogs] = useState<{ version: number; lines: string[] } | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const sendAbortControllerRef = useRef<AbortController | null>(null);
  const requestInFlightRef = useRef(false);
  const chatVersionRef = useRef(-1);

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
    queryKey: ["processes", selectedGroup, selectedType, processLimit],
    queryFn: () => getProcesses(processLimit, selectedGroup || undefined, selectedType || undefined),
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

  const applyChatSnapshot = useCallback((snapshot: ChatSnapshot | null | undefined) => {
    if (!snapshot || !Array.isArray(snapshot.messages)) {
      return;
    }

    const incomingVersion = Number.isFinite(snapshot.version) ? snapshot.version : -1;
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
  }, []);

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

  useEffect(() => {
    if (selectedModel) {
      return;
    }
    const fallback = bootstrapQuery.data?.selected_model ?? bootstrapQuery.data?.models?.[0] ?? "";
    if (fallback) {
      setSelectedModel(fallback);
    }
  }, [bootstrapQuery.data, selectedModel]);

  const uploadMutation = useMutation({
    mutationFn: uploadArchive,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["groups"] });
      queryClient.invalidateQueries({ queryKey: ["processes"] });
    },
  });

  const processes = processesQuery.data?.items ?? bootstrapQuery.data?.processes ?? [];
  const groups = groupsQuery.data?.items ?? bootstrapQuery.data?.groups ?? [];
  const polledLogsVersion = logsQuery.data?.version ?? bootstrapQuery.data?.logs.version ?? -1;
  const polledLogs = logsQuery.data?.lines ?? bootstrapQuery.data?.logs.lines ?? [];
  const logs =
    streamedLogs && streamedLogs.version >= polledLogsVersion
      ? streamedLogs.lines
      : polledLogs;
  const chatMessages = messages.length > 0 ? messages : chatQuery.data?.messages ?? bootstrapQuery.data?.chat.messages ?? [];
  const models = bootstrapQuery.data?.models ?? [];
  const quickPrompts = bootstrapQuery.data?.quick_prompts ?? [];

  const isReady = bootstrapQuery.isSuccess;
  const contextNodeIds = useMemo(() => contextNodes.map((node) => node.pk), [contextNodes]);
  const isChatBusy = isChatLoading;

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
    const seen = new Set<number>();
    const restored: FocusNode[] = [];
    nodes.forEach((node) => {
      if (!node || seen.has(node.pk)) {
        return;
      }
      seen.add(node.pk);
      restored.push(node);
    });
    setContextNodes(restored);
  }, []);

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
    if (!groups.includes(selectedGroup)) {
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
    async (text: string) => {
      const intent = text.trim();
      if (!intent || isChatBusy || requestInFlightRef.current) {
        return;
      }
      const selectedContextNodes = [...contextNodes];
      const contextPks = selectedContextNodes.map((node) => node.pk);

      const controller = new AbortController();
      sendAbortControllerRef.current = controller;
      requestInFlightRef.current = true;
      setIsChatLoading(true);
      setActiveTurnId(null);

      try {
        const payload: SendChatRequest = {
          intent,
          model_name: selectedModel || undefined,
          context_node_ids: contextPks,
          context_pks: contextPks,
          metadata: {
            context_pks: contextPks,
            context_node_pks: contextPks,
            context_nodes: selectedContextNodes.map((node) => ({
              pk: node.pk,
              label: node.label,
              formula: node.formula,
              node_type: node.node_type,
            })),
          },
        };
        const sendPromise = sendChat(payload, controller.signal);
        setContextNodes([]);
        const { turn_id: turnId } = await sendPromise;
        setActiveTurnId(turnId);
        void queryClient.invalidateQueries({ queryKey: ["chat"] });
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
    [contextNodes, isChatBusy, queryClient, selectedModel],
  );

  const handleStopResponse = useCallback(() => {
    if (!isChatBusy) {
      return;
    }

    sendAbortControllerRef.current?.abort();
    sendAbortControllerRef.current = null;
    requestInFlightRef.current = false;
    setIsChatLoading(false);
    const turnIdToStop = activeTurnId;
    setActiveTurnId(null);

    void stopChat(turnIdToStop ?? undefined)
      .catch((error) => {
        if (!isAbortError(error)) {
          console.error("Failed to stop chat request", error);
        }
      })
      .finally(() => {
        void queryClient.invalidateQueries({ queryKey: ["chat"] });
      });
  }, [activeTurnId, isChatBusy, queryClient]);

  return (
    <main className="dashboard-shell h-screen overflow-hidden p-2">
      <div className="mx-auto flex h-full min-h-0 w-full max-w-[1600px] flex-col gap-2 xl:flex-row">
        <Sidebar
          processes={processes}
          groupOptions={groups}
          selectedGroup={selectedGroup}
          selectedType={selectedType}
          processLimit={processLimit}
          contextNodeIds={contextNodeIds}
          isUpdatingProcessLimit={pendingProcessLimit !== null}
          isDarkMode={theme === "dark"}
          onToggleTheme={() => setTheme((value) => (value === "dark" ? "light" : "dark"))}
          onGroupChange={setSelectedGroup}
          onTypeChange={setSelectedType}
          onProcessLimitChange={(nextLimit) => {
            if (nextLimit === processLimit) {
              return;
            }
            setProcessLimit(nextLimit);
            setPendingProcessLimit(nextLimit);
          }}
          onAddContextNode={handleAddContextNode}
          onOpenProcessDetail={setActiveProcess}
        />

        <section className="flex h-full min-h-0 min-w-0 flex-1 flex-col gap-2 overflow-x-hidden xl:pt-10">
          {isReady ? (
            <ChatPanel
              messages={chatMessages}
              models={models}
              selectedModel={selectedModel}
              quickPrompts={quickPrompts}
              isLoading={isChatBusy}
              activeTurnId={activeTurnId}
              contextNodes={contextNodes}
              onSendMessage={handleSendMessage}
              onStopResponse={handleStopResponse}
              onModelChange={setSelectedModel}
              onAttachFile={(file) => uploadMutation.mutate(file)}
              onRemoveContextNode={handleRemoveContextNode}
              onOpenDetail={handleOpenDetail}
              onRestoreContextNodes={handleRestoreContextNodes}
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
    </main>
  );
}
