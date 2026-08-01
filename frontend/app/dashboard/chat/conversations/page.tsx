"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { getConversations } from "@/repository/supabase/queries";
import { Button } from "@/app/components/button";
import { Card } from "@/app/components/card";
import { H1, P } from "@/app/components/typography";
import { Plus } from "lucide-react";

export default function ConversationsPage() {
  const router = useRouter();

  const { data: conversations, isLoading } = useQuery({
    queryKey: ["getConversations"],
    queryFn: getConversations,
  });

  const startNew = () => router.push("/dashboard/chat/new");

  return (
    <div className="grid gap-8 p-4">
      <div className="flex items-center justify-between">
        <H1 className="text-xl md:text-xl">Conversations</H1>
        <Button
          onClick={startNew}
          className="bg-red-500 border-red-500 text-background-alt aspect-square py-2 px-2 rounded-full"
        >
          <Plus className="size-4" />
        </Button>
      </div>

      <div className="grid gap-3">
        {conversations?.map((conv) => (
          <Card
            key={conv.id}
            onClick={() => router.push(`/dashboard/chat/${conv.id}`)}
            className="flex items-center justify-between gap-4 cursor-pointer hover:bg-muted transition-colors overflow-auto"
          >
            <P className="truncate">{conv.title || "New conversation"}</P>
            <P className="text-sm text-muted-foreground whitespace-nowrap">
              {new Date(conv.created_at).toLocaleDateString(undefined, {
                month: "short",
                day: "numeric",
                hour: "numeric",
                minute: "numeric",
              })}
            </P>
          </Card>
        ))}
      </div>
    </div>
  );
}
