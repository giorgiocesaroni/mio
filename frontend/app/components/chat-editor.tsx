"use client";

import { useRef } from "react";
import { twMerge } from "tailwind-merge";
import { Card } from "./card";
import { Button } from "./button";
import { ArrowUp, MessageCircleMore, Mic, Plus, X } from "lucide-react";

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

export interface PendingAttachment {
  url: string;
  mime_type: string;
  name: string;
}

interface ChatEditorProps extends React.HTMLAttributes<HTMLDivElement> {
  placeholder?: string;
  text: string;
  onTextChange: (text: string) => void;
  onSend?: (text: string) => void;
  disabled?: boolean;
  onRecordingStart?: () => void;
  onRecordingStop?: () => void;
  isRecording?: boolean;
  onImageSelect?: (file: File) => void;
  pendingAttachments?: PendingAttachment[];
  onRemoveAttachment?: (index: number) => void;
  thinking?: boolean;
  onThinkingToggle?: () => void;
}

export const ChatEditor = ({
  className,
  text,
  onTextChange,
  placeholder = "Type a message...",
  onSend,
  disabled = false,
  onRecordingStart,
  onRecordingStop,
  isRecording = false,
  onImageSelect,
  pendingAttachments = [],
  onRemoveAttachment,
  thinking = false,
  onThinkingToggle,
  children,
  ...props
}: ChatEditorProps) => {
  const imageInputRef = useRef<HTMLInputElement>(null);
  return (
    <Card
      className={twMerge(
        "w-full border-border rounded-3xl bg-background-alt grid gap-2 p-2 shadow-2xl",
        className,
      )}
    >
      {pendingAttachments.length > 0 && (
        <div className="flex flex-wrap gap-2 px-2 pt-1">
          {pendingAttachments.map((att, i) => (
            <div key={i} className="relative size-16 shrink-0">
              {att.mime_type.startsWith("image/") ? (
                <img
                  src={att.url}
                  alt={att.name}
                  className="size-16 object-cover rounded-xl border border-border"
                />
              ) : (
                <div className="size-16 rounded-xl border border-border bg-muted-background flex items-center justify-center">
                  <Mic className="size-6 text-muted-foreground" />
                </div>
              )}
              <button
                onClick={() => onRemoveAttachment?.(i)}
                className="absolute -top-1.5 -right-1.5 size-4 flex items-center justify-center bg-background border border-border rounded-full text-muted-foreground hover:text-foreground"
                title="Remove"
              >
                <X className="size-2.5" />
              </button>
            </div>
          ))}
        </div>
      )}
      <textarea
        autoFocus={true}
        disabled={disabled}
        className="flex-1 outline-none p-2 field-sizing-content resize-none max-h-[50vh] disabled:opacity-50"
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
          disabled={disabled}
          className="bg-muted-background border-muted-background rounded-full aspect-square py-2 px-2"
          onClick={() => imageInputRef.current?.click()}
          title="Choose an image"
        >
          <Plus className="size-4" />
        </Button>
        <div className="flex-1"></div>
        <Button
          disabled={disabled}
          className={twMerge(
            "rounded-full aspect-square py-2 px-2",
            thinking
              ? "bg-blue-500 border-blue-500 text-white"
              : "bg-muted-background border-muted-background",
          )}
          onClick={onThinkingToggle}
          title={thinking ? "Thinking enabled" : "Thinking disabled"}
        >
          <MessageCircleMore className="size-4" />
        </Button>
        <Button
          className={twMerge(
            "rounded-full aspect-square py-2 px-2 select-none",
            isRecording
              ? "bg-red-500 border-red-500 text-white animate-pulse"
              : "bg-muted-background border-muted-background",
          )}
          disabled={disabled}
          title={isRecording ? "Stop recording" : "Record voice memo"}
          onClick={isRecording ? onRecordingStop : onRecordingStart}
        >
          <Mic className="size-4" />
        </Button>
        <Button
          disabled={disabled || (!text && pendingAttachments.length === 0)}
          className="bg-red-500 text-background-alt rounded-full aspect-square py-2 px-2"
          onClick={() => onSend?.(text)}
        >
          <ArrowUp className="size-4" />
        </Button>
      </div>
    </Card>
  );
};
