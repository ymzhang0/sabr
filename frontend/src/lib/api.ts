import axios from "axios";

import type {
  BridgeStatusResponse,
  BootstrapResponse,
  ChatResponse,
  GroupsResponse,
  LogsResponse,
  ProcessesResponse,
  ProfilesResponse,
  SendChatRequest,
  UploadArchiveResponse,
} from "@/types/aiida";

const API_BASE_URL = import.meta.env.DEV ? "http://localhost:8000" : "";
const FRONTEND_API_PREFIX = "/api/aiida/frontend";
const AIIDA_API_PREFIX = "/api/aiida";
const frontendBaseURL = `${API_BASE_URL}${FRONTEND_API_PREFIX}`;
const aiidaBaseURL = `${API_BASE_URL}${AIIDA_API_PREFIX}`;

function resolveHttpOrigin(): string {
  if (import.meta.env.DEV) {
    return "http://localhost:8000";
  }
  if (typeof window === "undefined") {
    return "";
  }
  return `${window.location.protocol}//${window.location.host}`;
}

function resolveWsOrigin(): string {
  if (import.meta.env.DEV) {
    return "ws://localhost:8000";
  }
  if (typeof window === "undefined") {
    return "";
  }
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}`;
}

export function getFrontendStreamUrl(path: string): string {
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  return `${resolveHttpOrigin()}${cleanPath}`;
}

export function getTerminalWsUrl(path = "/api/terminal"): string {
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  return `${resolveWsOrigin()}${cleanPath}`;
}

export const LOGS_STREAM_URL = getFrontendStreamUrl(`${FRONTEND_API_PREFIX}/logs/stream`);
export const TERMINAL_WS_URL = getTerminalWsUrl("/api/terminal");

export const frontendApi = axios.create({
  baseURL: frontendBaseURL,
  timeout: 15000,
});

const aiidaApi = axios.create({
  baseURL: aiidaBaseURL,
  timeout: 5000,
});

export async function getBootstrap(): Promise<BootstrapResponse> {
  const { data } = await frontendApi.get<BootstrapResponse>("/bootstrap");
  return data;
}

export async function getProfiles(): Promise<ProfilesResponse> {
  const { data } = await frontendApi.get<ProfilesResponse>("/profiles");
  return data;
}

export async function switchProfile(profileName: string): Promise<ProfilesResponse> {
  const { data } = await frontendApi.post<ProfilesResponse>("/profiles/switch", {
    profile_name: profileName,
  });
  return data;
}

export async function uploadArchive(file: File): Promise<UploadArchiveResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const { data } = await frontendApi.post<UploadArchiveResponse>("/archives/upload", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });
  return data;
}

export async function getProcesses(
  limit = 15,
  groupLabel?: string,
  nodeType?: string,
): Promise<ProcessesResponse> {
  const { data } = await frontendApi.get<ProcessesResponse>("/processes", {
    params: { limit, group_label: groupLabel, node_type: nodeType },
  });
  return data;
}

export async function getGroups(): Promise<GroupsResponse> {
  const { data } = await frontendApi.get<GroupsResponse>("/groups");
  return data;
}

export async function getLogs(limit = 240): Promise<LogsResponse> {
  const { data } = await frontendApi.get<LogsResponse>("/logs", {
    params: { limit },
  });
  return data;
}

export async function getChatMessages(): Promise<ChatResponse> {
  const { data } = await frontendApi.get<ChatResponse>("/chat/messages");
  return data;
}

export async function sendChat(
  payload: SendChatRequest,
  signal?: AbortSignal,
): Promise<{ turn_id: number }> {
  const { data } = await frontendApi.post<{ turn_id: number }>("/chat", payload, { signal });
  return data;
}

export async function stopChat(turnId?: number): Promise<{ status: string; turn_id: number | null }> {
  const { data } = await frontendApi.post<{ status: string; turn_id: number | null }>("/chat/stop", {
    turn_id: turnId,
  });
  return data;
}

const DEFAULT_BRIDGE_STATUS: BridgeStatusResponse = {
  status: "offline",
  url: "http://127.0.0.1:8001",
  environment: "Local Sandbox",
};

export async function getBridgeStatus(): Promise<BridgeStatusResponse> {
  try {
    const { data } = await aiidaApi.get<BridgeStatusResponse>("/status");
    return data;
  } catch {
    return DEFAULT_BRIDGE_STATUS;
  }
}

export async function getBridgePlugins(): Promise<string[]> {
  try {
    const { data } = await aiidaApi.get<string[]>("/plugins");
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}
