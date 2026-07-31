"use client";

import { getModels, getUsage } from "@/repository/backend/queries";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/app/components/button";
import { Card, CardHeader } from "@/app/components/card";
import { H1, P } from "@/app/components/typography";

const EXTRA_MODEL_NAMES: Record<string, string> = {
  "gemini-3.1-flash-lite": "Gemini 3.1 Flash Lite (transcription)",
};

function formatCost(cost: number): string {
  return `$${cost.toFixed(4)}`;
}

function formatTokens(tokens: number): string {
  return tokens.toLocaleString();
}

export default function UsagePage() {
  const router = useRouter();
  const { data: usage } = useQuery({
    queryKey: ["usage"],
    queryFn: getUsage,
  });
  const { data: modelsData } = useQuery({
    queryKey: ["models"],
    queryFn: getModels,
    staleTime: Infinity,
  });

  const modelNames = new Map(
    (modelsData?.models ?? []).map((m) => [m.id, m.name]),
  );

  return (
    <div className="grid gap-8 p-4">
      <header className="flex items-center gap-2">
        <Button
          className="bg-red-500 border-red-500 text-background-alt aspect-square px-2 py-2 rounded-full"
          onClick={() => router.push("/dashboard")}
        >
          <ArrowLeft className="size-4" />
        </Button>
        <H1 className="text-xl md:text-xl">Usage</H1>
      </header>

      {usage && (
        <Card>
          <CardHeader>
            <P>Total</P>
          </CardHeader>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div>
              <P className="text-sm">Cost</P>
              <P className="text-foreground font-medium">
                {formatCost(usage.total.total_cost)}
              </P>
            </div>
            <div>
              <P className="text-sm">Messages</P>
              <P className="text-foreground font-medium">
                {usage.total.total_invocations.toLocaleString()}
              </P>
            </div>
            <div>
              <P className="text-sm">Cost/message</P>
              <P className="text-foreground font-medium">
                {formatCost(
                  usage.total.total_cost / usage.total.total_invocations,
                )}
              </P>
            </div>
            <div>
              <P className="text-sm">Input tokens</P>
              <P className="text-foreground font-medium">
                {formatTokens(usage.total.prompt_tokens)}
              </P>
            </div>
            <div>
              <P className="text-sm">Output tokens</P>
              <P className="text-foreground font-medium">
                {formatTokens(usage.total.completion_tokens)}
              </P>
            </div>
          </div>
        </Card>
      )}

      <div className="grid gap-4">
        {usage?.models.map((m) => {
          const name =
            modelNames.get(m.model_id) ??
            EXTRA_MODEL_NAMES[m.model_id] ??
            m.model_id;
          return (
            <Card key={m.model_id}>
              <CardHeader>
                <P className="font-medium text-foreground">{name}</P>
              </CardHeader>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                <div>
                  <P className="text-sm">Cost</P>
                  <P className="text-foreground font-medium">
                    {formatCost(m.total_cost)}
                  </P>
                </div>
                <div>
                  <P className="text-sm">Messages</P>
                  <P className="text-foreground font-medium">
                    {m.invocations.toLocaleString()}
                  </P>
                </div>
                <div>
                  <P className="text-sm">Cost/message</P>
                  <P className="text-foreground font-medium">
                    {formatCost(m.cost_per_message)}
                  </P>
                </div>
                <div>
                  <P className="text-sm">Input tokens</P>
                  <P className="text-foreground font-medium">
                    {formatTokens(
                      m.uncached_input_tokens + m.cached_input_tokens,
                    )}
                  </P>
                </div>
                <div>
                  <P className="text-sm">Output tokens</P>
                  <P className="text-foreground font-medium">
                    {formatTokens(m.output_tokens)}
                  </P>
                </div>
              </div>
            </Card>
          );
        })}
        {usage && usage.models.length === 0 && (
          <Card>
            <P>No LLM invocations yet.</P>
          </Card>
        )}
      </div>
    </div>
  );
}
