"use client";

import { Card } from "@/app/components/card";
import {
  ChatEditor,
  type PendingAttachment,
} from "@/app/components/chat-editor";
import { H1, P } from "@/app/components/typography";
import { useAudioRecorder } from "@/app/hooks/use-audio-recorder";
import { readFileAsBase64 } from "@/app/lib/utils";
import {
  type RunAgentStep,
  getConversationMessages,
  streamChat,
} from "@/repository/backend/queries";
import { useQuery } from "@tanstack/react-query";
import { Cog } from "lucide-react";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { v4 } from "uuid";
import { MessageContent } from "../components/message-content";
import { useChatLoading } from "../layout";

function getGreeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "What are you eating for breakfast?";
  if (hour < 18) return "What are your plans for the day?";
  return "Good evening. How was your day?";
}

function StepDisplay({ step }: { step: RunAgentStep }) {
  if (step.type === "user_message") {
    return (
      <Card className={`justify-self-end px-4 py-2`}>
        {step.data ? (
          <div className="space-y-2">
            {/* <p className="text-sm text-green-700">{step.text}</p> */}
            {step.mime_type?.startsWith("image/") ? (
              <img
                src={`data:${step.mime_type};base64,${step.data}`}
                alt="User image"
                className="max-w-24 max-h-24 object-cover rounded-lg"
              />
            ) : step.mime_type?.startsWith("audio/") ? (
              <audio
                controls
                src={`data:${step.mime_type};base64,${step.data}`}
                className="min-w-32 max-w-full"
              />
            ) : null}
          </div>
        ) : (
          step.text
        )}
      </Card>
    );
  }
  if (step.type === "tool_call") {
    return (
      <div className="flex items-center gap-2 text-muted-foreground">
        <Cog className="size-4" /> <P className="font-serif">{step.name}...</P>
      </div>
    );
  }
  return (
    <div className="pr-8">
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

  const sendMessage = useCallback(
    async (id: string, payload: object) => {
      setIsLoading(true);
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        await streamChat(id, payload, controller.signal, (step) =>
          setSteps((prev) => [...prev, step]),
        );
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        console.error("Stream error:", err);
      } finally {
        setIsLoading(false);
        abortRef.current = null;
      }
    },
    [setIsLoading],
  );

  const { isFetching: isFetchingHistory, data: historyData } = useQuery({
    queryKey: ["messages", rawId],
    queryFn: () => getConversationMessages(rawId),
    enabled: !isNew,
    refetchOnWindowFocus: false,
  });

  useEffect(() => {
    if (historyData && historyData.length > 0) setSteps(historyData);
  }, [historyData]);

  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [steps]);

  const handleTextSubmit = async (str: string) => {
    debugger;
    if (
      (!str.trim() && pendingAttachments.length === 0) ||
      isLoading ||
      isFetchingHistory
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
      parts.push({ data: att.data, mime_type: att.mime_type });

    // For the step display, show the first attachment if any (existing StepDisplay handles one)
    if (attachments.length > 0) {
      // Emit one step per attachment, plus a text step if present
      if (text)
        setSteps((prev) => [...prev, { type: "user_message" as const, text }]);
      for (const att of attachments)
        setSteps((prev) => [
          ...prev,
          {
            type: "user_message" as const,
            text: att.name,
            data: att.data,
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
    const base64 = await readFileAsBase64(file);
    setPendingAttachments((prev) => [
      ...prev,
      { data: base64, mime_type: file.type, name: file.name },
    ]);
  };

  const handleRecordingStart = useCallback(() => {
    startRecording();
  }, [startRecording]);

  const handleRecordingStop = useCallback(
    async (autoSend: boolean) => {
      const attachment = await stopRecording();
      if (!attachment) return;
      let id = conversationId;
      if (autoSend) {
        if (!id) {
          id = v4();
          window.history.pushState(null, "", `/dashboard/chat/${id}`);
          setConversationId(id);
        }

        const text = input.trim();
        const images = pendingAttachments;
        const allAttachments = [
          ...images,
          {
            data: attachment.data,
            mime_type: attachment.mime_type,
            name: "Voice memo",
          },
        ];

        setInput("");
        setPendingAttachments([]);

        const parts: object[] = [];
        if (text) parts.push({ text });
        for (const att of allAttachments)
          parts.push({ data: att.data, mime_type: att.mime_type });

        if (text)
          setSteps((prev) => [
            ...prev,
            { type: "user_message" as const, text },
          ]);
        for (const att of allAttachments)
          setSteps((prev) => [
            ...prev,
            {
              type: "user_message" as const,
              text: att.name,
              data: att.data,
              mime_type: att.mime_type,
            },
          ]);

        await sendMessage(id, { parts });
      } else {
        setPendingAttachments((prev) => [
          ...prev,
          {
            data: attachment.data,
            mime_type: attachment.mime_type,
            name: "Voice memo",
          },
        ]);
      }
    },
    [
      stopRecording,
      conversationId,
      isNew,
      input,
      pendingAttachments,
      sendMessage,
    ],
  );

  return (
    <div className="flex flex-col flex-1">
      <div
        className={`flex-1 ${steps.length === 0 ? "flex items-center justify-center" : "grid gap-4 p-4 content-start"}`}
      >
        {steps.length === 0 ? (
          <H1 className="md:text-2xl text-2xl text-muted-foreground">
            {getGreeting()}
          </H1>
        ) : (
          steps.map((step, i) => <StepDisplay key={i} step={step} />)
        )}
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
        ></ChatEditor>
      </div>
    </div>
  );
}
