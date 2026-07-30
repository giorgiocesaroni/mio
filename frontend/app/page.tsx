"use client";

import { Brain, Code, Globe, Heart, Key } from "lucide-react";
import { H1, P } from "./components/typography";
import { Logo } from "./components/logo";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "./components/card";
import { ChatChip, ChatEditor } from "./components/chat-editor";
import { useState } from "react";

export default function Home() {
  const [text, setText] = useState("");
  return (
    <div className="mx-auto max-w-5xl font-sans md:p-12 p-6 grid content-center gap-16 min-h-screen">
      <section className="flex flex-col gap-8 items-center text-center">
        <Logo className="bg-red-500" />
        <H1>Effortless food tracking.</H1>
        <P className="max-w-lg md:text-lg">
          With Mio, you can easily track your food intake with voice, text, and
          images. The agent handles searching, refining, and logging foods for
          you. Powered by MiMo, open source, BYOK.
        </P>
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
          <ChatChip className="hidden sm:flex">
            <Brain className="size-4 text-blue-500 shrink-0" />
            <span className="truncate">MiMo v2.5</span>
          </ChatChip>
          <ChatChip>
            <Globe className="size-4 text-blue-500 shrink-0" />
            <span className="truncate">Search</span>
          </ChatChip>
        </ChatEditor>
      </section>

      <section className="grid md:grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <Brain className="size-4 text-muted-foreground" />
            <CardTitle>Powered by MiMo</CardTitle>
          </CardHeader>
          <CardDescription>
            MiMo's intelligence handles the heavy lifting of nutrition tracking.
          </CardDescription>
        </Card>
        <Card>
          <CardHeader>
            <Code className="size-4 text-muted-foreground" />
            <CardTitle>Open source</CardTitle>
          </CardHeader>
          <CardDescription>
            The code is accessible on GitHub. The product is free, forever.
          </CardDescription>
        </Card>
        <Card>
          <CardHeader>
            <Key className="size-4 text-muted-foreground" />
            <CardTitle>BYOK</CardTitle>
          </CardHeader>
          <CardDescription>
            Bring your own MiMo API key to start. Cheap and intelligent.
          </CardDescription>
        </Card>
      </section>
      <section>
        <a href="https://www.giorgiocesaroni.com" target="_blank">
          <P className="text-sm flex items-center gap-1 justify-center">
            Crafted with <Heart className="size-4 stroke-0 fill-red-500" /> by
            Giorgio
          </P>
        </a>
      </section>
    </div>
  );
}
