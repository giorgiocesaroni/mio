import { supabase } from "@/repository/supabase/queries";
import type {
  ConfirmDraftResult,
  LogDraft,
  RunAgentStep,
  ModelChoices,
  ModelInfo,
  ModelOption,
  ModelTask,
  SandboxStep,
} from "./types";
import { queryClient } from "@/app/providers";

const BACKEND_BASE_PATH = "/backend";

// Direct backend URL (bypasses the Next.js proxy). Used for file uploads:
// the browser POSTs straight to FastAPI.
// Falls back to the proxy path when the public env var is not configured.
function directBaseUrl(): string {
  return (
    process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ||
    BACKEND_BASE_PATH
  );
}

export type {
  DraftStep,
  ToolCallStep,
  ToolCallStartStep,
  ContentTokenStep,
  MessageStep,
  UserMessageStep,
  RunAgentStep,
  UsageLogCost,
  UsageOverview,
  SandboxStep,
  SandboxStageStep,
  SandboxDoneStep,
  SandboxStageName,
  ModelChoices,
  ModelInfo,
  ModelOption,
  ModelTask,
  LogDraft,
  DayLog,
  DayEntries,
  DraftRow,
  DraftAlternative,
  DraftServingSize,
  DraftUnit,
  MealType,
  Per100g,
  ConfirmDraftResult,
} from "./types";

async function getAuthHeaders(): Promise<HeadersInit> {
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return session?.access_token
    ? { Authorization: `Bearer ${session.access_token}` }
    : {};
}

function parseStep<T extends { type: string }>(data: unknown): T | null {
  if (typeof data === "string") {
    try {
      return JSON.parse(data);
    } catch {
      return null;
    }
  }
  if (typeof data === "object" && data !== null && "type" in data) {
    return data as T;
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
  // Served by the Next.js route in app/backend/transcribe, not by FastAPI.
  const res = await fetch(`${BACKEND_BASE_PATH}/transcribe`, {
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

async function streamSSE<T extends { type: string } = RunAgentStep>(
  path: string,
  body: object,
  signal: AbortSignal,
  onStep: (step: T) => void,
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
        const step = parseStep<T>(JSON.parse(part.slice(6)));
        if (step && step.type !== "user_message") onStep(step);
      } catch {
        // Skip malformed events
      }
    }
  }

  queryClient.invalidateQueries();
}

export async function streamChat(
  conversationId: string,
  payload: object,
  models: ModelChoices,
  signal: AbortSignal,
  onStep: (step: RunAgentStep) => void,
): Promise<void> {
  return streamSSE(
    "/chat",
    {
      conversation_id: conversationId,
      message: payload,
      models,
    },
    signal,
    onStep,
  );
}

export async function streamSandboxLog(
  payload: object,
  options: { day: string; models: ModelChoices },
  signal: AbortSignal,
  onStep: (step: SandboxStep) => void,
): Promise<void> {
  return streamSSE<SandboxStep>(
    "/sandbox/log",
    {
      message: payload,
      day: options.day,
      models: options.models,
    },
    signal,
    onStep,
  );
}

async function requestJSON<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${BACKEND_BASE_PATH}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...headers },
  });
  if (!res.ok) {
    // FastAPI puts the reason in `detail`.
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

/** The models that can do `task` matching `query`, searched server-side. */
export function searchModels(task: ModelTask, query: string): Promise<ModelOption[]> {
  const params = new URLSearchParams({ task, q: query });
  return requestJSON(`/models?${params}`);
}

/** OpenRouter's catalog entry for one model, as it lists it. */
export function getModelInfo(id: string): Promise<ModelInfo> {
  return requestJSON(`/models/info?${new URLSearchParams({ id })}`);
}

/** The configured model of each task, used when the user picked none. */
export function getModelDefaults(): Promise<Required<ModelChoices>> {
  return requestJSON("/models/defaults");
}


/** Applies a correction in the user's words to one dish of a draft; the draft is null once the correction removed its last dish. */
export function reviseDraftDish(
  id: string,
  dishId: string,
  instruction: string,
  models: ModelChoices,
): Promise<LogDraft | null> {
  return requestJSON(`/drafts/${id}/dishes/${encodeURIComponent(dishId)}/revise`, {
    method: "POST",
    body: JSON.stringify({ instruction, models }),
  });
}

/** Removes one draft dish; the draft is null once it's empty. */
export function deleteDraftDish(
  id: string,
  dishId: string,
): Promise<{ draft: LogDraft | null }> {
  return requestJSON(`/drafts/${id}/dishes/${encodeURIComponent(dishId)}`, {
    method: "DELETE",
  });
}

/** Logs the given rows of a draft, or all of them when `rowIds` is omitted. */
export function confirmDraft(
  id: string,
  rowIds?: string[],
): Promise<ConfirmDraftResult> {
  return requestJSON(`/drafts/${id}/confirm`, {
    method: "POST",
    body: JSON.stringify(rowIds ? { row_ids: rowIds } : {}),
  });
}

export function discardDraft(id: string): Promise<{ success: true }> {
  return requestJSON(`/drafts/${id}/discard`, { method: "POST" });
}

/** Applies a correction in the user's words to logged entries (one card). */
export function reviseLogs(
  day: string,
  logIds: string[],
  instruction: string,
  models: ModelChoices,
): Promise<ConfirmDraftResult> {
  return requestJSON(`/logs/revise`, {
    method: "POST",
    body: JSON.stringify({
      day,
      log_ids: logIds,
      instruction,
      models,
    }),
  });
}

export function deleteLogs(logIds: string[]): Promise<unknown> {
  return requestJSON(`/logs/delete`, {
    method: "POST",
    body: JSON.stringify({ log_ids: logIds }),
  });
}
