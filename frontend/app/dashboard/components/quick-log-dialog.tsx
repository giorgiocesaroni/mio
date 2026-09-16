"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  ChatEditor,
  type PendingAttachment,
} from "@/app/components/chat-editor";
import { useAudioRecorder } from "@/app/hooks/use-audio-recorder";
import {
  streamQuickLog,
  uploadFile,
  type QuickLogMode,
  type RunAgentStep,
} from "@/repository/backend/queries";
import { AlertCircle, Cog, Loader2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { MessageContent } from "../chat/components/message-content";

function StepDisplay({ step }: { step: RunAgentStep }) {
  if (step.type === "user_message") {
    if (
      step.data?.startsWith("data:image/") ||
      step.mime_type?.startsWith("image/")
    ) {
      return (
        <img
          src={step.data}
          alt="User image"
          className="max-h-24 max-w-24 justify-self-end rounded-lg object-cover"
        />
      );
    }
    if (step.mime_type?.startsWith("audio/") || step.mime_type === "url") {
      return (
        <audio
          controls
          src={step.data}
          className="ml-8 min-w-32 max-w-full justify-self-end"
        />
      );
    }
    return (
      <div className="ml-8 justify-self-end rounded-xl bg-muted px-4 py-2 text-base break-words">
        {step.text}
      </div>
    );
  }
  if (step.type === "tool_call") {
    return (
      <div className="flex items-center gap-2 text-muted-foreground">
        <Cog className="size-4" />{" "}
        <p className="font-sans">{step.name}</p>
      </div>
    );
  }
  if (step.type === "tool_call_start") {
    return (
      <div className="flex animate-pulse items-center gap-2 text-muted-foreground">
        <Loader2 className="size-4 animate-spin" />{" "}
        <p className="font-sans">{step.name}...</p>
      </div>
    );
  }
  if (step.type === "content_token") {
    return (
      <div className="min-w-0">
        <MessageContent text={step.token} />
      </div>
    );
  }
  if (step.type === "error") {
    return (
      <Alert variant="destructive">
        <AlertCircle />
        <AlertDescription className="break-words whitespace-pre-wrap">
          {step.text}
        </AlertDescription>
      </Alert>
    );
  }
  // Agent message — same plain look as in a conversation.
  return (
    <div className="min-w-0">
      <MessageContent text={step.text} />
    </div>
  );
}

export function QuickLogDialog({
  open,
  mode,
  onClose,
}: {
  open: boolean;
  mode: QuickLogMode;
  onClose: () => void;
}) {
  const [input, setInput] = useState("");
  const [steps, setSteps] = useState<RunAgentStep[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [pendingAttachments, setPendingAttachments] = useState<
    PendingAttachment[]
  >([]);
  const { isRecording, startRecording, stopRecording } = useAudioRecorder();
  const abortRef = useRef<AbortController | null>(null);
  const streamingContentRef = useRef<string>("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) {
      setSteps([]);
      setInput("");
      setPendingAttachments([]);
    } else {
      abortRef.current?.abort();
      setIsLoading(false);
    }
  }, [open]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [steps, open]);

  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  const handleStep = useCallback((step: RunAgentStep) => {
    if (step.type === "content_token") {
      streamingContentRef.current += step.token;
      const token = streamingContentRef.current;
      setSteps((prev) => {
        const last = prev[prev.length - 1];
        if (last?.type === "content_token") {
          return [...prev.slice(0, -1), { type: "content_token", token }];
        }
        return [...prev, { type: "content_token", token }];
      });
    } else if (step.type === "tool_call_start") {
      streamingContentRef.current = "";
      setSteps((prev) => [...prev, step]);
    } else if (step.type === "tool_call") {
      setSteps((prev) => [
        ...prev.filter((s) => s.type !== "tool_call_start"),
        step,
      ]);
    } else if (step.type === "message") {
      setSteps((prev) => [
        ...prev.filter((s) => s.type !== "content_token"),
        step,
      ]);
      streamingContentRef.current = "";
    } else {
      setSteps((prev) => [...prev, step]);
    }
  }, []);

  const handleTextSubmit = async (str: string) => {
    if (
      (!str.trim() && pendingAttachments.length === 0) ||
      isLoading ||
      pendingAttachments.some((a) => a.isLoading)
    )
      return;

    const model =
      typeof window !== "undefined"
        ? (window.localStorage.getItem("model") ?? undefined)
        : undefined;
    // Local YYYY-MM-DD so edits scope to the day the user is looking at.
    const day = new Date().toLocaleDateString("en-CA");

    const text = str.trim();
    setInput("");
    const attachments = pendingAttachments;
    setPendingAttachments([]);
    setIsLoading(true);
    setSteps((prev) => prev.filter((s) => s.type !== "error"));
    const controller = new AbortController();
    abortRef.current = controller;
    streamingContentRef.current = "";

    const parts: object[] = [];
    if (text) parts.push({ text });
    for (const att of attachments)
      parts.push({ url: att.url, mime_type: att.mime_type });

    if (attachments.length > 0) {
      if (text)
        setSteps((prev) => [...prev, { type: "user_message" as const, text }]);
      for (const att of attachments)
        setSteps((prev) => [
          ...prev,
          {
            type: "user_message" as const,
            text: att.name,
            data: att.url,
            mime_type: att.mime_type,
          },
        ]);
    } else {
      setSteps((prev) => [...prev, { type: "user_message" as const, text }]);
    }

    try {
      await streamQuickLog(
        mode,
        day,
        { parts },
        model ?? undefined,
        controller.signal,
        handleStep,
      );
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      const message = err instanceof Error ? err.message : String(err);
      setSteps((prev) => [...prev, { type: "error", text: message }]);
    } finally {
      setIsLoading(false);
      abortRef.current = null;
      streamingContentRef.current = "";
    }
  };

  const handleImageSelect = async (file: File) => {
    if (isLoading) return;
    const attachment: PendingAttachment = {
      url: "",
      mime_type: file.type,
      name: file.name,
      isLoading: true,
    };
    setPendingAttachments((prev) => [...prev, attachment]);
    try {
      const { url, mime_type } = await uploadFile(file);
      setPendingAttachments((prev) =>
        prev.map((a) =>
          a === attachment ? { ...a, url, mime_type, isLoading: false } : a,
        ),
      );
    } catch (err) {
      console.error("Upload failed:", err);
      setPendingAttachments((prev) => prev.filter((a) => a !== attachment));
    }
  };

  const handleRecordingStop = useCallback(async () => {
    const attachment = await stopRecording();
    if (!attachment) return;
    const file = new File([attachment.blob], "voice.wav", {
      type: attachment.mime_type,
    });
    const pending: PendingAttachment = {
      url: "",
      mime_type: attachment.mime_type,
      name: "Voice memo",
      isLoading: true,
    };
    setPendingAttachments((prev) => [...prev, pending]);
    try {
      const { url, mime_type } = await uploadFile(file);
      setPendingAttachments((prev) =>
        prev.map((a) =>
          a === pending ? { ...a, url, mime_type, isLoading: false } : a,
        ),
      );
    } catch (err) {
      console.error("Upload failed:", err);
      setPendingAttachments((prev) => prev.filter((a) => a !== pending));
    }
  }, [stopRecording]);

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-h-[85vh] gap-2 overflow-hidden text-base sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {mode === "log" ? "Quick add" : "Edit today"}
          </DialogTitle>
          <DialogDescription>
            {mode === "log"
              ? "What did you eat?"
              : "What should change about today's logs?"}
          </DialogDescription>
        </DialogHeader>

        {steps.length > 0 && (
          <div className="grid max-h-[40vh] min-h-24 content-start gap-4 overflow-y-auto py-2">
            {steps.map((step, i) => (
              <StepDisplay key={i} step={step} />
            ))}
            <div ref={bottomRef} />
          </div>
        )}

        <ChatEditor
          disabled={isLoading}
          text={input}
          onTextChange={setInput}
          onSend={handleTextSubmit}
          onRecordingStart={startRecording}
          onRecordingStop={handleRecordingStop}
          isRecording={isRecording}
          onImageSelect={handleImageSelect}
          pendingAttachments={pendingAttachments}
          onRemoveAttachment={(i) =>
            setPendingAttachments((prev) => prev.filter((_, idx) => idx !== i))
          }
          placeholder={
            mode === "log"
              ? "e.g. 2 eggs and coffee..."
              : "e.g. remove the pasta..."
          }
        />
      </DialogContent>
    </Dialog>
  );
}
