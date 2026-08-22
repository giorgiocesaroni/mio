"use client";

import { Card } from "@/app/components/card";
import {
  ChatEditor,
  type PendingAttachment,
} from "@/app/components/chat-editor";
import { H1, P } from "@/app/components/typography";
import { useAudioRecorder } from "@/app/hooks/use-audio-recorder";
import {
  type RunAgentStep,
  getConversationMessages,
  getModels,
  streamChat,
  uploadFile,
} from "@/repository/backend/queries";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle, Cog, Loader2 } from "lucide-react";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { v4 } from "uuid";
import { MessageContent } from "../components/message-content";
import { useChatLoading } from "../layout";

function getGreeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "What's for breakfast?";
  if (hour < 18) return "Any foods for the day?";
  return "What did you eat today?";
}

function StepDisplay({ step }: { step: RunAgentStep }) {
  if (step.type === "user_message") {
    if (step.data?.startsWith("data:image/") || step.mime_type?.startsWith("image/")) {
      return (
        <img
          src={step.data}
          alt="User image"
          className="ml-8 justify-self-end max-w-24 max-h-24 object-cover rounded-lg"
        />
      );
    }
    if (step.mime_type?.startsWith("audio/") || step.mime_type === "url") {
      return (
        <audio
          controls
          src={step.data}
          className="ml-8 justify-self-end min-w-32 max-w-full"
        />
      );
    }
    return <Card className={`ml-8 justify-self-end px-4 py-2`}>{step.text}</Card>;
  }
  if (step.type === "tool_call") {
    return (
      <div className="flex items-center gap-2 text-muted-foreground">
        <Cog className="size-4" /> <P className="font-serif">{step.name}</P>
      </div>
    );
  }
  if (step.type === "tool_call_start") {
    return (
      <div className="flex items-center gap-2 text-muted-foreground animate-pulse">
        <Loader2 className="size-4 animate-spin" />{" "}
        <P className="font-serif">{step.name}...</P>
      </div>
    );
  }
  if (step.type === "content_token") {
    return (
      <div className="overflow-auto">
        <MessageContent text={step.token} />
      </div>
    );
  }
  if (step.type === "error") {
    return (
      <div className="flex items-start gap-2 rounded-lg border border-red-500/50 bg-red-500/10 p-3 text-red-700">
        <AlertCircle className="size-4 mt-0.5 shrink-0" />
        <P className="font-serif break-words whitespace-pre-wrap">{step.text}</P>
      </div>
    );
  }
  return (
    <div className="overflow-auto">
      <MessageContent text={step.text} />
    </div>
  );
}

export default function Home() {
  const params = useParams();
  const rawId = params.id as string;
  const isNew = rawId === "new";
  const [conversationId, setConversationId] = useState<string | null>(
    isNew ? null : rawId,
  );
  const [input, setInput] = useState("");
  const [steps, setSteps] = useState<RunAgentStep[]>([]);
  const { isLoading, setIsLoading } = useChatLoading();
  const bottomRef = useRef<HTMLDivElement>(null);
  const { isRecording, startRecording, stopRecording } = useAudioRecorder();
  const [pendingAttachments, setPendingAttachments] = useState<
    PendingAttachment[]
  >([]);
  const abortRef = useRef<AbortController | null>(null);
  const streamingContentRef = useRef<string>("");
  const streamingTokenCountRef = useRef<number>(0);
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

  const sendMessage = useCallback(
    async (id: string, payload: object) => {
      setIsLoading(true);
      setSteps((prev) => prev.filter((s) => s.type !== "error"));
      const controller = new AbortController();
      abortRef.current = controller;
      streamingContentRef.current = "";
      streamingTokenCountRef.current = 0;

      try {
        await streamChat(
          id,
          payload,
          resolvedModel,
          controller.signal,
          (step) => {
            if (step.type === "content_token") {
              streamingContentRef.current += step.token;
              streamingTokenCountRef.current++;
              setSteps((prev) => {
                const last = prev[prev.length - 1];
                if (last?.type === "content_token") {
                  return [
                    ...prev.slice(0, -1),
                    {
                      type: "content_token",
                      token: streamingContentRef.current,
                    },
                  ];
                }
                return [
                  ...prev,
                  { type: "content_token", token: streamingContentRef.current },
                ];
              });
            } else if (step.type === "tool_call_start") {
              streamingContentRef.current = "";
              streamingTokenCountRef.current = 0;
              setSteps((prev) => [...prev, step]);
            } else if (step.type === "tool_call") {
              setSteps((prev) => {
                const filtered = prev.filter(
                  (s) => s.type !== "tool_call_start",
                );
                return [...filtered, step];
              });
            } else if (step.type === "message") {
              setSteps((prev) => {
                const filtered = prev.filter((s) => s.type !== "content_token");
                return [...filtered, step];
              });
              streamingContentRef.current = "";
              streamingTokenCountRef.current = 0;
            } else {
              setSteps((prev) => [...prev, step]);
            }
          },
        );
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        const message = err instanceof Error ? err.message : String(err);
        console.error("Stream error:", err);
        setSteps((prev) => [...prev, { type: "error", text: message }]);
      } finally {
        setIsLoading(false);
        abortRef.current = null;
        streamingContentRef.current = "";
        streamingTokenCountRef.current = 0;
      }
    },
    [setIsLoading, resolvedModel],
  );

  const { isFetching: isFetchingHistory, data: historyData } = useQuery({
    queryKey: ["messages", rawId],
    queryFn: () => getConversationMessages(rawId),
    enabled: !isNew,
    refetchOnWindowFocus: false,
  });

  useEffect(() => {
    if (historyData && historyData.length > 0) {
      setSteps((prev) => {
        const errors = prev.filter((s) => s.type === "error");
        return [...historyData, ...errors];
      });
    }
  }, [historyData]);

  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [steps]);

  const handleTextSubmit = async (str: string) => {
    if (
      (!str.trim() && pendingAttachments.length === 0) ||
      isLoading ||
      isFetchingHistory ||
      pendingAttachments.some((a) => a.isLoading)
    )
      return;

    let id = conversationId;

    if (!id) {
      id = v4();
      // Shallow routing
      window.history.pushState(null, "", `/dashboard/chat/${id}`);
      setConversationId(id);
    }

    const text = str.trim();
    setInput("");
    const attachments = pendingAttachments;
    setPendingAttachments([]);

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

    await sendMessage(id, { parts });
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

  const handleRecordingStart = useCallback(() => {
    startRecording();
  }, [startRecording]);

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
    <div className="flex flex-col flex-1">
      <div
        className={`flex-1 ${steps.length === 0 ? "flex items-center justify-center" : "grid gap-4 p-4 content-start"}`}
      >
        {steps.length === 0 && (
          <H1 className="md:text-2xl text-2xl text-muted-foreground">
            {isFetchingHistory
              ? "Loading..."
              : historyData
                ? null
                : getGreeting()}
          </H1>
        )}
        {steps.map((step, i) => (
          <StepDisplay key={i} step={step} />
        ))}
        {steps.length > 0 && (
          <div
            ref={bottomRef}
            className={
              "flex transition-colors duration-200 size-4 rounded-full" +
              (isLoading
                ? " bg-red-500 animate-pulse"
                : " bg-border animate-none")
            }
          ></div>
        )}
      </div>

      <div className="p-4 sticky bottom-0">
        <ChatEditor
          disabled={isLoading || (!isNew && isFetchingHistory)}
          text={input}
          onTextChange={(text) => setInput(text)}
          onSend={handleTextSubmit}
          onRecordingStart={handleRecordingStart}
          onRecordingStop={handleRecordingStop}
          isRecording={isRecording}
          onImageSelect={handleImageSelect}
          pendingAttachments={pendingAttachments}
          onRemoveAttachment={(i) =>
            setPendingAttachments((prev) => prev.filter((_, idx) => idx !== i))
          }
          modelSelector={
            modelsData ? (
              <span className="relative inline-block mx-2">
                <span className="invisible text-sm whitespace-nowrap">
                  {modelsData.models.find((m) => m.id === resolvedModel)
                    ?.name ?? ""}
                </span>
                <select
                  aria-label="Model"
                  value={resolvedModel ?? ""}
                  onChange={(e) => handleModelChange(e.target.value)}
                  className="absolute inset-0 appearance-none bg-transparent text-sm text-muted-foreground outline-none cursor-pointer"
                >
                  {modelsData.models.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name}
                    </option>
                  ))}
                </select>
              </span>
            ) : null
          }
        ></ChatEditor>
      </div>
    </div>
  );
}
