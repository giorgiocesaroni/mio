"use client";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { getDailyMacrosTrend } from "@/repository/supabase/queries";
import { PageTitle } from "@/app/dashboard/components/page-title";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
} from "recharts";

function dayKey(date: Date): string {
  return date.toLocaleDateString("en-CA");
}

function formatAxisValue(value: number): string {
  const absolute = Math.abs(value);
  if (absolute >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`;
  if (absolute >= 1_000) return `${(value / 1_000).toFixed(2)}K`;
  return Math.round(value).toString();
}

function formatAverageValue(value: number, dataKey: keyof typeof chartConfig): string {
  return dataKey === "calories"
    ? Math.round(value).toLocaleString()
    : formatAxisValue(value);
}

function getLastSevenDays() {
  const today = new Date();
  return Array.from({ length: 7 }, (_, index) => {
    const date = new Date(today);
    date.setHours(12, 0, 0, 0);
    date.setDate(today.getDate() - 6 + index);
    return {
      key: dayKey(date),
      label: date.toLocaleDateString(undefined, { weekday: "narrow" }),
    };
  });
}

const chartConfig = {
  calories: { label: "Calories", color: "#ef4444" },
  protein: { label: "Protein", color: "#f97316" },
  carbs: { label: "Carbs", color: "#eab308" },
  fat: { label: "Fat", color: "#22c55e" },
};

type TrendCardProps = {
  title: string;
  dataKey: keyof typeof chartConfig;
  data: Array<Record<string, number | string>>;
  unit: string;
};

type TrendTooltipProps = {
  active?: boolean;
  payload?: Array<{
    value?: number;
    payload?: { key?: string };
  }>;
  unit: string;
  label: string;
};

function TrendTooltip({ active, payload, unit, label }: TrendTooltipProps) {
  if (!active || !payload?.length) return null;

  const point = payload[0].payload;
  const date = point?.key
    ? new Date(`${point.key}T12:00:00`)
    : undefined;

  return (
    <div className="rounded-lg border bg-background px-3 py-2 text-sm shadow-lg">
      <p className="font-medium text-foreground">
        {date?.toLocaleDateString(undefined, {
          weekday: "long",
          month: "short",
          day: "numeric",
        })}
      </p>
      <p className="text-muted-foreground">
        {label}: {Math.round(Number(payload[0].value ?? 0)).toLocaleString()} {unit}
      </p>
    </div>
  );
}

function TrendCard({ title, dataKey, data, unit }: TrendCardProps) {
  const config = chartConfig[dataKey];
  const average = data.reduce((sum, point) => sum + Number(point[dataKey]), 0) / data.length;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-48 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 4 }}>
              <CartesianGrid vertical={false} strokeDasharray="3 3" />
              <XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fontSize: 12 }} />
              <Tooltip
                content={<TrendTooltip unit={unit} label={config.label} />}
                cursor={{ fill: "var(--color-muted)" }}
              />
              <ReferenceLine
                y={average}
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
                      {`${formatAverageValue(average, dataKey)} ${unit}`}
                    </text>
                  );
                }}
              />
              <Bar
                dataKey={dataKey}
                fill="var(--color-border)"
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

export default function TrendsPage() {
  const days = getLastSevenDays();
  const startDay = days[0].key;
  const { data: macros, isLoading } = useQuery({
    queryKey: ["getDailyMacrosTrend", startDay],
    queryFn: () => getDailyMacrosTrend(startDay),
  });

  const data = days.map(({ key, label }) => {
    const row = macros?.find((macro) => macro.day?.slice(0, 10) === key);
    return {
      key,
      label,
      calories: Math.round(Number(row?.total_calories_kcal ?? 0)),
      protein: Math.round(Number(row?.total_protein_g ?? 0)),
      carbs: Math.round(Number(row?.total_carbs_g ?? 0)),
      fat: Math.round(Number(row?.total_fat_g ?? 0)),
    };
  });

  return (
    <div className="grid gap-6">
      <div className="grid gap-1">
        <PageTitle>Trends</PageTitle>
        <p className="text-sm text-muted-foreground">Your nutrition over the last 7 days.</p>
      </div>
      {isLoading ? (
        <div className="text-sm text-muted-foreground">Loading trends…</div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          <TrendCard title="Calories" dataKey="calories" data={data} unit="kcal" />
          <TrendCard title="Protein" dataKey="protein" data={data} unit="g" />
          <TrendCard title="Carbs" dataKey="carbs" data={data} unit="g" />
          <TrendCard title="Fat" dataKey="fat" data={data} unit="g" />
        </div>
      )}
    </div>
  );
}
