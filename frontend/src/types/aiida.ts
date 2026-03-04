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

export type GroupItem = {
  pk: number;
  label: string;
  count: number;
  type_string?: string | null;
};

export type FocusNode = {
  pk: number;
  label: string;
  formula: string | null;
  node_type: string;
};

export type ResourceAttachmentKind = "computer" | "code" | "plugin";

export type ResourceAttachment = {
  kind: ResourceAttachmentKind;
  value: string;
  label: string;
  plugin: string | null;
  computerLabel: string | null;
  hostname: string | null;
};

export type ChatMessage = {
  role: "user" | "assistant" | string;
  text: string;
  status: "thinking" | "done" | "error" | string;
  turn_id: number;
  payload?: Record<string, unknown> | null;
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
  groups: GroupItem[];
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
  items: GroupItem[];
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

export type SubmissionResponse = Record<string, unknown>;

export type NodeHoverMetadataResponse = {
  pk: number;
  formula: string | null;
  spacegroup: string | null;
  node_type: string;
};

export type GroupMutationResponse = {
  item: GroupItem | null;
};

export type GroupAssignNodesResponse = {
  group: GroupItem | null;
  added: number[];
  missing: number[];
};

export type GroupDeleteResponse = {
  status: string;
  pk: number;
  label?: string;
  count?: number;
};

export type GroupExportResponse = {
  group: GroupItem | null;
  nodes: Record<string, unknown>[];
};

export type SoftDeleteNodeResponse = {
  pk: number;
  soft_deleted: boolean;
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
  inputs?: Record<string, ProcessNodeLink>;
  outputs?: Record<string, ProcessNodeLink>;
  direct_inputs?: Record<string, ProcessNodeLink>;
  direct_outputs?: Record<string, ProcessNodeLink>;
  children: Record<string, ProcessTreeNode>;
};

export type ProcessNodeLinkPreview = {
  remote_path?: string | null;
  computer_name?: string | null;
  computer?: string | null;
  path?: string | null;
  filenames?: string[];
  x_label?: string | null;
  x_length?: number | null;
  y_arrays?: Array<{ label: string; length: number | null }>;
  summary?: string | null;
  value?: string | number | boolean | null;
  count?: number | null;
  keys?: string[] | null;
};

export type ProcessNodeLink = {
  link_label: string;
  node_type: string;
  pk: number;
  label?: string | null;
  preview?: ProcessNodeLinkPreview | null;
  preview_info?: ProcessNodeLinkPreview | null;
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
  inputs?: Record<string, ProcessNodeLink>;
  outputs?: Record<string, ProcessNodeLink>;
  direct_inputs?: Record<string, ProcessNodeLink>;
  direct_outputs?: Record<string, ProcessNodeLink>;
  workchain?: {
    provenance_tree?: ProcessTreeNode;
  };
  logs?: ProcessLogsResponse;
  calculation?: Record<string, unknown>;
};

export type InfrastructureComputerCode = {
  pk: number;
  label: string;
  description: string | null;
  default_calc_job_plugin: string | null;
};

export type InfrastructureComputer = {
  pk: number;
  label: string;
  hostname: string;
  description: string | null;
  scheduler_type: string;
  transport_type: string;
  is_enabled: boolean;
  codes: InfrastructureComputerCode[];
};

export type ParseInfrastructureResponse = {
  status: string;
  data: {
    type: "computer" | "code" | "both";
    computer?: {
      label?: string;
      hostname?: string;
      description?: string;
      transport_type?: string;
      scheduler_type?: string;
      work_dir?: string;
      mpiprocs_per_machine?: number;
      mpirun_command?: string;
    };
    code?: {
      label?: string;
      description?: string;
      default_calc_job_plugin?: string;
      remote_abspath?: string;
    };
  };
};

export type UserInfoResponse = {
  first_name: string;
  last_name: string;
  email: string;
  institution: string;
};

export type ProfileSetupRequest = {
  profile_name: string;
  first_name: string;
  last_name: string;
  email: string;
  institution: string;
  filepath: string;
  backend: string;
  set_as_default: boolean;
};
