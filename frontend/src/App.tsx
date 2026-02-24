import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getBootstrap,
  getChatMessages,
  getLogs,
  getProcesses,
  getProfiles,
  sendChat,
  switchProfile,
  uploadArchive,
} from "@/lib/api";
import { ChatPanel } from "@/components/dashboard/chat-panel";
import { RuntimeTerminal } from "@/components/dashboard/runtime-terminal";
import { Sidebar } from "@/components/dashboard/sidebar";

const THEME_STORAGE_KEY = "sabr.dashboard.theme";

function initialTheme(): "light" | "dark" {
  const saved = window.localStorage.getItem(THEME_STORAGE_KEY);
  return saved === "light" ? "light" : "dark";
}

export default function App() {
  const queryClient = useQueryClient();
  const [theme, setTheme] = useState<"light" | "dark">(initialTheme);
  const [selectedModel, setSelectedModel] = useState("");

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
    queryKey: ["processes"],
    queryFn: () => getProcesses(15),
    enabled: bootstrapQuery.isSuccess,
    refetchInterval: 3_000,
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
    refetchInterval: 900,
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
      queryClient.invalidateQueries({ queryKey: ["chat"] });
    },
  });

  const uploadMutation = useMutation({
    mutationFn: uploadArchive,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profiles"] });
    },
  });

  const sendMutation = useMutation({
    mutationFn: sendChat,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["chat"] });
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
  const logs = logsQuery.data?.lines ?? bootstrapQuery.data?.logs.lines ?? [];
  const chatMessages = chatQuery.data?.messages ?? bootstrapQuery.data?.chat.messages ?? [];
  const models = bootstrapQuery.data?.models ?? [];
  const quickPrompts = bootstrapQuery.data?.quick_prompts ?? [];

  const isReady = bootstrapQuery.isSuccess;
  const loadingMessage = useMemo(() => {
    if (bootstrapQuery.isLoading) {
      return "Initializing dashboard...";
    }
    if (bootstrapQuery.isError) {
      return "Unable to connect to backend bridge.";
    }
    return "";
  }, [bootstrapQuery.isError, bootstrapQuery.isLoading]);

  return (
    <main className="dashboard-shell h-screen overflow-hidden p-2">
      <div className="mx-auto flex h-full min-h-0 w-full max-w-[1600px] flex-col gap-2 xl:flex-row">
        <Sidebar
          profiles={profileData?.profiles ?? []}
          currentProfile={profileData?.current_profile ?? null}
          processes={processes}
          isSwitchingProfile={switchMutation.isPending}
          isUploadingArchive={uploadMutation.isPending}
          isDarkMode={theme === "dark"}
          onToggleTheme={() => setTheme((value) => (value === "dark" ? "light" : "dark"))}
          onSwitchProfile={(profileName) => {
            if (switchMutation.isPending || profileName === profileData?.current_profile) {
              return;
            }
            switchMutation.mutate(profileName);
          }}
          onUploadArchive={(file) => uploadMutation.mutate(file)}
        />

        <section className="flex h-full min-h-0 min-w-0 flex-1 flex-col gap-2 overflow-x-hidden">
          {isReady ? (
            <ChatPanel
              messages={chatMessages}
              models={models}
              selectedModel={selectedModel}
              quickPrompts={quickPrompts}
              isSending={sendMutation.isPending}
              onSendMessage={(text) =>
                sendMutation.mutate({
                  intent: text,
                  model_name: selectedModel || undefined,
                })
              }
              onModelChange={setSelectedModel}
              onAttachFile={(file) => uploadMutation.mutate(file)}
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
