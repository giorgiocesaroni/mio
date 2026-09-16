"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { getConversations } from "@/repository/supabase/queries";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { getElapsedTime } from "@/app/utils";
import { PageTitle } from "@/app/dashboard/components/page-title";
import { Plus } from "lucide-react";

export default function ConversationsPage() {
  const router = useRouter();

  const { data: conversations, isLoading } = useQuery({
    queryKey: ["getConversations"],
    queryFn: getConversations,
  });

  const startNew = () => router.push("/dashboard/chat/new");

  return (
    <div className="grid gap-8">
      <div className="flex items-center justify-between">
        <PageTitle>Conversations</PageTitle>
        <Button
          size="icon"
          onClick={startNew}
          className="rounded-full bg-red-500 text-white hover:bg-red-600"
        >
          <Plus className="size-4" />
        </Button>
      </div>

      <div className="grid gap-3">
        {isLoading &&
          [0, 1, 2].map((i) => <Skeleton key={i} className="h-14 w-full" />)}
        {conversations?.map((conv) => (
          <Card
            key={conv.id}
            onClick={() => router.push(`/dashboard/chat/${conv.id}`)}
            className="cursor-pointer py-3 transition-colors hover:bg-muted/50"
          >
            <CardContent className="flex items-center justify-between gap-4 overflow-auto">
              <p className="truncate font-sans">
                {conv.title || "New conversation"}
              </p>
              <p className="font-sans text-sm whitespace-nowrap text-muted-foreground">
                {getElapsedTime(conv.created_at)}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
