"use client";

import { useRef } from "react";
import { twMerge } from "tailwind-merge";
import { Card } from "./card";
import { Button } from "./button";
import { ArrowUp, Mic, Plus } from "lucide-react";

export const ChatChip = ({
  className,
  children,
}: React.HTMLAttributes<HTMLDivElement>) => (
  <Button
    className={twMerge(
      "rounded-full text-sm px-3 border-muted-background bg-muted-background font-normal",
      className,
    )}
  >
    {children}
  </Button>
);

interface ChatEditorProps extends React.HTMLAttributes<HTMLDivElement> {
  placeholder?: string;
  text: string;
  onTextChange: (text: string) => void;
  onSend?: (text: string) => void;
  onAudioCapture?: () => void;
  isRecording?: boolean;
  onImageSelect?: (file: File) => void;
}

export const ChatEditor = ({
  className,
  text,
  onTextChange,
  placeholder = "Type a message...",
  onSend,
  onAudioCapture,
  isRecording = false,
  onImageSelect,
  children,
  ...props
}: ChatEditorProps) => {
  const imageInputRef = useRef<HTMLInputElement>(null);
  console.debug({ text });
  return (
    <Card
      className={twMerge(
        "w-full border-border rounded-3xl bg-background-alt grid gap-2 p-2 shadow-2xl",
        className,
      )}
    >
      <textarea
        autoFocus={true}
        className="flex-1 outline-none p-2 field-sizing-content resize-none max-h-[50vh]"
        placeholder={placeholder}
        value={text}
        onChange={(e) => onTextChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            onSend?.(text);
          }
        }}
      />
      <div className="flex items-center gap-2">
        {children}
        <div className="flex-1"></div>
        <input
          ref={imageInputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) onImageSelect?.(file);
            e.target.value = "";
          }}
        />
        <Button
          className="bg-muted-background border-muted-background rounded-full aspect-square py-2 px-2"
          onClick={() => imageInputRef.current?.click()}
          title="Choose an image"
        >
          <Plus className="size-4" />
        </Button>
        <Button
          className={twMerge(
            "rounded-full aspect-square py-2 px-2",
            isRecording
              ? "bg-red-500 border-red-500 text-white animate-pulse"
              : "bg-muted-background border-muted-background",
          )}
          onClick={onAudioCapture}
          title={isRecording ? "Stop recording" : "Record voice memo"}
        >
          <Mic className="size-4" />
        </Button>
        <Button
          disabled={!text}
          className="bg-red-500 text-background-alt rounded-full aspect-square py-2 px-2"
          onClick={() => onSend?.(text)}
        >
          <ArrowUp className="size-4" />
        </Button>
      </div>
    </Card>
  );
};
