"use client";

import { useParams } from "next/navigation";
import { DashboardPage } from "@/app/dashboard/components/dashboard-page";
import { ChatThread } from "../components/chat-thread";

export default function ChatPage() {
  const params = useParams();
  const rawId = params.id as string;

  return (
    <DashboardPage title="Chat" bodyClassName="flex flex-col text-sm">
      <ChatThread
        conversationId={rawId === "new" ? null : rawId}
        // Shallow routing
        onStart={(id) =>
          window.history.pushState(null, "", `/dashboard/chat/${id}`)
        }
      />
    </DashboardPage>
  );
}
