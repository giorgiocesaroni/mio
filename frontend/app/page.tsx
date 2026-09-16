"use client";

import { Brain, Code, Globe, Heart, Key } from "lucide-react";
import { Logo } from "./components/logo";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ChatChip, ChatEditor } from "./components/chat-editor";
import { useState } from "react";

export default function Home() {
  const [text, setText] = useState("");
  return (
    <div className="mx-auto grid min-h-screen max-w-5xl content-center gap-16 p-6 font-sans md:p-12">
      <section className="flex flex-col items-center gap-8 text-center">
        <Logo className="bg-red-500" />
        <h1 className="font-sans text-4xl font-medium tracking-tight md:text-6xl">
          Effortless food tracking.
        </h1>
        <p className="max-w-lg font-sans text-muted-foreground md:text-lg">
          With Mio, you can easily track your food intake with voice, text, and
          images. The agent handles searching, refining, and logging foods for
          you. Powered by MiMo, open source, BYOK.
        </p>
        <ChatEditor
          className="max-w-lg shadow-xl"
          text={text}
          onTextChange={setText}
          placeholder="Type what you ate..."
          onSend={(text) => {
            console.debug("Send", { text });
            setText("");
          }}
        >
          <ChatChip className="hidden sm:inline-flex">
            <Brain className="size-4 shrink-0 text-blue-500" />
            <span className="truncate">MiMo v2.5</span>
          </ChatChip>
          <ChatChip>
            <Globe className="size-4 shrink-0 text-blue-500" />
            <span className="truncate">Search</span>
          </ChatChip>
        </ChatEditor>
      </section>

      <section className="grid gap-6 md:grid-cols-3">
        <Card>
          <CardHeader>
            <Brain className="size-4 text-muted-foreground" />
            <CardTitle>Powered by MiMo</CardTitle>
            <CardDescription>
              MiMo&apos;s intelligence handles the heavy lifting of nutrition
              tracking.
            </CardDescription>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <Code className="size-4 text-muted-foreground" />
            <CardTitle>Open source</CardTitle>
            <CardDescription>
              The code is accessible on GitHub. The product is free, forever.
            </CardDescription>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <Key className="size-4 text-muted-foreground" />
            <CardTitle>BYOK</CardTitle>
            <CardDescription>
              Bring your own MiMo API key to start. Cheap and intelligent.
            </CardDescription>
          </CardHeader>
        </Card>
      </section>
      <section>
        <a href="https://www.giorgiocesaroni.com" target="_blank">
          <p className="flex items-center justify-center gap-1 font-sans text-sm text-muted-foreground">
            Crafted with <Heart className="size-4 fill-red-500 stroke-0" /> by
            Giorgio
          </p>
        </a>
      </section>
    </div>
  );
}
