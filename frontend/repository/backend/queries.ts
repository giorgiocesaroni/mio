import { supabase } from "@/repository/supabase/queries";
import type { RunAgentStep } from "./types";

export type {
  ToolCallStep,
  MessageStep,
  UserMessageStep,
  RunAgentStep,
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

export async function getConversationMessages(
  conversationId: string,
): Promise<RunAgentStep[]> {
  const headers = await getAuthHeaders();
  const res = await fetch(
    `${process.env.NEXT_PUBLIC_BACKEND_URL}/conversations/${conversationId}/messages`,
    { headers },
  );
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function streamChat(
  conversationId: string,
  payload: object,
  signal: AbortSignal,
  onStep: (step: RunAgentStep) => void,
): Promise<void> {
  const authHeaders = await getAuthHeaders();
  const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders },
    body: JSON.stringify({ conversation_id: conversationId, message: payload }),
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
}
