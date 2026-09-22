"use client";

import { getModels, getUsage } from "@/repository/backend/queries";
import { useQuery } from "@tanstack/react-query";
import { DashboardPage } from "@/app/dashboard/components/dashboard-page";
import { ChartTooltip } from "@/app/dashboard/components/chart";
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
  ResponsiveContainer,
  Tooltip,
  XAxis,
  type BarShapeProps,
} from "recharts";

const EXTRA_MODEL_NAMES: Record<string, string> = {
  "gemini-3.1-flash-lite": "Gemini 3.1 Flash Lite (transcription)",
  "meta/muse-voice-transcribe-1.0": "Muse Voice Transcribe 1.0 (transcription)",
  "openai/gpt-transcribe": "GPT Transcribe (transcription)",
};

function formatCost(cost: number): string {
  return `$${cost.toFixed(4)}`;
}

const CHART_COLORS = [
  "#2563eb",
  "#7c3aed",
  "#0d9488",
  "#d97706",
  "#db2777",
];

type StackedBarShapeProps = BarShapeProps;

function createStackedBarShape(modelKeys: string[], currentKey: string) {
  return function StackedBarShape({
    x,
    y,
    width,
    height,
    fill,
    fillOpacity,
    payload,
  }: StackedBarShapeProps) {
    if (width <= 0 || height <= 0) return null;
    const topKey = [...modelKeys]
      .reverse()
      .find((key) => Number(payload?.[key] ?? 0) > 0);
    const radius = Math.min(4, width / 2, height / 2);
    const right = x + width;
    const bottom = y + height;
    const path =
      currentKey === topKey && radius > 0
        ? `M ${x} ${bottom} V ${y + radius} Q ${x} ${y} ${x + radius} ${y} H ${right - radius} Q ${right} ${y} ${right} ${y + radius} V ${bottom} Z`
        : `M ${x} ${y} H ${right} V ${bottom} H ${x} Z`;
    return <path d={path} fill={fill} fillOpacity={fillOpacity} />;
  };
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
  const dailyTotals = days.map(
    ({ key }) => usage?.daily.find((entry) => entry.day === key)?.total_cost ?? 0,
  );
  const averageSpend =
    dailyTotals.reduce((sum, cost) => sum + cost, 0) / dailyTotals.length;

  const modelTotals = new Map<string, number>();
  for (const entry of usage?.daily ?? []) {
    for (const model of entry.models ?? []) {
      modelTotals.set(
        model.model_id,
        (modelTotals.get(model.model_id) ?? 0) + model.cost,
      );
    }
  }
  const chartModels = [...modelTotals.entries()]
    .filter(([, cost]) => cost > 0)
    .sort((a, b) => b[1] - a[1])
    .map(([modelId], index) => ({
      modelId,
      dataKey: `model${index}`,
      color: CHART_COLORS[index % CHART_COLORS.length],
      opacity: index < CHART_COLORS.length ? 1 : 0.5,
      name: modelNames.get(modelId) ?? EXTRA_MODEL_NAMES[modelId] ?? modelId,
    }));

  const dailyData = days.map(({ key, label }) => {
    const entry = usage?.daily.find((day) => day.day === key);
    const point: Record<string, number | string> = {
      key,
      label,
      cost: entry?.total_cost ?? 0,
      total: entry?.total_cost ?? 0,
    };
    for (const model of chartModels) point[model.dataKey] = 0;
    for (const logged of entry?.models ?? []) {
      const model = chartModels.find((c) => c.modelId === logged.model_id);
      if (model) point[model.dataKey] = logged.cost;
    }
    return point;
  });
  const labeledModels = (usage?.models ?? []).filter((model) =>
    Boolean(
      modelNames.get(model.model_id) ?? EXTRA_MODEL_NAMES[model.model_id],
    ),
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
                <BarChart
                  data={dailyData}
                  margin={{ top: 8, right: 0, bottom: 0, left: 0 }}
                >
                  <XAxis
                    dataKey="key"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fontSize: 12 }}
                    tickFormatter={(value: string) =>
                      String(
                        dailyData.find((point) => point.key === value)?.label ??
                          value,
                      )
                    }
                  />
                  {/* <YAxis
                    orientation="right"
                    width={48}
                    axisLine={false}
                    tickLine={false}
                    domain={[0, chartMax]}
                    tickFormatter={(value) => `$${Number(value).toFixed(2)}`}
                    minTickGap={24}
                  /> */}
                  <Tooltip
                    allowEscapeViewBox={{ x: true, y: true }}
                    wrapperStyle={{ zIndex: 10 }}
                    content={
                      <ChartTooltip formatValue={formatCost} showBreakdown />
                    }
                    cursor={{ fill: "var(--color-muted)" }}
                  />
                  {chartModels.length > 0 ? (
                    chartModels.map((model) => (
                      <Bar
                        key={model.dataKey}
                        dataKey={model.dataKey}
                        name={model.name}
                        stackId="spend"
                        fill={model.color}
                        fillOpacity={model.opacity}
                        shape={createStackedBarShape(
                          chartModels.map((item) => item.dataKey),
                          model.dataKey,
                        )}
                      />
                    ))
                  ) : (
                    <Bar
                      dataKey="cost"
                      fill="#94a3b8"
                      radius={[4, 4, 0, 0]}
                    />
                  )}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4">
        {labeledModels.flatMap((m) => {
          const name =
            modelNames.get(m.model_id) ?? EXTRA_MODEL_NAMES[m.model_id];
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
                    />{" "}
                    / <CompactNumber value={m.output_tokens} />
                  </p>
                </div>
              </CardContent>
            </Card>,
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
