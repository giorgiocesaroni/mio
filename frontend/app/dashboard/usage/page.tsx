"use client";

import { getModels, getUsage } from "@/repository/backend/queries";
import { useQuery } from "@tanstack/react-query";
import { DashboardPage } from "@/app/dashboard/components/dashboard-page";
import { CompactNumber } from "./components/compact-number";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Bar,
  BarChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const EXTRA_MODEL_NAMES: Record<string, string> = {
  "gemini-3.1-flash-lite": "Gemini 3.1 Flash Lite (transcription)",
  "meta/muse-voice-transcribe-1.0": "Muse Voice Transcribe 1.0 (transcription)",
  "openai/gpt-transcribe": "GPT Transcribe (transcription)",
};

function formatCost(cost: number): string {
  return `$${cost.toFixed(4)}`;
}

function getLastSevenDays() {
  const today = new Date();
  return Array.from({ length: 7 }, (_, index) => {
    const date = new Date(today);
    date.setHours(12, 0, 0, 0);
    date.setDate(today.getDate() - 6 + index);
    return {
      key: date.toISOString().slice(0, 10),
      label: date.toLocaleDateString(undefined, { weekday: "narrow" }),
    };
  });
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
  const days = getLastSevenDays();
  const dailyData = days.map(({ key, label }) => ({
    key,
    label,
    cost: usage?.daily.find((entry) => entry.day === key)?.total_cost ?? 0,
  }));
  const averageSpend = dailyData.reduce((sum, point) => sum + point.cost, 0) / dailyData.length;
  const chartMax = Math.max(...dailyData.map((point) => point.cost), averageSpend, 0.0001);
  const labeledModels = (usage?.models ?? []).filter(
    (model) => Boolean(modelNames.get(model.model_id) ?? EXTRA_MODEL_NAMES[model.model_id]),
  );

  return (
    <DashboardPage title="Usage" bodyClassName="gap-8">

      {usage && (
        <Card>
          <CardHeader>
            <CardTitle>Total</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-4 md:grid-cols-4">
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
              <p className="font-sans text-sm text-muted-foreground">Tokens</p>
              <p className="font-medium text-foreground">
                <CompactNumber value={usage.total.prompt_tokens} /> /{" "}
                <CompactNumber value={usage.total.completion_tokens} />
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {usage && (
        <Card className="h-[17rem]">
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle>7-day spend</CardTitle>
            <span className="text-sm font-normal text-muted-foreground">
              {formatCost(averageSpend)} avg.
            </span>
          </CardHeader>
          <CardContent>
            <div className="h-48 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={dailyData} margin={{ top: 8, right: 0, bottom: 0, left: 0 }}>
                  <XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fontSize: 12 }} />
                  <YAxis
                    orientation="right"
                    width={48}
                    axisLine={false}
                    tickLine={false}
                    domain={[0, chartMax]}
                    tickFormatter={(value) => `$${Number(value).toFixed(2)}`}
                  />
                  <Tooltip
                    formatter={(value) => [formatCost(Number(value)), "Spend"]}
                    cursor={{ fill: "var(--color-muted)" }}
                  />
                  <ReferenceLine
                    y={averageSpend}
                    stroke="#ef4444"
                    strokeWidth={2.5}
                    strokeLinecap="round"
                    label={({ viewBox }) => {
                      const { x, y } = viewBox as { x?: number; y?: number };
                      return (
                        <text
                          x={x ?? 0}
                          y={(y ?? 0) - 6}
                          fill="#ef4444"
                          fontFamily="var(--font-sans)"
                          fontSize={12}
                          fontWeight={600}
                          textAnchor="start"
                        >
                          {formatCost(averageSpend)}
                        </text>
                      );
                    }}
                  />
                  <Bar dataKey="cost" fill="var(--color-border)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4">
        {labeledModels.flatMap((m) => {
          const name = modelNames.get(m.model_id) ?? EXTRA_MODEL_NAMES[m.model_id];
          if (!name) return [];
          return [
            <Card key={m.model_id}>
              <CardHeader>
                <CardTitle className="text-base">{name}</CardTitle>
                <CardDescription>{m.model_id}</CardDescription>
              </CardHeader>
              <CardContent className="grid grid-cols-2 gap-4 md:grid-cols-4">
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
                    Tokens
                  </p>
                  <p className="font-medium text-foreground">
                    <CompactNumber
                      value={m.uncached_input_tokens + m.cached_input_tokens}
                    />{" "}/ <CompactNumber value={m.output_tokens} />
                  </p>
                </div>
              </CardContent>
            </Card>
          ];
        })}
        {usage && labeledModels.length === 0 && (
          <Card>
            <CardContent>
              <p className="font-sans text-muted-foreground">
                No LLM invocations yet.
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </DashboardPage>
  );
}
