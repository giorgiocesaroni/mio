"use client";

import { twMerge } from "tailwind-merge";
import { Card } from "./card";
import { Button } from "./button";
import { ArrowUp, Mic, Plus } from "lucide-react";

interface ChatEditorProps extends React.HTMLAttributes<HTMLDivElement> {
  placeholder?: string;
  text: string;
  onTextChange: (text: string) => void;
  onSend?: (text: string) => void;
}

export const ChatEditor = ({
  className,
  text,
  onTextChange,
  placeholder = "Type a message...",
  onSend,
  children,
  ...props
}: ChatEditorProps) => {
  console.debug({ text });
  return (
    <Card
      className={twMerge(
        "w-full border-border rounded-3xl bg-background-alt grid gap-2 p-2 shadow-2xl",
        className,
      )}
    >
      <input
        className="flex-1 outline-none p-2 h-fit"
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
        <Button className="bg-muted-background border-muted-background rounded-full aspect-square py-2 px-2">
          <Plus className="size-4" />
        </Button>
        <Button className="bg-muted-background border-muted-background rounded-full aspect-square py-2 px-2">
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
