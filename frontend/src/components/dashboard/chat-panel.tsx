import { Bot, ChevronDown, Paperclip, SendHorizontal } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/types/aiida";

type ChatTurn = {
  turnId: number;
  userText?: string;
  thinkingText?: string;
  assistantText?: string;
  assistantStatus?: string;
};

function groupMessages(messages: ChatMessage[]): ChatTurn[] {
  const grouped = new Map<number, ChatTurn>();

  messages.forEach((message, index) => {
    const turnId = message.turn_id > 0 ? message.turn_id : index + 1;
    const turn = grouped.get(turnId) ?? { turnId };

    if (message.role === "user") {
      turn.userText = message.text;
    } else if (message.status === "thinking") {
      turn.thinkingText = message.text;
    } else {
      turn.assistantText = message.text;
      turn.assistantStatus = message.status;
    }

    grouped.set(turnId, turn);
  });

  return [...grouped.values()].sort((a, b) => a.turnId - b.turnId);
}

type ChatPanelProps = {
  messages: ChatMessage[];
  models: string[];
  selectedModel: string;
  quickPrompts: Array<{ label: string; prompt: string }>;
  isSending: boolean;
  onSendMessage: (text: string) => void;
  onModelChange: (model: string) => void;
  onAttachFile: (file: File) => void;
};

export function ChatPanel({
  messages,
  models,
  selectedModel,
  quickPrompts,
  isSending,
  onSendMessage,
  onModelChange,
  onAttachFile,
}: ChatPanelProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const modelMenuRef = useRef<HTMLDivElement | null>(null);
  const [draft, setDraft] = useState("");
  const [isModelMenuOpen, setIsModelMenuOpen] = useState(false);
  const [avatarFailed, setAvatarFailed] = useState(false);

  const turns = useMemo(() => groupMessages(messages), [messages]);

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

  const updateTextareaHeight = (target: HTMLTextAreaElement) => {
    target.style.height = "0px";
    target.style.height = `${Math.min(target.scrollHeight, 220)}px`;
  };

  const handleSubmit = () => {
    const text = draft.trim();
    if (!text) {
      return;
    }
    onSendMessage(text);
    setDraft("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "56px";
    }
  };

  return (
    <Panel className="flex h-full min-h-0 min-w-0 flex-1 flex-col gap-2 overflow-x-hidden p-0">
      <div className="minimal-scrollbar min-h-0 flex-1 space-y-5 overflow-x-hidden overflow-y-auto px-5 pb-6 pt-5 md:px-8">
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
          turns.map((turn) => (
            <article key={turn.turnId} className="space-y-3">
              {turn.userText ? (
                <div className="flex justify-end">
                  <div className="max-w-[78%] rounded-2xl border border-zinc-200/80 bg-white/90 px-4 py-3 text-sm leading-6 text-zinc-900 shadow-sm dark:border-zinc-800 dark:bg-zinc-900/80 dark:text-zinc-100">
                    <p className="whitespace-pre-wrap">{turn.userText}</p>
                  </div>
                </div>
              ) : null}

              {turn.thinkingText || turn.assistantText ? (
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
                    {turn.thinkingText ? (
                      <details className="rounded-xl border border-zinc-200/80 bg-zinc-50/85 px-3 py-2 text-xs transition-colors duration-200 dark:border-zinc-800 dark:bg-zinc-900/70">
                        <summary className="cursor-pointer select-none uppercase tracking-[0.16em] text-zinc-500 dark:text-zinc-400">
                          Thinking...
                        </summary>
                        <p className="mt-2 whitespace-pre-wrap leading-5 text-zinc-600 dark:text-zinc-300">
                          {turn.thinkingText}
                        </p>
                      </details>
                    ) : null}

                    {turn.assistantText ? (
                      <div
                        className={cn(
                          "rounded-2xl border bg-zinc-50/80 px-4 py-3 text-sm leading-6 text-zinc-800 transition-colors duration-200 dark:bg-zinc-900/60 dark:text-zinc-100",
                          turn.assistantStatus === "error"
                            ? "border-rose-200/80 dark:border-rose-800/60"
                            : "border-zinc-200/80 dark:border-zinc-800",
                        )}
                      >
                        <p className="whitespace-pre-wrap">{turn.assistantText}</p>
                        {turn.assistantStatus === "error" ? (
                          <p className="mt-2 text-xs text-rose-500">Response ended with error.</p>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                </div>
              ) : null}
            </article>
          ))
        )}
      </div>

      <div className="bg-white/75 px-4 pb-4 pt-3 backdrop-blur dark:bg-zinc-950/35 md:px-6">
        {quickPrompts.length > 0 ? (
          <div className="mb-2 flex flex-wrap gap-2">
            {quickPrompts.map((prompt) => (
              <Button
                key={prompt.label}
                variant="ghost"
                size="sm"
                className="rounded-full border border-zinc-300/70 px-3 transition-colors duration-200 dark:border-white/10"
                onClick={() => onSendMessage(prompt.prompt)}
              >
                {prompt.label}
              </Button>
            ))}
          </div>
        ) : null}

        <div className="rounded-2xl border border-zinc-200/80 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-950/70">
          <textarea
            ref={textareaRef}
            rows={2}
            value={draft}
            placeholder="Message SABR..."
            className="max-h-[220px] min-h-[56px] w-full resize-none border-none bg-transparent text-sm text-zinc-900 outline-none placeholder:text-zinc-400 dark:text-zinc-100"
            onChange={(event) => {
              setDraft(event.target.value);
              updateTextareaHeight(event.currentTarget);
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                handleSubmit();
              }
            }}
          />

          <div className="mt-3 flex flex-row items-center justify-between gap-3">
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
                    className={cn("h-4 w-4 shrink-0 transition-transform duration-200", isModelMenuOpen && "rotate-180")}
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

            <Button onClick={handleSubmit} disabled={isSending || !draft.trim()}>
              <SendHorizontal className="h-4 w-4" /> Send
            </Button>
          </div>
        </div>
      </div>
    </Panel>
  );
}
