"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { MessageContent } from "../components/message-content";
import { ArrowLeft, Cog } from "lucide-react";
import { Button } from "@/app/components/button";
import { ChatEditor } from "@/app/components/chat-editor";
import { Card } from "@/app/components/card";
import { P } from "@/app/components/typography";

type ToolCallStep = {
  type: "tool_call";
  name: string;
  args: Record<string, unknown>;
};

type MessageStep = {
  type: "message";
  text: string;
};

type UserMessageStep = {
  type: "user_message";
  text: string;
  data?: string;
  mime_type?: string;
};

type RunAgentStep = ToolCallStep | MessageStep | UserMessageStep;

function StepDisplay({ step }: { step: RunAgentStep }) {
  if (step.type === "user_message") {
    return (
      <Card className={`justify-self-end px-4 py-2`}>
        {step.data ? (
          <div className="space-y-2">
            <p className="text-sm text-green-700">{step.text}</p>
            {step.mime_type?.startsWith("image/") ? (
              <img
                src={`data:${step.mime_type};base64,${step.data}`}
                alt="User image"
                className="max-w-full rounded-lg"
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
  const imageInputRef = useRef<HTMLInputElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async (payload: object) => {
      setIsLoading(true);
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_BACKEND_URL}/chat`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              conversation_id: conversationId,
              message: payload,
            }),
            signal: controller.signal,
          },
        );

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const reader = response.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split("\n\n");
          buffer = parts.pop() || "";

          for (const part of parts) {
            if (!part.startsWith("data: ")) continue;
            try {
              const step = parseStep(JSON.parse(part.slice(6)));
              if (step && step.type !== "user_message") {
                setSteps((prev) => [...prev, step]);
              }
            } catch {
              // skip malformed events
            }
          }
        }
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
    fetch(
      `${process.env.NEXT_PUBLIC_BACKEND_URL}/conversations/${conversationId}/messages`,
    )
      .then((res) => {
        if (!res.ok) throw new Error("Failed to fetch history");
        return res.json();
      })
      .then((data: RunAgentStep[]) => setSteps(data))
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

      <div className="flex-1 grid gap-4 p-4 content-start">
        {steps.map((step, i) => (
          <StepDisplay key={i} step={step} />
        ))}
        <div ref={bottomRef} />
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
