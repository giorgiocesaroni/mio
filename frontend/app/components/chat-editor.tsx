"use client";

import { useRef } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ArrowUp, Check, Loader2, Mic, Plus, X } from "lucide-react";

export const ChatChip = ({
  className,
  children,
  ...props
}: React.ComponentProps<typeof Button>) => (
  <Button
    variant="secondary"
    size="sm"
    className={cn("rounded-full font-normal", className)}
    {...props}
  >
    {children}
  </Button>
);

export interface PendingAttachment {
  url: string;
  mime_type: string;
  name: string;
  isLoading?: boolean;
}

interface ChatEditorProps extends React.HTMLAttributes<HTMLDivElement> {
  placeholder?: string;
  text: string;
  onTextChange: (text: string) => void;
  onSend?: (text: string) => void;
  disabled?: boolean;
  isSending?: boolean;
  autoFocus?: boolean;
  onRecordingStart?: () => void;
  onRecordingStop?: () => void;
  isRecording?: boolean;
  isTranscribing?: boolean;
  isSent?: boolean;
  onImageSelect?: (file: File) => void;
  pendingAttachments?: PendingAttachment[];
  onRemoveAttachment?: (index: number) => void;
  modelSelector?: React.ReactNode;
}

export const ChatEditor = ({
  className,
  text,
  onTextChange,
  placeholder = "Type a message...",
  onSend,
  disabled = false,
  isSending = false,
  autoFocus = true,
  onRecordingStart,
  onRecordingStop,
  isRecording = false,
  isTranscribing = false,
  isSent = false,
  onImageSelect,
  pendingAttachments = [],
  onRemoveAttachment,
  modelSelector,
  children,
  ...props
}: ChatEditorProps) => {
  const imageInputRef = useRef<HTMLInputElement>(null);
  return (
    <div
      className={cn(
        "grid w-full gap-2 rounded-xl bg-card p-2 text-card-foreground ring-1 ring-foreground/10",
        className,
      )}
      {...props}
    >
      {pendingAttachments.length > 0 && (
        <div className="flex flex-wrap gap-2 px-2 pt-1">
          {pendingAttachments.map((att, i) => (
            <div key={i} className="relative size-16 shrink-0">
              {att.isLoading ? (
                <div className="flex size-16 items-center justify-center rounded-xl border bg-muted">
                  <Loader2 className="size-6 animate-spin text-muted-foreground" />
                </div>
              ) : att.mime_type.startsWith("image/") ? (
                <img
                  src={att.url}
                  alt={att.name}
                  className="size-16 rounded-xl border object-cover"
                />
              ) : (
                <div className="flex size-16 items-center justify-center rounded-xl border bg-muted">
                  <Mic className="size-6 text-muted-foreground" />
                </div>
              )}
              <Button
                variant="outline"
                size="icon-xs"
                onClick={() => onRemoveAttachment?.(i)}
                className="absolute -top-1.5 -right-1.5 size-5 rounded-full bg-background"
                title="Remove"
              >
                <X className="size-2.5" />
              </Button>
            </div>
          ))}
        </div>
      )}
      <textarea
        autoFocus={autoFocus}
        disabled={disabled}
        className="max-h-[50vh] flex-1 resize-none field-sizing-content p-2 text-sm outline-none disabled:opacity-50"
        placeholder={placeholder}
        value={text}
        onChange={(e) => onTextChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
            e.preventDefault();
            onSend?.(text);
          }
        }}
      />
      <div className="flex items-center gap-2 px-1 pb-1">
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
          variant="secondary"
          size="icon"
          disabled={disabled}
          className="rounded-full"
          onClick={() => imageInputRef.current?.click()}
          title="Choose an image"
        >
          <Plus className="size-4" />
        </Button>
        <div className="flex-1"></div>
        {modelSelector}
        <Button
          variant="secondary"
          size="icon"
          className={cn(
            "rounded-full select-none",
            isRecording && "animate-pulse bg-red-500 text-white hover:bg-red-600",
          )}
          disabled={disabled}
          title={
            isRecording
              ? "Stop recording"
              : isTranscribing
                ? "Transcribing…"
                : "Record voice memo"
          }
          onClick={isRecording ? onRecordingStop : onRecordingStart}
        >
          {isTranscribing ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <Mic className="size-4" />
          )}
        </Button>
        <Button
          size="icon"
          disabled={
            disabled ||
            isSending ||
            (!text && pendingAttachments.length === 0) ||
            pendingAttachments.some((a) => a.isLoading)
          }
          className={cn(
            "rounded-full text-white",
            isSent
              ? "bg-green-500 hover:bg-green-600"
              : "bg-red-500 hover:bg-red-600",
          )}
          onClick={() => onSend?.(text)}
        >
          {isSending ? (
            <Loader2 className="size-4 animate-spin" />
          ) : isSent ? (
            <Check className="size-4" />
          ) : (
            <ArrowUp className="size-4" />
          )}
        </Button>
      </div>
    </div>
  );
};
