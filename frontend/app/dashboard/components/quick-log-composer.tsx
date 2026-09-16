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
import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useRef, useState } from "react";

type Feedback =
  | { kind: "working"; text: string }
  | { kind: "success"; text: string }
  | { kind: "error"; text: string };

export function QuickLogComposer() {
  const [input, setInput] = useState("");
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [isSent, setIsSent] = useState(false);
  const [pendingAttachments, setPendingAttachments] = useState<
    PendingAttachment[]
  >([]);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const { isRecording, startRecording, stopRecording } = useAudioRecorder();
  const abortRef = useRef<AbortController | null>(null);
  const sentTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const resultRef = useRef<{ message?: string; error?: string }>({});

  useEffect(
    () => () => {
      abortRef.current?.abort();
      if (sentTimeoutRef.current) clearTimeout(sentTimeoutRef.current);
    },
    [],
  );

  const isWorking = feedback?.kind === "working";

  const handleTextChange = (value: string) => {
    setInput(value);
    if (isSent) {
      setIsSent(false);
      if (sentTimeoutRef.current) clearTimeout(sentTimeoutRef.current);
    }
    if (feedback?.kind !== "working") setFeedback(null);
  };

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
    setFeedback({ kind: "working", text: "Logging…" });
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
        setFeedback({ kind: "error", text: error });
      } else {
        setInput("");
        setPendingAttachments([]);
        setFeedback({ kind: "success", text: message ?? "Done." });
        setIsSent(true);
        if (sentTimeoutRef.current) clearTimeout(sentTimeoutRef.current);
        sentTimeoutRef.current = setTimeout(() => setIsSent(false), 10000);
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        setFeedback(null);
        return;
      }
      const message = err instanceof Error ? err.message : String(err);
      setFeedback({ kind: "error", text: message });
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
        onTextChange={handleTextChange}
        onSend={handleTextSubmit}
        onRecordingStart={startRecording}
        onRecordingStop={handleRecordingStop}
        isRecording={isRecording}
        isTranscribing={isTranscribing}
        isSent={isSent}
        onImageSelect={handleImageSelect}
        pendingAttachments={pendingAttachments}
        onRemoveAttachment={(i) =>
          setPendingAttachments((prev) => prev.filter((_, idx) => idx !== i))
        }
        placeholder="What did you eat? Or fix today's logs…"
      />
      <div className="min-h-16">
        <AnimatePresence initial={false} mode="wait">
          {feedback && (
            <motion.div
              key={`${feedback.kind}:${feedback.text}`}
              aria-live="polite"
              initial={{ opacity: 0, scale: 0.97, filter: "blur(6px)" }}
              animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
              exit={{ opacity: 0, scale: 1.03, filter: "blur(6px)" }}
              transition={{ duration: 0.2, ease: "easeOut" }}
              className="rounded-xl bg-card px-4 py-3 text-sm shadow-sm ring-1 ring-foreground/10 break-words"
            >
              <span
                className={
                  feedback.kind === "error" ? "text-destructive" : undefined
                }
              >
                {feedback.text}
              </span>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
