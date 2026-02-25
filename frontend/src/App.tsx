import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getBootstrap,
  getChatMessages,
  getGroups,
  getLogs,
  getProcesses,
  getProfiles,
  sendChat,
  stopChat,
  switchProfile,
  uploadArchive,
} from "@/lib/api";
import { ChatPanel } from "@/components/dashboard/chat-panel";
import { RuntimeTerminal } from "@/components/dashboard/runtime-terminal";
import { Sidebar } from "@/components/dashboard/sidebar";
import type {
  ChatMessage,
  ProcessItem,
  ReferenceNode,
  SendChatRequest,
} from "@/types/aiida";

const THEME_STORAGE_KEY = "sabr.dashboard.theme";
const CHAT_POLL_INTERVAL_MS = 350;
const CHAT_TURN_TIMEOUT_MS = 120_000;

function initialTheme(): "light" | "dark" {
  const saved = window.localStorage.getItem(THEME_STORAGE_KEY);
  return saved === "light" ? "light" : "dark";
}

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
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

export default function App() {
  const queryClient = useQueryClient();
  const [theme, setTheme] = useState<"light" | "dark">(initialTheme);
  const [selectedModel, setSelectedModel] = useState("");
  const [selectedGroup, setSelectedGroup] = useState("");
  const [selectedType, setSelectedType] = useState("");
  const [processLimit, setProcessLimit] = useState(15);
  const [pendingProcessLimit, setPendingProcessLimit] = useState<number | null>(null);
  const [selectedReferences, setSelectedReferences] = useState<ReferenceNode[]>([]);
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [activeTurnId, setActiveTurnId] = useState<number | null>(null);
  const sendAbortControllerRef = useRef<AbortController | null>(null);
  const requestInFlightRef = useRef(false);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  const bootstrapQuery = useQuery({
    queryKey: ["bootstrap"],
    queryFn: getBootstrap,
    refetchOnWindowFocus: false,
  });

  const profilesQuery = useQuery({
    queryKey: ["profiles"],
    queryFn: getProfiles,
    enabled: bootstrapQuery.isSuccess,
    refetchInterval: 20_000,
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

  useEffect(() => {
    if (selectedModel) {
      return;
    }
    const fallback = bootstrapQuery.data?.selected_model ?? bootstrapQuery.data?.models?.[0] ?? "";
    if (fallback) {
      setSelectedModel(fallback);
    }
  }, [bootstrapQuery.data, selectedModel]);

  const switchMutation = useMutation({
    mutationFn: switchProfile,
    onSuccess: (data) => {
      queryClient.setQueryData(["profiles"], data);
      queryClient.invalidateQueries({ queryKey: ["processes"] });
      queryClient.invalidateQueries({ queryKey: ["groups"] });
      queryClient.invalidateQueries({ queryKey: ["chat"] });
    },
  });

  const uploadMutation = useMutation({
    mutationFn: uploadArchive,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profiles"] });
      queryClient.invalidateQueries({ queryKey: ["groups"] });
      queryClient.invalidateQueries({ queryKey: ["processes"] });
    },
  });

  const profileData =
    profilesQuery.data ??
    (bootstrapQuery.data
      ? {
          current_profile: bootstrapQuery.data.current_profile,
          profiles: bootstrapQuery.data.profiles,
        }
      : undefined);

  const processes = processesQuery.data?.items ?? bootstrapQuery.data?.processes ?? [];
  const groups = groupsQuery.data?.items ?? bootstrapQuery.data?.groups ?? [];
  const logs = logsQuery.data?.lines ?? bootstrapQuery.data?.logs.lines ?? [];
  const chatMessages = chatQuery.data?.messages ?? bootstrapQuery.data?.chat.messages ?? [];
  const models = bootstrapQuery.data?.models ?? [];
  const quickPrompts = bootstrapQuery.data?.quick_prompts ?? [];

  const isReady = bootstrapQuery.isSuccess;
  const referencedNodeIds = useMemo(
    () => selectedReferences.map((reference) => reference.pk),
    [selectedReferences],
  );
  const isChatBusy = isChatLoading;

  const handleReferenceNode = (process: ProcessItem) => {
    setSelectedReferences((current) => {
      if (current.some((reference) => reference.pk === process.pk)) {
        return current;
      }
      return [
        ...current,
        {
          pk: process.pk,
          label: process.label,
          formula: process.formula ?? null,
        },
      ];
    });
  };

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

      const controller = new AbortController();
      sendAbortControllerRef.current = controller;
      requestInFlightRef.current = true;
      setIsChatLoading(true);
      setActiveTurnId(null);

      try {
        const payload: SendChatRequest = {
          intent,
          model_name: selectedModel || undefined,
          context_node_ids: referencedNodeIds,
        };
        const { turn_id: turnId } = await sendChat(payload, controller.signal);
        setActiveTurnId(turnId);
        const startedAt = Date.now();

        // Keep loading state attached to the active turn until backend marks it complete.
        while (true) {
          if (controller.signal.aborted) {
            throw new DOMException("The request was aborted.", "AbortError");
          }

          const snapshot = await queryClient.fetchQuery({
            queryKey: ["chat"],
            queryFn: getChatMessages,
            staleTime: 0,
          });
          if (isTurnFinalized(snapshot.messages, turnId)) {
            break;
          }

          if (Date.now() - startedAt > CHAT_TURN_TIMEOUT_MS) {
            throw new Error("Timed out while waiting for chat response completion.");
          }

          await sleep(CHAT_POLL_INTERVAL_MS);
        }
      } catch (error) {
        setIsChatLoading(false);
        if (!isAbortError(error)) {
          console.error("Chat request failed", error);
        }
      } finally {
        sendAbortControllerRef.current = null;
        requestInFlightRef.current = false;
        setActiveTurnId(null);
        setIsChatLoading(false);
        void queryClient.invalidateQueries({ queryKey: ["chat"] });
      }
    },
    [isChatBusy, queryClient, referencedNodeIds, selectedModel],
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
          profiles={profileData?.profiles ?? []}
          currentProfile={profileData?.current_profile ?? null}
          processes={processes}
          groupOptions={groups}
          selectedGroup={selectedGroup}
          selectedType={selectedType}
          processLimit={processLimit}
          referencedNodeIds={referencedNodeIds}
          isUpdatingProcessLimit={pendingProcessLimit !== null}
          isSwitchingProfile={switchMutation.isPending}
          isUploadingArchive={uploadMutation.isPending}
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
          onSwitchProfile={(profileName) => {
            if (switchMutation.isPending || profileName === profileData?.current_profile) {
              return;
            }
            switchMutation.mutate(profileName);
          }}
          onUploadArchive={(file) => uploadMutation.mutate(file)}
          onReferenceNode={handleReferenceNode}
        />

        <section className="flex h-full min-h-0 min-w-0 flex-1 flex-col gap-2 overflow-x-hidden">
          {isReady ? (
            <ChatPanel
              messages={chatMessages}
              models={models}
              selectedModel={selectedModel}
              quickPrompts={quickPrompts}
              isLoading={isChatBusy}
              activeTurnId={activeTurnId}
              selectedReferences={selectedReferences}
              onSendMessage={handleSendMessage}
              onStopResponse={handleStopResponse}
              onModelChange={setSelectedModel}
              onAttachFile={(file) => uploadMutation.mutate(file)}
              onRemoveReference={(pk) =>
                setSelectedReferences((current) =>
                  current.filter((reference) => reference.pk !== pk),
                )
              }
            />
          ) : (
            <section className="flex flex-1 items-center justify-center rounded-2xl border border-white/40 bg-white/70 shadow-glass backdrop-blur dark:border-white/10 dark:bg-zinc-950/40">
              <p className="text-sm text-zinc-600 dark:text-zinc-300">{loadingMessage}</p>
            </section>
          )}

          <RuntimeTerminal lines={logs} />
        </section>
      </div>
    </main>
  );
}
