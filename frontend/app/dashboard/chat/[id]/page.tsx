"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { MessageContent } from "../components/message-content";
import { ArrowLeft, Cog } from "lucide-react";
import { Button } from "@/app/components/button";
import { ChatEditor } from "@/app/components/chat-editor";
import { Card } from "@/app/components/card";
import { H1, P } from "@/app/components/typography";
import {
  type RunAgentStep,
  getConversationMessages,
  streamChat,
} from "@/repository/backend/queries";

function getGreeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning.";
  if (hour < 18) return "Good afternoon.";
  return "Good evening.";
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

function readFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      const base64 = result.split(",")[1];
      resolve(base64);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

export default function Home() {
  const router = useRouter();
  const params = useParams();
  const conversationId = params.id as string;
  const [input, setInput] = useState("");
  const [steps, setSteps] = useState<RunAgentStep[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async (payload: object) => {
      setIsLoading(true);
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        await streamChat(conversationId, payload, controller.signal, (step) =>
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
    [conversationId],
  );

  useEffect(() => {
    if (!conversationId) return;
    getConversationMessages(conversationId)
      .then((data) => setSteps(data))
      .catch((err) => console.error("Failed to load history:", err));
  }, [conversationId]);

  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [steps]);

  const handleTextSubmit = async (str: string) => {
    if (!str.trim() || isLoading) return;
    const text = str.trim();
    setInput("");
    setSteps((prev) => [...prev, { type: "user_message", text }]);
    await sendMessage({ parts: [{ text }] });
  };

  const handleImageSelect = async (file: File) => {
    if (isLoading) return;
    const base64 = await readFileAsBase64(file);
    setSteps((prev) => [
      ...prev,
      {
        type: "user_message",
        text: file.name,
        data: base64,
        mime_type: file.type,
      },
    ]);
    await sendMessage({ parts: [{ data: base64, mime_type: file.type }] });
  };

  const handleAudioCapture = async () => {
    if (isRecording) {
      mediaRecorderRef.current?.stop();
      setIsRecording(false);
      return;
    }
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mediaRecorder = new MediaRecorder(stream);
    mediaRecorderRef.current = mediaRecorder;
    const chunks: Blob[] = [];
    mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
    mediaRecorder.onstop = async () => {
      if (isLoading) return;
      const blob = new Blob(chunks, { type: mediaRecorder.mimeType });
      const base64 = await readFileAsBase64(
        new File([blob], "voice", { type: mediaRecorder.mimeType }),
      );
      setSteps((prev) => [
        ...prev,
        {
          type: "user_message",
          text: "Voice memo",
          data: base64,
          mime_type: mediaRecorder.mimeType,
        },
      ]);
      await sendMessage({
        parts: [{ data: base64, mime_type: mediaRecorder.mimeType }],
      });
      stream.getTracks().forEach((t) => t.stop());
    };
    mediaRecorder.start();
    setIsRecording(true);
  };

  return (
    <div className="flex flex-col min-h-screen">
      <header className="p-4 sticky top-0">
        <div className="flex items-center gap-2">
          <Button
            className="bg-red-500 border-red-500 text-background-alt aspect-square px-2 py-2 rounded-full"
            onClick={() => router.push("/dashboard")}
          >
            <ArrowLeft className="size-4" />
          </Button>
        </div>
        <span
          className={`size-2 rounded-full ${isLoading ? "bg-amber-500 animate-pulse" : "bg-green-500"}`}
        />
      </header>

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

      {/* <input
        ref={imageInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleImageSelect(file);
          e.target.value = "";
        }}
      /> */}

      <div className="p-4 sticky bottom-0">
        <ChatEditor
          text={input}
          onTextChange={(text) => setInput(text)}
          onSend={handleTextSubmit}
          onAudioCapture={handleAudioCapture}
          isRecording={isRecording}
          onImageSelect={handleImageSelect}
        ></ChatEditor>
      </div>

      {/* {!input.trim() ? (
        <>
          <button
            type="button"
            className="rounded-full size-10 bg-neutral-100 text-neutral-600 flex items-center justify-center cursor-pointer hover:bg-neutral-200 shrink-0 disabled:opacity-50"
            disabled={isLoading}
            onClick={() => imageInputRef.current?.click()}
            title="Choose an image"
          >
            <Image className="size-4" />
          </button>
          <button
            type="button"
            className={`rounded-full size-10 flex items-center justify-center cursor-pointer shrink-0 disabled:opacity-50 ${
              isRecording
                ? "bg-red-500 text-white animate-pulse"
                : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
            }`}
            disabled={isLoading}
            onClick={handleAudioCapture}
            title={isRecording ? "Stop recording" : "Record voice memo"}
          >
            <Mic className="size-4" />
          </button>
        </>
      ) : (
        <button
          type="submit"
          className="rounded-full size-10 bg-green-700 text-white flex items-center justify-center cursor-pointer shrink-0"
          disabled={isLoading}
        >
          ↑
        </button>
      )} */}
    </div>
  );
}
