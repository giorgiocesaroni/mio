"use client";

import { Card, CardContent } from "@/components/ui/card";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  confirmDraft,
  deleteDraftRow,
  reviseDraftRow,
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

function macrosOf(per100g: Per100g, grams: number): Macros {
  return {
    calories: (per100g.calories_kcal * grams) / 100,
    protein: (per100g.protein_g * grams) / 100,
    carbs: (per100g.carbs_g * grams) / 100,
    fat: (per100g.fat_g * grams) / 100,
  };
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

function useDraftRowMutations(draft: LogDraft) {
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
      rowId,
      instruction,
    }: {
      rowId: string;
      instruction: string;
    }) => reviseDraftRow(draft.id, rowId, instruction),
    onSuccess: (updated) => setDraft(updated),
    onError: (err) => toast.error(err.message),
  });
  const remove = useMutation({
    mutationFn: (rowId: string) => deleteDraftRow(draft.id, rowId),
    onSuccess: ({ draft: updated }) => setDraft(updated),
    onError: (err) => toast.error(err.message),
  });
  const confirm = useMutation({
    mutationFn: (rowId: string) => confirmDraft(draft.id, [rowId]),
    onSuccess: async (result) => {
      const failed = result.results.filter((r) => !r.success);
      if (failed.length)
        toast.error(`Logging failed: ${failed.map((f) => f.error).join("; ")}`);
      // The day's drafts and logs are one query, so the draft row and its new
      // log swap in a single update.
      await invalidateLogs();
    },
    onError: (err) => toast.error(err.message),
  });
  return { revise, remove, confirm };
}

function DraftEntryCard({ draft, row }: { draft: LogDraft; row: DraftRow }) {
  const [dialog, setDialog] = useState<EntryDialog>(null);
  const { revise, remove, confirm } = useDraftRowMutations(draft);
  const busy = revise.isPending || remove.isPending || confirm.isPending;
  const target = targetOf(row);
  const close = () => setDialog(null);

  return (
    <>
      <Card>
        <CardContent className="grid gap-2">
          <div className="flex min-w-0 items-center justify-between gap-4 overflow-hidden">
            <p className="min-w-0 truncate font-medium text-foreground">
              <EntryPill>Draft</EntryPill>
              {target.name}
              {row.flags.length ? (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <AlertTriangle
                      className="ml-2 inline size-4 align-[-2px] text-amber-600 dark:text-amber-400"
                      aria-label="Needs review"
                    />
                  </TooltipTrigger>
                  <TooltipContent>{row.flags.join(" · ")}</TooltipContent>
                </Tooltip>
              ) : null}
            </p>
            <div className="flex shrink-0 items-center gap-2">
              <p className="whitespace-nowrap text-muted-foreground">
                {getElapsedTime(draft.created_at)}
              </p>
              <EntryMenu
                disabled={busy}
                onConfirm={() => confirm.mutate(row.id)}
                onOpen={setDialog}
              />
            </div>
          </div>
          <FoodBadges
            amount={amountOf(row, target)}
            macros={macrosOf(target.per_100g, row.grams)}
          />
        </CardContent>
      </Card>
      {dialog === "edit" ? (
        <ReviseDialog
          open
          onOpenChange={(open) => !open && close()}
          description={`${amountOf(row, target)} ${target.name}${row.said ? ` · “${row.said}”` : ""}`}
          flags={row.flags}
          pending={revise.isPending}
          onApply={(instruction) =>
            revise.mutate({ rowId: row.id, instruction }, { onSuccess: close })
          }
        />
      ) : null}
      {dialog === "delete" ? (
        <DeleteDialog
          open
          onOpenChange={(open) => !open && close()}
          name={target.name}
          pending={remove.isPending}
          onDelete={() => remove.mutate(row.id, { onSuccess: close })}
        />
      ) : null}
    </>
  );
}

/**
 * A draft inside a conversation: the same entries as on the day's list while
 * it's pending, then a one-line outcome once it has been reviewed.
 */
export function ChatDraft({ draft }: { draft: LogDraft }) {
  const { data } = useDayEntries(draft.day);
  const live = data
    ? data.drafts.find((d) => d.id === draft.id)
    : draft.status === "pending"
      ? draft
      : undefined;
  if (live)
    return (
      <div className="grid gap-3">
        {live.rows.map((row) => (
          <DraftEntryCard key={`${live.id}-${row.id}`} draft={live} row={row} />
        ))}
      </div>
    );
  return (
    <p className="text-sm text-muted-foreground">
      {draft.status === "discarded" ? "Draft discarded." : "Draft reviewed."}
    </p>
  );
}

/** Pending log drafts for a day, one entry per food, awaiting confirmation. */
export function PendingDrafts({ day }: { day: string }) {
  const { data } = useDayEntries(day);
  const drafts = data?.drafts;
  if (!drafts?.length) return null;
  return drafts.flatMap((draft) =>
    draft.rows.map((row) => (
      <DraftEntryCard key={`${draft.id}-${row.id}`} draft={draft} row={row} />
    )),
  );
}
