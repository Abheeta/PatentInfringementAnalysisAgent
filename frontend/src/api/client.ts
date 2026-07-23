import { ApiError, ChatMessage, Row } from "../types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers:
      options.body && !(options.body instanceof FormData)
        ? { "Content-Type": "application/json", ...options.headers }
        : options.headers,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    if (body?.error) {
      throw new ApiError(body.error);
    }
    throw new ApiError({ code: "unknown_error", message: response.statusText });
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export function createSession(): Promise<{ session_id: string }> {
  return request("/session", { method: "POST" });
}

export function uploadChart(sid: string, file: File): Promise<void> {
  const form = new FormData();
  form.append("file", file);
  return request(`/session/${sid}/upload-chart`, { method: "POST", body: form });
}

export function uploadEvidence(
  sid: string,
  source: { file: File } | { url: string }
): Promise<void> {
  const form = new FormData();
  if ("file" in source) {
    form.append("file", source.file);
  } else {
    form.append("url", source.url);
  }
  return request(`/session/${sid}/upload-evidence`, {
    method: "POST",
    body: form,
  });
}

export function getChart(sid: string): Promise<{ rows: Row[] }> {
  return request(`/session/${sid}/chart`, { method: "GET" });
}

export function generate(
  sid: string
): Promise<{ generated: boolean; opening_message: ChatMessage }> {
  return request(`/session/${sid}/generate`, { method: "POST" });
}

export function getChatHistory(sid: string): Promise<{ messages: ChatMessage[] }> {
  return request(`/session/${sid}/chat/history`, { method: "GET" });
}

export function sendChatMessage(
  sid: string,
  body: { content: string; row_id: number | null }
): Promise<{ assistant_message: ChatMessage; refresh_chart: boolean }> {
  return request(`/session/${sid}/chat/message`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function acceptRow(sid: string, rowId: number): Promise<void> {
  return request(`/session/${sid}/rows/${rowId}/accept`, { method: "POST" });
}

export function rejectRow(sid: string, rowId: number): Promise<void> {
  return request(`/session/${sid}/rows/${rowId}/reject`, { method: "POST" });
}

export function undoRow(sid: string, rowId: number): Promise<void> {
  return request(`/session/${sid}/rows/${rowId}/undo`, { method: "POST" });
}

export function flagRow(
  sid: string,
  rowId: number
): Promise<{ system_note: ChatMessage }> {
  return request(`/session/${sid}/rows/${rowId}/flag`, { method: "POST" });
}

export function getSystemPrompt(sid: string): Promise<{ system_prompt: string }> {
  return request(`/session/${sid}/system-prompt`, { method: "GET" });
}

export function putSystemPrompt(sid: string, text: string): Promise<void> {
  return request(`/session/${sid}/system-prompt`, {
    method: "PUT",
    body: JSON.stringify({ system_prompt: text }),
  });
}

export async function exportChart(sid: string): Promise<Blob> {
  const response = await fetch(`${BASE_URL}/session/${sid}/export`);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    if (body?.error) {
      throw new ApiError(body.error);
    }
    throw new ApiError({ code: "unknown_error", message: response.statusText });
  }
  return response.blob();
}
