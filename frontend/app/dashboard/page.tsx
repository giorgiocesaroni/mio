"use client";

import {
  getCurrentGoal,
  getDailyFoodLogsWithFoodsView,
  getDailyMacrosView,
  getTotalLlmCost,
} from "@/repository/supabase/queries";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { H1, P } from "../components/typography";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../components/card";
import { Button } from "../components/button";
import { Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { v4 } from "uuid";

function TotalCost() {
  const { data } = useQuery({
    queryKey: ["getTotalLlmCost"],
    queryFn: getTotalLlmCost,
  });

  return <P className="text-sm">${(data?.total_cost ?? 0).toFixed(2)}</P>;
}

function MacroCard({
  label,
  unit,
  current,
  target,
  showDifference,
  onClick,
}: {
  label: string;
  unit: string;
  current: number;
  target: number | undefined;
  showDifference: boolean;
  onClick: () => void;
}) {
  const remaining = target !== undefined ? target - current : undefined;

  const value = showDifference ? remaining : current;
  const displayValue = value !== undefined ? Math.abs(value).toFixed() : "0";

  let suffix: string | undefined;
  if (showDifference && remaining !== undefined) {
    suffix = remaining >= 0 ? "left" : "over";
  }

  return (
    <button type="button" onClick={onClick} className="block text-left">
      <Card className="cursor-pointer">
        <CardDescription>{label}</CardDescription>
        <CardHeader>
          <CardTitle>
            {displayValue} {unit}
            {suffix && ` ${suffix}`}
          </CardTitle>
        </CardHeader>
      </Card>
    </button>
  );
}

function DailyMacros() {
  const [showDifference, setShowDifference] = useState(false);

  const { data: macros } = useQuery({
    queryKey: ["getDailyMacrosView"],
    queryFn: getDailyMacrosView,
  });

  const { data: goal } = useQuery({
    queryKey: ["getCurrentGoal"],
    queryFn: getCurrentGoal,
  });

  return (
    <div className="grid md:grid-cols-4 grid-cols-2 gap-4 items-center">
      <MacroCard
        label="Calories"
        unit="Kcal"
        current={macros?.total_calories_kcal ?? 0}
        target={goal?.calories_kcal}
        showDifference={showDifference}
        onClick={() => setShowDifference((v) => !v)}
      />
      <MacroCard
        label="Protein"
        unit="g"
        current={macros?.total_protein_g ?? 0}
        target={goal?.protein_g}
        showDifference={showDifference}
        onClick={() => setShowDifference((v) => !v)}
      />
      <MacroCard
        label="Carbs"
        unit="g"
        current={macros?.total_carbs_g ?? 0}
        target={goal?.carbs_g}
        showDifference={showDifference}
        onClick={() => setShowDifference((v) => !v)}
      />
      <MacroCard
        label="Fat"
        unit="g"
        current={macros?.total_fat_g ?? 0}
        target={goal?.fat_g}
        showDifference={showDifference}
        onClick={() => setShowDifference((v) => !v)}
      />
    </div>
  );
}

function DailyFoodLogsWithFoods() {
  const { data: dailyFoodLogsView } = useQuery({
    queryKey: ["getDailyFoodLogsWithFoodsView"],
    queryFn: getDailyFoodLogsWithFoodsView,
  });

  return (
    <div className="grid gap-4">
      {dailyFoodLogsView?.map((log) => (
        <Card key={log.log_id} className="overflow-auto grid gap-2">
          <div className="flex justify-between items-center gap-4">
            <P className="truncate text-foreground font-medium">
              {log.food_name}
            </P>
            <P className="whitespace-nowrap text-sm">
              {new Date(log.log_created_at!).toLocaleTimeString()}
            </P>
          </div>
          <div className="flex gap-4 items-center text-sm">
            <P>{log.log_quantity_g} g</P>
            <P>
              {(
                (log.log_quantity_g ?? 0) *
                ((log.food_calories_kcal ?? 0) / 100)
              ).toFixed()}{" "}
              Kcal
            </P>
            <P className="">
              P{" "}
              {(
                (log.log_quantity_g ?? 0) *
                ((log.food_protein_g ?? 0) / 100)
              ).toFixed()}{" "}
              g
            </P>
            <P className="">
              C{" "}
              {(
                (log.log_quantity_g ?? 0) *
                ((log.food_carbs_g ?? 0) / 100)
              ).toFixed()}{" "}
              g
            </P>
            <P className="">
              F{" "}
              {(
                (log.log_quantity_g ?? 0) *
                ((log.food_fat_g ?? 0) / 100)
              ).toFixed()}{" "}
              g
            </P>
          </div>
        </Card>
      ))}
    </div>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  return (
    <div className="grid gap-12 p-4">
      <div className="flex items-center gap-4 justify-between">
        <H1 className="text-xl md:text-xl">Today</H1>
        <div className="flex items-center gap-2">
          <TotalCost />
          <Button
            onClick={() => router.push(`/dashboard/chat/${v4()}`)}
            className="bg-red-500 border-red-500 text-background-alt aspect-square py-2 px-2 rounded-full"
          >
            <Plus className="size-4" />
          </Button>
        </div>
      </div>
      <DailyMacros />
      <DailyFoodLogsWithFoods />
    </div>
  );
}
