import { supabase } from "@/repository/supabase/queries";
import type { ModelsResponse, RunAgentStep, UsageOverview } from "./types";
import { queryClient } from "@/app/providers";

const BACKEND_BASE_PATH = "/backend";

// Direct backend URL (bypasses the Next.js proxy). Used for multipart uploads
// (transcription, file uploads): the browser POSTs straight to FastAPI.
// Falls back to the proxy path when the public env var is not configured.
function directBaseUrl(): string {
  return (
    process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ||
    BACKEND_BASE_PATH
  );
}

export type {
  ToolCallStep,
  ToolCallStartStep,
  ContentTokenStep,
  MessageStep,
  UserMessageStep,
  RunAgentStep,
  Model,
  ModelsResponse,
  UsageOverview,
} from "./types";

async function getAuthHeaders(): Promise<HeadersInit> {
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return session?.access_token
    ? { Authorization: `Bearer ${session.access_token}` }
    : {};
}

function parseStep(data: unknown): RunAgentStep | null {
  if (typeof data === "string") {
    try {
      return JSON.parse(data);
    } catch {
      return null;
    }
  }
  if (typeof data === "object" && data !== null && "type" in data) {
    return data as RunAgentStep;
  }
  return null;
}

export async function uploadFile(file: File): Promise<{ url: string; mime_type: string }> {
  const headers = await getAuthHeaders();
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${directBaseUrl()}/upload`, {
    method: "POST",
    headers,
    body: formData,
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(
      `Upload failed: HTTP ${res.status}${detail ? ` ${detail}` : ""}`,
    );
  }
  return res.json();
}

export async function transcribeAudio(file: File): Promise<{ text: string }> {
  const headers = await getAuthHeaders();
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${directBaseUrl()}/transcribe`, {
    method: "POST",
    headers,
    body: formData,
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(
      `Transcription failed: HTTP ${res.status}${detail ? ` ${detail}` : ""}`,
    );
  }
  return res.json();
}

export async function getConversationMessages(
  conversationId: string,
): Promise<RunAgentStep[]> {
  const headers = await getAuthHeaders();
  const res = await fetch(
    `${BACKEND_BASE_PATH}/conversations/${conversationId}/messages`,
    { headers },
  );
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function getModels(): Promise<ModelsResponse> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${BACKEND_BASE_PATH}/models`, {
    headers,
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function getUsage(): Promise<UsageOverview> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${BACKEND_BASE_PATH}/usage`, {
    headers,
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function streamSSE(
  path: string,
  body: object,
  signal: AbortSignal,
  onStep: (step: RunAgentStep) => void,
): Promise<void> {
  const authHeaders = await getAuthHeaders();
  const response = await fetch(`${BACKEND_BASE_PATH}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders },
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok) throw new Error(`HTTP ${response.status}`);

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      if (!part.startsWith("data: ")) continue;
      try {
        const step = parseStep(JSON.parse(part.slice(6)));
        if (step && step.type !== "user_message") onStep(step);
      } catch {
        // Skip malformed events
      }
    }
  }

  queryClient.invalidateQueries();
}

export type QuickLogMode = "log" | "edit";

export async function streamQuickLog(
  mode: QuickLogMode,
  day: string,
  payload: object,
  model: string | undefined,
  signal: AbortSignal,
  onStep: (step: RunAgentStep) => void,
): Promise<void> {
  return streamSSE(
    "/quick-log",
    {
      mode,
      day,
      message: payload,
      ...(model ? { model } : {}),
    },
    signal,
    onStep,
  );
}

export async function streamChat(
  conversationId: string,
  payload: object,
  model: string | undefined,
  signal: AbortSignal,
  onStep: (step: RunAgentStep) => void,
): Promise<void> {
  return streamSSE(
    "/chat",
    {
      conversation_id: conversationId,
      message: payload,
      ...(model ? { model } : {}),
    },
    signal,
    onStep,
  );
}
