"use client";

import {
  ChatEditor,
  type PendingAttachment,
} from "@/app/components/chat-editor";
import { useAudioRecorder } from "@/app/hooks/use-audio-recorder";
import {
  streamQuickLog,
  transcribeAudio,
  uploadFile,
} from "@/repository/backend/queries";
import { useCallback, useEffect, useRef, useState } from "react";

type Status =
  | { kind: "idle" }
  | { kind: "working" }
  | { kind: "done"; text: string }
  | { kind: "error"; text: string };

export function QuickLogComposer() {
  const [input, setInput] = useState("");
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const [pendingAttachments, setPendingAttachments] = useState<
    PendingAttachment[]
  >([]);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const { isRecording, startRecording, stopRecording } = useAudioRecorder();
  const abortRef = useRef<AbortController | null>(null);
  const resultRef = useRef<{ message?: string; error?: string }>({});

  useEffect(() => () => abortRef.current?.abort(), []);

  const isWorking = status.kind === "working";

  const handleTextSubmit = async (str: string) => {
    if (
      (!str.trim() && pendingAttachments.length === 0) ||
      isWorking ||
      isTranscribing ||
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
    const attachments = pendingAttachments;
    setStatus({ kind: "working" });
    resultRef.current = {};
    const controller = new AbortController();
    abortRef.current = controller;

    const parts: object[] = [];
    if (text) parts.push({ text });
    for (const att of attachments)
      parts.push({ url: att.url, mime_type: att.mime_type });

    try {
      // "edit" covers both cases: it corrects today's logs, and logs
      // as new when nothing matches — so one composer replaces both buttons.
      await streamQuickLog(
        "edit",
        day,
        { parts },
        model,
        controller.signal,
        (step) => {
          // No conversation view: ignore tokens/tool calls, keep only the
          // single final message (or error) to show at the end.
          if (step.type === "message") resultRef.current.message = step.text;
          else if (step.type === "error") resultRef.current.error = step.text;
        },
      );
      const { message, error } = resultRef.current;
      if (error) {
        setStatus({ kind: "error", text: error });
      } else {
        setInput("");
        setPendingAttachments([]);
        setStatus({ kind: "done", text: message ?? "Done." });
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        setStatus({ kind: "idle" });
        return;
      }
      const message = err instanceof Error ? err.message : String(err);
      setStatus({ kind: "error", text: message });
    } finally {
      abortRef.current = null;
    }
  };

  const handleImageSelect = async (file: File) => {
    if (isWorking) return;
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
    setIsTranscribing(true);
    try {
      const { text } = await transcribeAudio(file);
      const transcript = text.trim();
      if (transcript) {
        setInput((prev) => (prev ? `${prev} ${transcript}` : transcript));
      }
    } catch (err) {
      console.error("Transcription failed:", err);
    } finally {
      setIsTranscribing(false);
    }
  }, [stopRecording]);

  return (
    <div className="grid gap-4">
      <ChatEditor
        autoFocus={false}
        disabled={isWorking || isTranscribing}
        isSending={isWorking}
        text={input}
        onTextChange={setInput}
        onSend={handleTextSubmit}
        onRecordingStart={startRecording}
        onRecordingStop={handleRecordingStop}
        isRecording={isRecording}
        isTranscribing={isTranscribing}
        onImageSelect={handleImageSelect}
        pendingAttachments={pendingAttachments}
        onRemoveAttachment={(i) =>
          setPendingAttachments((prev) => prev.filter((_, idx) => idx !== i))
        }
        placeholder="What did you eat? Or fix today's logs…"
      />
      {status.kind !== "idle" && (
        <div
          aria-live="polite"
          className="justify-self-end rounded-xl bg-muted px-4 py-2 text-base break-words"
        >
          {status.kind === "working" && (
            <span className="text-muted-foreground">Logging…</span>
          )}
          {status.kind === "done" && status.text}
          {status.kind === "error" && (
            <span className="text-destructive">{status.text}</span>
          )}
        </div>
      )}
    </div>
  );
}
