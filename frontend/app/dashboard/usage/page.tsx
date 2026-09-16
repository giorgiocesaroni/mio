"use client";

import { getModels, getUsage } from "@/repository/backend/queries";
import { useQuery } from "@tanstack/react-query";
import { PageTitle } from "@/app/dashboard/components/page-title";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

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
    <div className="grid gap-8">
      <header className="flex items-center gap-2">
        <PageTitle>Usage</PageTitle>
      </header>

      {usage && (
        <Card>
          <CardHeader>
            <CardTitle>Total</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-4 md:grid-cols-5">
            <div>
              <p className="font-sans text-sm text-muted-foreground">Cost</p>
              <p className="font-medium text-foreground">
                {formatCost(usage.total.total_cost)}
              </p>
            </div>
            <div>
              <p className="font-sans text-sm text-muted-foreground">
                Messages
              </p>
              <p className="font-medium text-foreground">
                {usage.total.total_invocations.toLocaleString()}
              </p>
            </div>
            <div>
              <p className="font-sans text-sm text-muted-foreground">
                Cost/message
              </p>
              <p className="font-medium text-foreground">
                {formatCost(
                  usage.total.total_cost / usage.total.total_invocations,
                )}
              </p>
            </div>
            <div>
              <p className="font-sans text-sm text-muted-foreground">
                Input tokens
              </p>
              <p className="font-medium text-foreground">
                {formatTokens(usage.total.prompt_tokens)}
              </p>
            </div>
            <div>
              <p className="font-sans text-sm text-muted-foreground">
                Output tokens
              </p>
              <p className="font-medium text-foreground">
                {formatTokens(usage.total.completion_tokens)}
              </p>
            </div>
          </CardContent>
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
                <CardTitle className="text-base">{name}</CardTitle>
                <CardDescription>{m.model_id}</CardDescription>
              </CardHeader>
              <CardContent className="grid grid-cols-2 gap-4 md:grid-cols-5">
                <div>
                  <p className="font-sans text-sm text-muted-foreground">
                    Cost
                  </p>
                  <p className="font-medium text-foreground">
                    {formatCost(m.total_cost)}
                  </p>
                </div>
                <div>
                  <p className="font-sans text-sm text-muted-foreground">
                    Messages
                  </p>
                  <p className="font-medium text-foreground">
                    {m.invocations.toLocaleString()}
                  </p>
                </div>
                <div>
                  <p className="font-sans text-sm text-muted-foreground">
                    Cost/message
                  </p>
                  <p className="font-medium text-foreground">
                    {formatCost(m.cost_per_message)}
                  </p>
                </div>
                <div>
                  <p className="font-sans text-sm text-muted-foreground">
                    Input tokens
                  </p>
                  <p className="font-medium text-foreground">
                    {formatTokens(
                      m.uncached_input_tokens + m.cached_input_tokens,
                    )}
                  </p>
                </div>
                <div>
                  <p className="font-sans text-sm text-muted-foreground">
                    Output tokens
                  </p>
                  <p className="font-medium text-foreground">
                    {formatTokens(m.output_tokens)}
                  </p>
                </div>
              </CardContent>
            </Card>
          );
        })}
        {usage && usage.models.length === 0 && (
          <Card>
            <CardContent>
              <p className="font-sans text-muted-foreground">
                No LLM invocations yet.
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
