"use client";

import type { DayLog } from "@/repository/backend/queries";
import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

function dayKey(date: Date): string {
  return date.toLocaleDateString("en-CA");
}

function getRecentDays() {
  const today = new Date();
  return Array.from({ length: 7 }, (_, index) => {
    const date = new Date(today);
    date.setHours(12, 0, 0, 0);
    date.setDate(today.getDate() - 6 + index);
    return { date, key: dayKey(date) };
  });
}

function DayPicker({
  selectedDay,
  onSelect,
}: {
  selectedDay: string;
  onSelect: (day: string) => void;
}) {
  const days = getRecentDays();
  const today = days[days.length - 1].key;

  return (
    <div className="grid grid-cols-7 gap-3">
      {days.map(({ date, key }) => {
        const isToday = key === today;
        return (
          <button
            key={key}
            type="button"
            aria-pressed={selectedDay === key}
            onClick={() => onSelect(key)}
            className={cn(
              "grid gap-1 rounded-xl border py-2 text-center text-sm transition-colors",
              selectedDay === key
                ? "border-brand bg-brand text-brand-foreground hover:bg-brand/90"
                : isToday
                  ? "border-brand text-brand hover:bg-brand/10"
                  : "border-border text-foreground hover:bg-muted",
            )}
          >
            <span className="font-heading text-base leading-snug font-medium">
              {date.getDate()}
            </span>
            <span
              className={cn(
                "text-sm",
                selectedDay === key
                  ? "text-white/80"
                  : isToday
                    ? "text-brand"
                    : "text-muted-foreground",
              )}
            >
              {date.toLocaleDateString(undefined, { weekday: "narrow" })}
            </span>
          </button>
        );
      })}
    </div>
  );
}
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { getElapsedTime } from "../utils";
import { DailyMacros } from "./components/daily-macros";
import { DashboardPage } from "./components/dashboard-page";
import { useDayEntries } from "./components/day-entries";
import { PendingDrafts } from "./components/draft-card";
import {
  DeleteDialog,
  EntryMenu,
  EntryPill,
  ReviseDialog,
  useLogEntryActions,
} from "./components/entry-actions";
import { FoodBadges, type Macros } from "./components/food-badges";

type FoodLog = DayLog;

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
  return `${Math.round(log.log_quantity_g ?? 0)} g`;
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

/** Right side of an entry's first row: elapsed time and the actions menu. */
function EntryMeta({
  timestamp,
  menu,
}: {
  timestamp: string;
  menu: React.ReactNode;
}) {
  return (
    <div className="flex shrink-0 items-center gap-2">
      <p className="whitespace-nowrap text-muted-foreground">
        {getElapsedTime(timestamp)}
      </p>
      {menu}
    </div>
  );
}

/** Menu and dialogs for one logged card (a log, or a recipe's logs). */
function useLogEntry(day: string, logs: FoodLog[], description: string) {
  const { dialog, setDialog, revise, remove } = useLogEntryActions(
    day,
    logs.map((log) => log.log_id!),
  );
  const close = () => setDialog(null);
  const menu = (
    <EntryMenu
      disabled={revise.isPending || remove.isPending}
      onOpen={setDialog}
    />
  );
  const dialogs = (
    <>
      {dialog === "edit" ? (
        <ReviseDialog
          open
          onOpenChange={(open) => !open && close()}
          description={description}
          pending={revise.isPending}
          onApply={(instruction) => revise.mutate(instruction)}
        />
      ) : null}
      {dialog === "delete" ? (
        <DeleteDialog
          open
          onOpenChange={(open) => !open && close()}
          name={description}
          pending={remove.isPending}
          onDelete={() => remove.mutate()}
        />
      ) : null}
    </>
  );
  return { menu, dialogs };
}

function IngredientLogCard({ day, log }: { day: string; log: FoodLog }) {
  const { menu, dialogs } = useLogEntry(
    day,
    [log],
    `${amountOf(log)} ${log.food_name}`,
  );
  return (
    <>
      <Card>
        <CardContent className="grid gap-2">
          <div className="flex min-w-0 items-center justify-between gap-4 overflow-hidden">
            <p className="min-w-0 truncate font-medium text-foreground">
              {log.food_name}
            </p>
            <EntryMeta timestamp={log.log_created_at!} menu={menu} />
          </div>
          <FoodBadges amount={amountOf(log)} macros={macrosOf(log)} />
        </CardContent>
      </Card>
      {dialogs}
    </>
  );
}

function RecipeLogCard({
  day,
  block,
}: {
  day: string;
  block: Extract<FoodBlock, { kind: "recipe" }>;
}) {
  const [expanded, setExpanded] = useState(false);
  const timestamp = block.logs[0].log_created_at!;
  const totalGrams = block.logs.reduce(
    (sum, log) => sum + (log.log_quantity_g ?? 0),
    0,
  );
  const { menu, dialogs } = useLogEntry(
    day,
    block.logs,
    `${Math.round(totalGrams)} g ${block.recipeName}`,
  );
  return (
    <>
      <Card
        onClick={() => setExpanded((v) => !v)}
        className="cursor-pointer hover:bg-muted/30"
      >
        <CardContent className="grid gap-2">
          <div className="flex min-w-0 items-center justify-between gap-4 overflow-hidden">
            <p className="min-w-0 truncate font-medium text-foreground">
              <EntryPill>Recipe</EntryPill>
              {block.recipeName}
            </p>
            <EntryMeta timestamp={timestamp} menu={menu} />
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
      {dialogs}
    </>
  );
}

function DailyFoodLogsWithFoods({ day }: { day: string }) {
  const { data: entries } = useDayEntries(day);

  const blocks = buildBlocks(entries?.logs ?? []);

  return (
    <div className="grid gap-3">
      <PendingDrafts day={day} />
      {blocks.map((block, index) =>
        block.kind === "food" ? (
          <IngredientLogCard key={block.log.log_id} day={day} log={block.log} />
        ) : (
          <RecipeLogCard
            key={`recipe-${block.recipeId}-${index}`}
            day={day}
            block={block}
          />
        ),
      )}
    </div>
  );
}

export default function DashboardHomePage() {
  const [selectedDay, setSelectedDay] = useState(dayKey(new Date()));

  return (
    <DashboardPage
      title="Mio"
      bodyClassName="gap-12"
      actions={
        <Button
          size="icon-sm"
          asChild
          className="rounded-full bg-brand text-brand-foreground hover:bg-brand/90"
        >
          <Link href="/dashboard/chat/new" aria-label="New chat">
            <Plus className="size-4" />
          </Link>
        </Button>
      }
    >
      <DayPicker selectedDay={selectedDay} onSelect={setSelectedDay} />
      <DailyMacros day={selectedDay} />
      <DailyFoodLogsWithFoods day={selectedDay} />
    </DashboardPage>
  );
}
