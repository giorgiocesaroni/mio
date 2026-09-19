"use client";

import {
  ChatEditor,
  type PendingAttachment,
} from "@/app/components/chat-editor";
import { ModelSelector } from "@/app/components/model-selector";
import { useAudioRecorder } from "@/app/hooks/use-audio-recorder";
import {
  getModels,
  streamQuickLog,
  transcribeAudio,
  uploadFile,
} from "@/repository/backend/queries";
import { toast } from "sonner";
import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

export function QuickLogComposer({ day }: { day: string }) {
  const [input, setInput] = useState("");
  const [isWorking, setIsWorking] = useState(false);
  const [isSent, setIsSent] = useState(false);
  const [pendingAttachments, setPendingAttachments] = useState<
    PendingAttachment[]
  >([]);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [model, setModel] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem("model");
  });
  const { data: modelsData } = useQuery({
    queryKey: ["models"],
    queryFn: getModels,
    staleTime: Infinity,
  });
  const resolvedModel =
    model && modelsData?.models.some((m) => m.id === model)
      ? model
      : (modelsData?.default ?? undefined);
  const handleModelChange = (value: string) => {
    setModel(value);
    window.localStorage.setItem("model", value);
  };
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

  const handleTextChange = (value: string) => {
    setInput(value);
    if (isSent) {
      setIsSent(false);
      if (sentTimeoutRef.current) clearTimeout(sentTimeoutRef.current);
    }
  };

  const handleTextSubmit = async (str: string) => {
    if (
      (!str.trim() && pendingAttachments.length === 0) ||
      isWorking ||
      isTranscribing ||
      pendingAttachments.some((a) => a.isLoading)
    )
      return;

    const text = str.trim();
    const attachments = pendingAttachments;
    setIsWorking(true);
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
        resolvedModel,
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
        toast.error(error);
      } else {
        setInput("");
        setPendingAttachments([]);
        toast.success(message ?? "Done.");
        setIsSent(true);
        if (sentTimeoutRef.current) clearTimeout(sentTimeoutRef.current);
        sentTimeoutRef.current = setTimeout(() => setIsSent(false), 10000);
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        return;
      }
      const message = err instanceof Error ? err.message : String(err);
      toast.error(message);
    } finally {
      abortRef.current = null;
      setIsWorking(false);
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
    const file = new File([attachment.blob], "voice", {
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
        modelSelector={
          modelsData ? (
            <ModelSelector
              models={modelsData.models}
              value={resolvedModel}
              onChange={handleModelChange}
            />
          ) : null
        }
      />
    </div>
  );
}
