export type ProfileItem = {
  name: string;
  display_name: string;
  is_active: boolean;
  type: "configured" | "imported" | string;
};

export type ProcessItem = {
  pk: number;
  label: string;
  state: string;
  status_color: "running" | "success" | "error" | "idle" | string;
};

export type ChatMessage = {
  role: "user" | "assistant" | string;
  text: string;
  status: "thinking" | "done" | "error" | string;
  turn_id: number;
};

export type ChatSnapshot = {
  version: number;
  messages: ChatMessage[];
};

export type LogsSnapshot = {
  version: number;
  lines: string[];
};

export type BootstrapResponse = {
  profiles: ProfileItem[];
  current_profile: string | null;
  processes: ProcessItem[];
  chat: ChatSnapshot;
  logs: LogsSnapshot;
  models: string[];
  selected_model: string;
  quick_prompts: Array<{ label: string; prompt: string }>;
};

export type ProcessesResponse = {
  items: ProcessItem[];
};

export type ProfilesResponse = {
  current_profile: string | null;
  profiles: ProfileItem[];
};

export type UploadArchiveResponse = {
  status: string;
  profile_name: string;
  stored_path: string;
  profiles: ProfileItem[];
};

export type LogsResponse = LogsSnapshot;

export type ChatResponse = ChatSnapshot;

export type SendChatRequest = {
  intent: string;
  model_name?: string;
  context_archive?: string | null;
};
