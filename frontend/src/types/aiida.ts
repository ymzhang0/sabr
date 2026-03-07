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

export type SessionParameter = {
  key: string;
  value: string;
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
  session_id: string | null;
  messages: ChatMessage[];
  snapshot: ChatSessionSnapshot;
};

export type ChatSessionSnapshot = {
  context_nodes: FocusNode[];
  pinned_nodes: FocusNode[];
  selected_group: string | null;
  selected_model: string | null;
  session_environment: string | null;
  session_environment_auto: boolean;
  prompt_override: string | null;
  session_parameters: SessionParameter[];
};

export type ChatSessionSummary = {
  id: string;
  project_id: string;
  title: string;
  auto_title: boolean;
  title_state: "idle" | "pending" | "ready" | "failed" | string;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
  tags: string[];
  project_label: string | null;
  project_group_label?: string | null;
  session_group_label?: string | null;
  workspace_path: string;
  node_count: number;
  preview: string;
  message_count: number;
  snapshot: ChatSessionSnapshot;
};

export type ChatSessionDetail = ChatSessionSummary & {
  version: number;
  messages: ChatMessage[];
};

export type ChatSessionsResponse = {
  version: number;
  active_session_id: string | null;
  active_project_id: string | null;
  projects: ChatProject[];
  items: ChatSessionSummary[];
};

export type ChatSessionMutationResponse = {
  version: number;
  active_session_id: string | null;
  active_project_id: string | null;
  projects: ChatProject[];
  session: ChatSessionDetail;
  chat: ChatSnapshot;
};

export type ChatProject = {
  id: string;
  name: string;
  group_label?: string | null;
  root_path: string;
  sessions_path: string;
  created_at: string;
  updated_at: string;
  session_count: number;
  active: boolean;
};

export type ChatProjectMutationResponse = {
  project: ChatProject;
  active_project_id: string | null;
  projects: ChatProject[];
};

export type WorkspaceEntry = {
  name: string;
  path: string;
  relative_path: string;
  is_dir: boolean;
  size: number | null;
  updated_at: string;
};

export type ChatSessionWorkspaceResponse = {
  session_id: string;
  project_id: string;
  project_name: string;
  workspace_path: string;
  relative_path: string;
  entries: WorkspaceEntry[];
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

export type SpecializationAction = {
  id: string;
  label: string;
  prompt: string;
  description: string | null;
  icon: string | null;
  command: string | null;
  section: string;
  placements: string[];
  specialization: string;
  specialization_label: string;
  accent: string;
  variant: "general" | "specialized";
  enabled: boolean;
  disabled_reason: string | null;
};

export type SpecializationMenuSection = {
  id: string;
  label: string;
  items: SpecializationAction[];
};

export type SpecializationSummary = {
  name: string;
  label: string;
  description: string | null;
  accent: string;
  variant: "general" | "specialized";
  active: boolean;
  reasons: string[];
};

export type ActiveSpecializationsResponse = {
  chips: SpecializationAction[];
  slash_menu: SpecializationMenuSection[];
  active_specializations: SpecializationSummary[];
  inactive_specializations: SpecializationSummary[];
  environment: {
    selected: string | null;
    resolved: string;
    auto_switch: boolean;
  };
  context: {
    context_node_ids: number[];
    context_node_types: string[];
    project_tags: string[];
    resource_plugins: string[];
    worker_plugins: string[];
    worker_plugins_available: boolean;
  };
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

export type NodeScriptResponse = {
  pk: number;
  node_type: string;
  language: string;
  script: string;
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
  formula?: string | null;
  atom_count?: number | null;
  remote_path?: string | null;
  computer_name?: string | null;
  computer?: string | null;
  path?: string | null;
  filenames?: string[];
  files?: string[];
  file_count?: number | null;
  mesh?: number[];
  offset?: number[];
  mode?: string | null;
  num_points?: number | null;
  has_labels?: boolean | null;
  num_kpoints?: number | null;
  num_bands?: number | null;
  arrays?: Array<{ name?: string; label?: string; shape?: number[] | null }>;
  x_label?: string | null;
  x_length?: number | null;
  y_labels?: string[];
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
    node_type?: string;
    full_type?: string;
    label?: string;
    state?: string;
    process_label?: string;
    exit_status?: number | null;
    ctime?: string | null;
    preview?: ProcessNodeLinkPreview | null;
    preview_info?: ProcessNodeLinkPreview | null;
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

export type NodeFileListResponse = {
  pk: number;
  files: string[];
  source?: string | null;
};

export type NodeFileContentResponse = {
  pk: number;
  filename: string;
  content: string;
  source?: string | null;
};

export type BandsPlotPath = {
  length?: number | null;
  from?: string | null;
  to?: string | null;
  values?: number[][];
  x?: number[];
  two_band_types?: boolean | null;
};

export type BandsPlotData = {
  paths?: BandsPlotPath[];
  band_type_idx?: number[];
  tick_pos?: number[];
  tick_labels?: string[];
  legend_text?: string | null;
  legend_text2?: string | null;
  yaxis_label?: string | null;
  title?: string | null;
  x_min_lim?: number | null;
  x_max_lim?: number | null;
  y_min_lim?: number | null;
  y_max_lim?: number | null;
  plot_zero_axis?: boolean | null;
};

export type BandsPlotResponse = {
  pk: number;
  data: BandsPlotData;
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

export type InfrastructureExportResponse = {
  kind: string;
  label: string;
  filename: string;
  format: string;
  content: string;
};

export type ParseInfrastructureResponse = {
  status: string;
  data: {
    type: "computer" | "code" | "both";
    preset_matched?: boolean;
    preset_domain?: string;
    computer?: {
      label?: string;
      hostname?: string;
      username?: string;
      description?: string;
      transport_type?: string;
      scheduler_type?: string;
      shebang?: string;
      work_dir?: string;
      mpiprocs_per_machine?: number;
      mpirun_command?: string;
      default_memory_per_machine?: number | null;
      use_double_quotes?: boolean;
      prepend_text?: string;
      append_text?: string;
      key_filename?: string;
      proxy_command?: string;
      proxy_jump?: string;
      safe_interval?: number;
      use_login_shell?: boolean;
      connection_timeout?: number;
    };
    code?: {
      label?: string;
      description?: string;
      default_calc_job_plugin?: string;
      remote_abspath?: string;
      prepend_text?: string;
      append_text?: string;
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

export type ImportDataResponse = {
  status: string;
  pk: number;
  uuid: string;
  type: string;
};
