export type ProcessItem = {
  pk: number;
  label: string;
  state: string;
  status_color: "running" | "success" | "error" | "idle" | string;
  node_type: string;
  process_label?: string | null;
  process_state: string | null;
  formula: string | null;
  preview?: Record<string, unknown> | null;
  preview_info?: Record<string, unknown> | null;
};

export type FocusNode = {
  pk: number;
  label: string;
  formula: string | null;
  node_type: string;
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
  context_pks?: number[];
  metadata?: Record<string, unknown>;
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

export type ProcessTreeNode = {
  pk: number;
  process_label: string;
  state: string;
  exit_status: number | null;
  inputs?: ProcessNodeLink[];
  outputs?: ProcessNodeLink[];
  children: Record<string, ProcessTreeNode>;
};

export type ProcessNodeLinkPreview = {
  remote_path?: string | null;
  computer_name?: string | null;
  filenames?: string[];
  x_label?: string | null;
  x_length?: number | null;
  y_arrays?: Array<{ label: string; length: number | null }>;
};

export type ProcessNodeLink = {
  link_label: string;
  node_type: string;
  pk: number;
  preview?: ProcessNodeLinkPreview | null;
};

export type ProcessLogsResponse = {
  pk: number;
  lines: string[];
  reports: string[];
  stderr_excerpt: string | null;
  text: string;
};

export type ProcessDetailResponse = {
  summary?: {
    pk?: number;
    uuid?: string;
    type?: string;
    state?: string;
    exit_status?: number | null;
  };
  inputs?: ProcessNodeLink[];
  outputs?: ProcessNodeLink[];
  workchain?: {
    provenance_tree?: ProcessTreeNode;
  };
  logs?: ProcessLogsResponse;
  calculation?: Record<string, unknown>;
};
