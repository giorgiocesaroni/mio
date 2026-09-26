"use client";

import {
  ChatEditor,
  type PendingAttachment,
} from "@/app/components/chat-editor";
import { ModelSelector } from "@/app/components/model-selector";
import { DashboardPage } from "@/app/dashboard/components/dashboard-page";
import { useAudioRecorder } from "@/app/hooks/use-audio-recorder";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  getModels,
  streamSandboxLog,
  transcribeAudio,
  uploadFile,
} from "@/repository/backend/queries";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { DAY_ENTRIES_QUERY_KEY } from "@/app/dashboard/components/day-entries";
import { PendingDrafts } from "@/app/dashboard/components/draft-card";
import { PipelineRun, formatCost, type Run } from "./components/pipeline-run";

// Mirrors the backend's EXTRACT_MODEL_ID default.
const DEFAULT_EXTRACT_MODEL = "google/gemini-3.8-flash";

function todayKey(): string {
  return new Date().toLocaleDateString("en-CA");
}

export default function SandboxPage() {
  const [input, setInput] = useState("");
  const [pendingAttachments, setPendingAttachments] = useState<
    PendingAttachment[]
  >([]);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [day, setDay] = useState(todayKey);
  // Separate from the app-wide "model" preference, so experiments here don't
  // change the model used by quick log and chat.
  const [model, setModel] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem("sandbox-model");
  });
  const [runs, setRuns] = useState<Run[]>([]);
  const abortRef = useRef<AbortController | null>(null);
  const { isRecording, startRecording, stopRecording } = useAudioRecorder();
  const queryClient = useQueryClient();

  const { data: modelsData } = useQuery({
    queryKey: ["models"],
    queryFn: getModels,
    staleTime: Infinity,
  });
  const available = (id: string | null) =>
    !!id && !!modelsData?.models.some((m) => m.id === id);
  const resolvedModel = available(model)
    ? model!
    : available(DEFAULT_EXTRACT_MODEL)
      ? DEFAULT_EXTRACT_MODEL
      : modelsData?.default;

  const isRunning = runs.some((r) => !r.done && !r.error);

  useEffect(() => () => abortRef.current?.abort(), []);

  const updateRun = (id: string, update: (run: Run) => Run) =>
    setRuns((prev) => prev.map((r) => (r.id === id ? update(r) : r)));

  const handleSend = async (str: string) => {
    const text = str.trim();
    if (
      (!text && pendingAttachments.length === 0) ||
      isRunning ||
      isTranscribing ||
      pendingAttachments.some((a) => a.isLoading)
    )
      return;

    const parts: object[] = [];
    if (text) parts.push({ text });
    for (const att of pendingAttachments)
      parts.push({ url: att.url, mime_type: att.mime_type });

    const run: Run = {
      id: crypto.randomUUID(),
      text,
      images: pendingAttachments.map((a) => a.url),
      model: resolvedModel,
      stages: [],
    };
    setRuns((prev) => [run, ...prev]);
    setInput("");
    setPendingAttachments([]);

    const controller = new AbortController();
    abortRef.current = controller;
    try {
      await streamSandboxLog(
        { parts },
        { day, model: resolvedModel },
        controller.signal,
        (step) => {
          if (step.type === "stage")
            updateRun(run.id, (r) => ({ ...r, stages: [...r.stages, step] }));
          else if (step.type === "done")
            updateRun(run.id, (r) => ({ ...r, done: step }));
          else if (step.type === "error")
            updateRun(run.id, (r) => ({ ...r, error: step.text }));
        },
      );
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      const message = err instanceof Error ? err.message : String(err);
      updateRun(run.id, (r) => ({ ...r, error: message }));
    } finally {
      abortRef.current = null;
      await queryClient.invalidateQueries({ queryKey: DAY_ENTRIES_QUERY_KEY });
      // A stream that closed without a final event would otherwise spin forever.
      updateRun(run.id, (r) =>
        r.done || r.error ? r : { ...r, error: "Stream ended unexpectedly." },
      );
    }
  };

  const handleImageSelect = async (file: File) => {
    const id = crypto.randomUUID();
    setPendingAttachments((prev) => [
      ...prev,
      { id, url: "", mime_type: file.type, name: file.name, isLoading: true },
    ]);
    try {
      const { url, mime_type } = await uploadFile(file);
      setPendingAttachments((prev) =>
        prev.map((a) =>
          a.id === id ? { ...a, url, mime_type, isLoading: false } : a,
        ),
      );
    } catch (err) {
      setPendingAttachments((prev) => prev.filter((a) => a.id !== id));
      const message = err instanceof Error ? err.message : String(err);
      toast.error(`Upload failed: ${message}`);
    }
  };

  const handleRecordingStart = useCallback(async () => {
    try {
      await startRecording();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    }
  }, [startRecording]);

  const handleRecordingStop = useCallback(async () => {
    const attachment = await stopRecording();
    if (!attachment) {
      toast.error("No audio was captured. Try recording again.");
      return;
    }
    setIsTranscribing(true);
    try {
      const { text } = await transcribeAudio(
        new File([attachment.blob], "voice", { type: attachment.mime_type }),
      );
      const transcript = text.trim();
      if (transcript)
        setInput((prev) => (prev ? `${prev} ${transcript}` : transcript));
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      toast.error(`Transcription failed: ${message}`);
    } finally {
      setIsTranscribing(false);
    }
  }, [stopRecording]);

  const finished = runs.filter((r) => r.done);
  const averageCost =
    finished.reduce((sum, r) => sum + (r.done?.total_cost ?? 0), 0) /
    (finished.length || 1);

  return (
    <DashboardPage
      title="Sandbox"
      subtitle="Structured logging pipeline prototype: every stage is shown for debugging."
      actions={
        runs.length ? (
          <Button
            variant="ghost"
            size="sm"
            disabled={isRunning}
            onClick={() => setRuns([])}
          >
            Clear
          </Button>
        ) : null
      }
      bodyClassName="gap-6"
    >
      <div className="grid gap-3">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
          <div className="flex items-center gap-2">
            <Label htmlFor="sandbox-day">Day</Label>
            <Input
              id="sandbox-day"
              type="date"
              value={day}
              onChange={(e) => setDay(e.target.value || todayKey())}
              className="h-8 w-auto"
            />
          </div>
          {finished.length ? (
            <span className="ml-auto text-xs tabular-nums text-muted-foreground">
              {finished.length} run{finished.length === 1 ? "" : "s"} · avg{" "}
              {formatCost(averageCost)}
            </span>
          ) : null}
        </div>
        <ChatEditor
          autoFocus
          disabled={isRunning || isTranscribing}
          isSending={isRunning}
          text={input}
          onTextChange={setInput}
          onSend={handleSend}
          onRecordingStart={handleRecordingStart}
          onRecordingStop={handleRecordingStop}
          isRecording={isRecording}
          isTranscribing={isTranscribing}
          onImageSelect={handleImageSelect}
          pendingAttachments={pendingAttachments}
          onRemoveAttachment={(i) =>
            setPendingAttachments((prev) => prev.filter((_, idx) => idx !== i))
          }
          placeholder="What did you eat?"
          modelSelector={
            modelsData ? (
              <ModelSelector
                models={modelsData.models}
                value={resolvedModel}
                onChange={(value) => {
                  setModel(value);
                  window.localStorage.setItem("sandbox-model", value);
                }}
              />
            ) : null
          }
        />
      </div>
      <PendingDrafts day={day} />
      {runs.map((run) => (
        <PipelineRun key={run.id} run={run} />
      ))}
    </DashboardPage>
  );
}
