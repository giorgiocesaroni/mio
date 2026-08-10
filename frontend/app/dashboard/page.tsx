"use client";

import {
  getCurrentGoal,
  getDailyFoodLogsWithFoodsView,
  getDailyMacrosView,
  getTotalLlmCost,
} from "@/repository/supabase/queries";
import { Database } from "@/repository/supabase/types";
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
import { getElapsedTime } from "../utils";

function TotalCost() {
  const router = useRouter();
  const { data } = useQuery({
    queryKey: ["getTotalLlmCost"],
    queryFn: getTotalLlmCost,
  });

  return (
    <button
      type="button"
      onClick={() => router.push("/dashboard/usage")}
      className="cursor-pointer hover:opacity-80 transition-opacity"
      title="View usage"
    >
      <P className="text-sm">${(data?.total_cost ?? 0).toFixed(2)}</P>
    </button>
  );
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
    <button
      type="button"
      onClick={onClick}
      className="block text-left"
      disabled={target === undefined}
    >
      <Card className={target === undefined ? "" : "cursor-pointer"}>
        <CardDescription>
          {label} {suffix && ` ${suffix}`}
        </CardDescription>
        <CardHeader>
          <CardTitle>
            {displayValue} {unit}
          </CardTitle>
        </CardHeader>
      </Card>
    </button>
  );
}

function MacroBadge({
  letter,
  color,
  value,
}: {
  letter: string;
  color: string;
  value: string;
}) {
  return (
    <span className="inline-flex items-center gap-1.5 text-sm leading-none">
      <span className={`${color} text-white text-xs font-bold px-1 rounded`}>
        {letter}
      </span>
      {value} g
    </span>
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

type FoodLog =
  Database["public"]["Views"]["v_daily_food_logs_with_foods"]["Row"];

type Macros = { calories: number; protein: number; carbs: number; fat: number };

function macrosOf(log: FoodLog): Macros {
  const q = log.log_quantity_g ?? 0;
  return {
    calories: Math.round(q * ((log.food_calories_kcal ?? 0) / 100)),
    protein: Math.round(q * ((log.food_protein_g ?? 0) / 100)),
    carbs: Math.round(q * ((log.food_carbs_g ?? 0) / 100)),
    fat: Math.round(q * ((log.food_fat_g ?? 0) / 100)),
  };
}

function amountOf(log: FoodLog): string {
  if (log.log_serving_size_id) {
    return `${log.log_quantity}× ${
      (log.log_quantity ?? 0) > 1
        ? log.log_serving_size_label_plural
        : log.log_serving_size_label
    }`;
  }
  return `${log.log_quantity_g} g`;
}

function FoodBadges({ amount, macros }: { amount?: string; macros: Macros }) {
  return (
    <div className="whitespace-nowrap grid grid-cols-4 md:grid-cols-5 gap-4 items-center text-sm text-muted-foreground">
      {amount !== undefined && (
        <span className="hidden md:inline whitespace-nowrap">{amount}</span>
      )}
      <P>{macros.calories.toFixed()} Kcal</P>
      <MacroBadge
        letter="P"
        color="bg-red-500"
        value={macros.protein.toFixed()}
      />
      <MacroBadge
        letter="C"
        color="bg-yellow-500"
        value={macros.carbs.toFixed()}
      />
      <MacroBadge letter="F" color="bg-blue-500" value={macros.fat.toFixed()} />
    </div>
  );
}

type FoodBlock =
  | { kind: "food"; log: FoodLog }
  | { kind: "recipe"; recipeId: string; recipeName: string; logs: FoodLog[] };

function buildBlocks(logs: FoodLog[]) {
  const groups = new Map<string, FoodLog[]>();
  const standalone: FoodLog[] = [];
  for (const log of logs) {
    if (log.log_recipe_id) {
      const list = groups.get(log.log_recipe_id) ?? [];
      list.push(log);
      groups.set(log.log_recipe_id, list);
    } else {
      standalone.push(log);
    }
  }

  const blocks: FoodBlock[] = standalone.map((log) => ({ kind: "food", log }));
  for (const [recipeId, recipeLogs] of groups) {
    blocks.push({
      kind: "recipe",
      recipeId,
      recipeName: recipeLogs[0].recipe_name ?? "Recipe",
      logs: recipeLogs,
    });
  }

  // Keep chronological order (descending) using each block's representative timestamp.
  const ts = (b: FoodBlock) =>
    b.kind === "food" ? b.log.log_created_at! : b.logs[0].log_created_at!;
  blocks.sort((a, b) => new Date(ts(b)).getTime() - new Date(ts(a)).getTime());
  return blocks;
}

function sumMacros(logs: FoodLog[]): Macros {
  return logs.reduce<Macros>(
    (acc, log) => {
      const m = macrosOf(log);
      return {
        calories: Math.round(acc.calories + m.calories),
        protein: Math.round(acc.protein + m.protein),
        carbs: Math.round(acc.carbs + m.carbs),
        fat: Math.round(acc.fat + m.fat),
      };
    },
    { calories: 0, protein: 0, carbs: 0, fat: 0 },
  );
}

function IngredientLogCard({ log }: { log: FoodLog }) {
  const timestamp = log.log_created_at!;
  return (
    <Card className="grid gap-2">
      <div className="overflow-auto flex justify-between items-center gap-4">
        <P className="truncate text-foreground font-medium">{log.food_name}</P>
        <P className="whitespace-nowrap text-sm">{getElapsedTime(timestamp)}</P>
      </div>
      <FoodBadges amount={amountOf(log)} macros={macrosOf(log)} />
    </Card>
  );
}

function RecipeLogCard({
  block,
}: {
  block: Extract<FoodBlock, { kind: "recipe" }>;
}) {
  const [expanded, setExpanded] = useState(false);
  const timestamp = block.logs[0].log_created_at!;
  const totalGrams = block.logs.reduce(
    (sum, log) => sum + (log.log_quantity_g ?? 0),
    0,
  );
  return (
    <button
      type="button"
      onClick={() => setExpanded((v) => !v)}
      className="text-left"
    >
      <Card className="grid gap-2">
        <div className="overflow-auto flex justify-between items-center gap-4">
          <P className="truncate text-foreground font-medium">
            {block.recipeName}
            <span className="text-muted-foreground font-normal"> (recipe)</span>
          </P>
          <P className="whitespace-nowrap text-sm">
            {getElapsedTime(timestamp)}
          </P>
        </div>
        <FoodBadges
          amount={`${Math.round(totalGrams)} g`}
          macros={sumMacros(block.logs)}
        />
        {expanded && (
          <>
            <hr className="border-border my-2" />
            <div className="grid gap-1">
              {block.logs.map((log) => {
                const m = macrosOf(log);
                return (
                  <div
                    key={log.log_id}
                    className="flex justify-between items-center gap-4 text-sm px-1"
                  >
                    <span className="truncate text-muted-foreground">
                      {log.food_name}{" "}
                      <span className="">({amountOf(log)})</span>
                    </span>
                    <span className="whitespace-nowrap text-muted-foreground">
                      {m.calories.toFixed()} Kcal
                    </span>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </Card>
    </button>
  );
}

function DailyFoodLogsWithFoods() {
  const { data: dailyFoodLogsView } = useQuery({
    queryKey: ["getDailyFoodLogsWithFoodsView"],
    queryFn: getDailyFoodLogsWithFoodsView,
  });

  const blocks = buildBlocks(dailyFoodLogsView ?? []);

  return (
    <div className="grid gap-4">
      {blocks.map((block, index) =>
        block.kind === "food" ? (
          <IngredientLogCard key={block.log.log_id} log={block.log} />
        ) : (
          <RecipeLogCard
            key={`recipe-${block.recipeId}-${index}`}
            block={block}
          />
        ),
      )}
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
            onClick={() => router.push("/dashboard/chat/new")}
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
