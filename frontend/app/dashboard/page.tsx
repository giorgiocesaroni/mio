"use client";

import {
  getCurrentGoal,
  getDailyFoodLogsWithFoodsView,
  getDailyMacrosView,
} from "@/repository/supabase/queries";
import { Database } from "@/repository/supabase/types";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { getElapsedTime } from "../utils";
import { PageTitle } from "./components/page-title";
import { QuickLogComposer } from "./components/quick-log-composer";

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
    <Card
      onClick={target === undefined ? undefined : onClick}
      className={
        target === undefined ? undefined : "cursor-pointer hover:bg-muted/50"
      }
    >
      <CardHeader className="gap-0">
        <CardDescription>
          {label} {suffix && ` ${suffix}`}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <CardTitle>
          {displayValue} {unit}
        </CardTitle>
      </CardContent>
    </Card>
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
      <Badge className={cn(color, "size-5 p-0 text-white")}>{letter}</Badge>
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
    <div className="grid grid-cols-2 items-center gap-4 md:grid-cols-4">
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
    <div className="grid grid-cols-4 items-center gap-4 whitespace-nowrap text-muted-foreground md:grid-cols-5">
      {amount !== undefined && (
        <span className="hidden whitespace-nowrap md:inline">{amount}</span>
      )}
      <span>{macros.calories.toFixed()} Kcal</span>
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
    <Card>
      <CardContent className="grid gap-2">
        <div className="flex items-center justify-between gap-4 overflow-auto">
          <p className="truncate font-medium text-foreground">
            {log.food_name}
          </p>
          <p className="whitespace-nowrap text-muted-foreground">
            {getElapsedTime(timestamp)}
          </p>
        </div>
        <FoodBadges amount={amountOf(log)} macros={macrosOf(log)} />
      </CardContent>
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
    <Card
      onClick={() => setExpanded((v) => !v)}
      className="cursor-pointer hover:bg-muted/30"
    >
      <CardContent className="grid gap-2">
        <div className="flex items-center justify-between gap-4 overflow-auto">
          <p className="truncate font-medium text-foreground">
            {block.recipeName}
            <span className="font-normal text-muted-foreground">
              {" "}
              (recipe)
            </span>
          </p>
          <p className="whitespace-nowrap text-muted-foreground">
            {getElapsedTime(timestamp)}
          </p>
        </div>
        <FoodBadges
          amount={`${Math.round(totalGrams)} g`}
          macros={sumMacros(block.logs)}
        />
        {expanded && (
          <>
            <Separator className="my-2" />
            <div className="grid gap-1">
              {block.logs.map((log) => {
                const m = macrosOf(log);
                return (
                  <div
                    key={log.log_id}
                    className="flex items-center justify-between gap-4 px-1"
                  >
                    <span className="truncate text-muted-foreground">
                      {log.food_name} <span>({amountOf(log)})</span>
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
      </CardContent>
    </Card>
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
  return (
    <div className="grid gap-12">
      <PageTitle>Today</PageTitle>
      <DailyMacros />
      <QuickLogComposer />
      <DailyFoodLogsWithFoods />
    </div>
  );
}
