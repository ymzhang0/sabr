export type ProcessItem = {
  pk: number;
  label: string;
  state: string;
  status_color: "running" | "success" | "error" | "idle" | string;
  node_type: string;
  process_state: string | null;
  formula: string | null;
};

export type ReferenceNode = {
  pk: number;
  label: string;
  formula: string | null;
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
  processes: ProcessItem[];
  groups: string[];
  chat: ChatSnapshot;
  logs: LogsSnapshot;
  models: string[];
  selected_model: string;
  quick_prompts: Array<{ label: string; prompt: string }>;
};

export type ProcessesResponse = {
  items: ProcessItem[];
};

export type GroupsResponse = {
  items: string[];
};

export type UploadArchiveResponse = {
  status: string;
  profile_name: string;
  stored_path: string;
};

export type LogsResponse = LogsSnapshot;

export type ChatResponse = ChatSnapshot;

export type SendChatRequest = {
  intent: string;
  model_name?: string;
  context_archive?: string | null;
  context_node_ids?: number[];
};

export type BridgeStatusResponse = {
  status: "online" | "offline";
  url: string;
  environment: string;
  profile: string;
  daemon_status: boolean;
  resources: BridgeSystemCounts;
  plugins: string[];
};

export type BridgeProfileItem = {
  name: string;
  is_default: boolean;
  is_active: boolean;
};

export type BridgeProfilesResponse = {
  current_profile: string | null;
  default_profile: string | null;
  profiles: BridgeProfileItem[];
};

export type BridgeSwitchProfileResponse = {
  status: string;
  current_profile: string | null;
};

export type BridgeSystemCounts = {
  computers: number;
  codes: number;
  workchains: number;
};

export type BridgeSystemInfoResponse = {
  profile: string;
  counts: BridgeSystemCounts;
  daemon_status: boolean;
};

export type BridgeComputerResource = {
  label: string;
  hostname: string;
  description: string | null;
};

export type BridgeCodeResource = {
  label: string;
  default_plugin: string | null;
  computer_label: string | null;
};

export type BridgeResourcesResponse = {
  computers: BridgeComputerResource[];
  codes: BridgeCodeResource[];
};
