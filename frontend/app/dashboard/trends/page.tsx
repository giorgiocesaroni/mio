"use client";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { getDailyMacrosTrend } from "@/repository/supabase/queries";
import { useQuery } from "@tanstack/react-query";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

function dayKey(date: Date): string {
  return date.toLocaleDateString("en-CA");
}

function getLastSevenDays() {
  const today = new Date();
  return Array.from({ length: 7 }, (_, index) => {
    const date = new Date(today);
    date.setHours(12, 0, 0, 0);
    date.setDate(today.getDate() - 6 + index);
    return {
      key: dayKey(date),
      label: date.toLocaleDateString(undefined, { weekday: "short" }),
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

function TrendCard({ title, dataKey, data, unit }: TrendCardProps) {
  const config = chartConfig[dataKey];

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-48 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 4 }}>
              <CartesianGrid vertical={false} strokeDasharray="3 3" />
              <XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fontSize: 12 }} />
              <YAxis
                axisLine={false}
                tickLine={false}
                tick={{ fontSize: 12 }}
                tickFormatter={(value) => Math.round(Number(value)).toLocaleString()}
                allowDecimals={false}
                width={52}
              />
              <Tooltip
                contentStyle={{ borderRadius: 12, border: "none", fontSize: 12 }}
                formatter={(value) => [
                  `${Math.round(Number(value)).toLocaleString()} ${unit}`,
                  config.label,
                ]}
              />
              <Line
                type="monotone"
                dataKey={dataKey}
                stroke={config.color}
                strokeWidth={2.5}
                dot={{ r: 3, fill: config.color, strokeWidth: 0 }}
                activeDot={{ r: 5 }}
                connectNulls
              />
            </LineChart>
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
      label,
      calories: Math.round(Number(row?.total_calories_kcal ?? 0)),
      protein: Math.round(Number(row?.total_protein_g ?? 0)),
      carbs: Math.round(Number(row?.total_carbs_g ?? 0)),
      fat: Math.round(Number(row?.total_fat_g ?? 0)),
    };
  });

  return (
    <div className="grid gap-6">
      <div>
        <h1 className="font-heading text-2xl font-semibold">Trends</h1>
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
