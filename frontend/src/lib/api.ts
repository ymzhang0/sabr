import axios from "axios";

import type {
  BootstrapResponse,
  ChatResponse,
  LogsResponse,
  ProcessesResponse,
  ProfilesResponse,
  SendChatRequest,
  UploadArchiveResponse,
} from "@/types/aiida";

const baseURL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/aiida/frontend";

export const frontendApi = axios.create({
  baseURL,
  timeout: 15000,
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

export async function getProcesses(limit = 15): Promise<ProcessesResponse> {
  const { data } = await frontendApi.get<ProcessesResponse>("/processes", {
    params: { limit },
  });
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

export async function sendChat(payload: SendChatRequest): Promise<{ turn_id: number }> {
  const { data } = await frontendApi.post<{ turn_id: number }>("/chat", payload);
  return data;
}
