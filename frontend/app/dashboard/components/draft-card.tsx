"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  confirmDraft,
  deleteDraftDish,
  reviseDraftDish,
  type DayEntries,
  type DraftAlternative,
  type DraftRow,
  type LogDraft,
  type Per100g,
} from "@/repository/backend/queries";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { getElapsedTime } from "@/app/utils";
import {
  DeleteDialog,
  EntryMenu,
  EntryPill,
  ReviseDialog,
  useInvalidateLogs,
  type EntryDialog,
} from "./entry-actions";
import { dayEntriesQueryKey, useDayEntries } from "./day-entries";
import { FoodBadges, type Macros } from "./food-badges";

function targetOf(row: DraftRow): DraftAlternative {
  return row.alternatives.find((a) => a.key === row.target)!;
}

/** What groups a row with its dish's other rows: the dish, or the row alone. */
function groupKey(row: DraftRow): string {
  return row.dish_id ?? row.id;
}

function macrosOf(per100g: Per100g, grams: number): Macros {
  return {
    calories: (per100g.calories_kcal * grams) / 100,
    protein: (per100g.protein_g * grams) / 100,
    carbs: (per100g.carbs_g * grams) / 100,
    fat: (per100g.fat_g * grams) / 100,
  };
}

function sumMacros(rows: DraftRow[]): Macros {
  return rows.reduce<Macros>(
    (acc, row) => {
      const m = macrosOf(targetOf(row).per_100g, row.grams);
      return {
        calories: acc.calories + m.calories,
        protein: acc.protein + m.protein,
        carbs: acc.carbs + m.carbs,
        fat: acc.fat + m.fat,
      };
    },
    { calories: 0, protein: 0, carbs: 0, fat: 0 },
  );
}

function amountOf(row: DraftRow, target: DraftAlternative): string {
  if (row.unit === "serving") {
    const serving = target.serving_sizes?.find(
      (s) => s.id === row.serving_size_id,
    );
    const label = row.quantity > 1 ? serving?.label_plural : serving?.label;
    return `${row.quantity}× ${label ?? "serving"}`;
  }
  if (row.unit === "recipe") return `${row.quantity}× recipe`;
  return `${Math.round(row.quantity)} g`;
}

/** A draft's rows, one list per dish, in the order the dishes were logged. */
function groupRows(rows: DraftRow[]): DraftRow[][] {
  const groups = new Map<string, DraftRow[]>();
  for (const row of rows) {
    const list = groups.get(groupKey(row)) ?? [];
    list.push(row);
    groups.set(groupKey(row), list);
  }
  return [...groups.values()];
}

function useDraftMutations(draft: LogDraft) {
  const queryClient = useQueryClient();
  const invalidateLogs = useInvalidateLogs();
  const setDraft = (updated: LogDraft | null) =>
    queryClient.setQueryData<DayEntries>(
      dayEntriesQueryKey(draft.day),
      (prev) =>
        prev && {
          ...prev,
          drafts: prev.drafts.flatMap((d) =>
            d.id !== draft.id ? [d] : updated ? [updated] : [],
          ),
        },
    );

  const revise = useMutation({
    mutationFn: ({
      dishId,
      instruction,
    }: {
      dishId: string;
      instruction: string;
    }) => reviseDraftDish(draft.id, dishId, instruction),
    onSuccess: (updated) => setDraft(updated),
    onError: (err) => toast.error(err.message),
  });
  const remove = useMutation({
    mutationFn: (dishId: string) => deleteDraftDish(draft.id, dishId),
    onSuccess: ({ draft: updated }) => setDraft(updated),
    onError: (err) => toast.error(err.message),
  });
  const confirm = useMutation({
    mutationFn: (rowIds: string[]) => confirmDraft(draft.id, rowIds),
    onSuccess: async (result) => {
      const failed = result.results.filter((r) => !r.success);
      if (failed.length)
        toast.error(`Logging failed: ${failed.map((f) => f.error).join("; ")}`);
      // The day's drafts and logs are one query, so the draft dish and its new
      // logs swap in a single update.
      await invalidateLogs();
    },
    onError: (err) => toast.error(err.message),
  });
  return { revise, remove, confirm };
}

/**
 * One dish of a draft, reviewed as a whole: its header shows the dish's total
 * and the actions apply to every component at once. A single food is a dish
 * with one component and looks like a plain entry.
 */
function DraftDishCard({
  draft,
  rows,
  readOnly = false,
}: {
  draft: LogDraft;
  rows: DraftRow[];
  readOnly?: boolean;
}) {
  const [dialog, setDialog] = useState<EntryDialog>(null);
  const [expanded, setExpanded] = useState(false);
  const { revise, remove, confirm } = useDraftMutations(draft);
  const busy = revise.isPending || remove.isPending || confirm.isPending;
  const close = () => setDialog(null);

  const single = rows.length === 1;
  const dishId = groupKey(rows[0]);
  const name = single ? targetOf(rows[0]).name : rows[0].dish ?? "Dish";
  const totalGrams = rows.reduce((sum, row) => sum + row.grams, 0);
  const amount = single
    ? amountOf(rows[0], targetOf(rows[0]))
    : `${Math.round(totalGrams)} g`;
  const flags = [...new Set(rows.flatMap((row) => row.flags))];
  const description = single
    ? `${amountOf(rows[0], targetOf(rows[0]))} ${name}${rows[0].said ? ` · “${rows[0].said}”` : ""}`
    : `${name} · ${rows.length} components`;

  return (
    <>
      <Card
        onClick={single ? undefined : () => setExpanded((v) => !v)}
        className={single ? undefined : "cursor-pointer hover:bg-muted/30"}
      >
        <CardContent className="grid gap-2">
          <div className="flex min-w-0 items-center justify-between gap-4 overflow-hidden">
            <p className="min-w-0 truncate font-medium text-foreground">
              <EntryPill>Draft</EntryPill>
              {name}
              {flags.length ? (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <AlertTriangle
                      className="ml-2 inline size-4 align-[-2px] text-amber-600 dark:text-amber-400"
                      aria-label="Needs review"
                    />
                  </TooltipTrigger>
                  <TooltipContent>{flags.join(" · ")}</TooltipContent>
                </Tooltip>
              ) : null}
            </p>
            <div className="flex shrink-0 items-center gap-2">
              <p className="whitespace-nowrap text-muted-foreground">
                {getElapsedTime(draft.created_at)}
              </p>
              {readOnly ? null : (
                <EntryMenu
                  disabled={busy}
                  onConfirm={() => confirm.mutate(rows.map((row) => row.id))}
                  onOpen={setDialog}
                />
              )}
            </div>
          </div>
          <FoodBadges amount={amount} macros={sumMacros(rows)} />
          {expanded && !single && (
            <>
              <Separator className="my-2" />
              <div className="grid gap-1">
                {rows.map((row) => {
                  const target = targetOf(row);
                  const m = macrosOf(target.per_100g, row.grams);
                  return (
                    <div
                      key={row.id}
                      className="flex items-center justify-between gap-4 px-1"
                    >
                      <span className="min-w-0 truncate text-muted-foreground">
                        {target.name}{" "}
                        <span className="text-muted-foreground/70">
                          ({amountOf(row, target)})
                        </span>
                        {row.assumed ? (
                          <span className="ml-2 text-xs">assumed</span>
                        ) : null}
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
      {!readOnly && dialog === "edit" ? (
        <ReviseDialog
          open
          onOpenChange={(open) => !open && close()}
          description={description}
          flags={flags}
          pending={revise.isPending}
          onApply={(instruction) =>
            revise.mutate({ dishId, instruction }, { onSuccess: close })
          }
        />
      ) : null}
      {!readOnly && dialog === "delete" ? (
        <DeleteDialog
          open
          onOpenChange={(open) => !open && close()}
          name={name}
          pending={remove.isPending}
          onDelete={() => remove.mutate(dishId, { onSuccess: close })}
        />
      ) : null}
    </>
  );
}

export function DraftDishes({
  draft,
  readOnly = false,
}: {
  draft: LogDraft;
  readOnly?: boolean;
}) {
  return (
    <div className="grid gap-3">
      {groupRows(draft.rows).map((rows) => (
        <DraftDishCard
          key={`${draft.id}-${groupKey(rows[0])}`}
          draft={draft}
          rows={rows}
          readOnly={readOnly}
        />
      ))}
    </div>
  );
}

/**
 * A draft inside a conversation: the same dishes as on the day's list while
 * it's pending, then a one-line outcome once it has been reviewed.
 */
export function ChatDraft({ draft }: { draft: LogDraft }) {
  const { data } = useDayEntries(draft.day);
  const live = data
    ? data.drafts.find((d) => d.id === draft.id)
    : draft.status === "pending"
      ? draft
      : undefined;
  if (live) return <DraftDishes draft={live} />;
  return (
    <p className="text-sm text-muted-foreground">
      {draft.status === "discarded" ? "Draft discarded." : "Draft reviewed."}
    </p>
  );
}

/** Pending log drafts for a day, one card per dish, awaiting confirmation. */
export function PendingDrafts({ day }: { day: string }) {
  const { data } = useDayEntries(day);
  // Sandbox runs save drafts for debugging; they aren't the user's real logs.
  const drafts = data?.drafts.filter((draft) => draft.via !== "sandbox");
  if (!drafts?.length) return null;
  return drafts.flatMap((draft) =>
    groupRows(draft.rows).map((rows) => (
      <DraftDishCard
        key={`${draft.id}-${groupKey(rows[0])}`}
        draft={draft}
        rows={rows}
      />
    )),
  );
}
