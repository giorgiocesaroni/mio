import type {
  LogDraft,
  RunAgentStep,
  UserMessageStep,
} from "@/repository/backend/types";

/** A stored chat message: the OpenAI-format message the agent saw. */
type StoredMessage = {
  role?: string;
  content?: unknown;
  tool_calls?: { function: { name: string; arguments: string } }[] | null;
};

type ContentPart = {
  type?: string;
  text?: string;
  image_url?: { url?: string };
  input_audio?: { data?: string };
};

const MIME_TYPES: Record<string, string> = {
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  png: "image/png",
  gif: "image/gif",
  webp: "image/webp",
  heic: "image/heic",
  ogg: "audio/ogg",
  oga: "audio/ogg",
  mp3: "audio/mpeg",
  m4a: "audio/mp4",
  wav: "audio/wav",
  webm: "audio/webm",
  pdf: "application/pdf",
};

function mimeTypeFromUrl(url: string): string | undefined {
  const ext = url.split("?", 1)[0].split(".").pop()?.toLowerCase();
  return ext ? MIME_TYPES[ext] : undefined;
}

/** The mime type of a `data:` URL, e.g. "image/png". */
function dataUrlMimeType(url: string): string {
  return url.slice("data:".length).split(/[;,]/, 1)[0];
}

function attachmentStep(url: string, audio: boolean): UserMessageStep {
  if (!url.startsWith("data:")) {
    return {
      type: "user_message",
      text: audio ? "Audio" : "Image",
      data: url,
      mime_type: mimeTypeFromUrl(url),
    };
  }
  const mime = dataUrlMimeType(url);
  const label = audio
    ? "Audio"
    : mime.startsWith("image/")
      ? "Image"
      : mime.startsWith("audio/")
        ? "Audio"
        : "File";
  return {
    type: "user_message",
    text: label,
    data: url,
    mime_type: audio ? mime : undefined,
  };
}

/** The draft a `log_food` result created, as it is now. */
function draftOf(
  message: StoredMessage,
  drafts: Map<string, LogDraft>,
): LogDraft | undefined {
  if (typeof message.content !== "string") return undefined;
  try {
    const result = JSON.parse(message.content);
    return typeof result?.draft_id === "string"
      ? drafts.get(result.draft_id)
      : undefined;
  } catch {
    return undefined;
  }
}

/** A conversation's stored messages as the steps the chat shows. */
export function conversationSteps(
  messages: StoredMessage[],
  drafts: LogDraft[],
): RunAgentStep[] {
  const draftsById = new Map(drafts.map((d) => [d.id, d]));
  const steps: RunAgentStep[] = [];
  for (const message of messages) {
    if (message.role === "user") {
      if (typeof message.content === "string") {
        steps.push({ type: "user_message", text: message.content });
      } else if (Array.isArray(message.content)) {
        for (const part of message.content as ContentPart[]) {
          if (part.type === "text") {
            steps.push({ type: "user_message", text: part.text ?? "" });
          } else if (part.type === "image_url") {
            steps.push(attachmentStep(part.image_url?.url ?? "", false));
          } else if (part.type === "input_audio") {
            steps.push(attachmentStep(part.input_audio?.data ?? "", true));
          }
        }
      }
    } else if (message.role === "tool") {
      const draft = draftOf(message, draftsById);
      if (draft) steps.push({ type: "draft", draft });
    } else if (message.role === "assistant") {
      if (typeof message.content === "string" && message.content) {
        steps.push({ type: "message", text: message.content });
      }
      for (const call of message.tool_calls ?? []) {
        let args: Record<string, unknown> = {};
        try {
          args = JSON.parse(call.function.arguments);
        } catch {}
        steps.push({ type: "tool_call", name: call.function.name, args });
      }
    }
  }
  return steps;
}
