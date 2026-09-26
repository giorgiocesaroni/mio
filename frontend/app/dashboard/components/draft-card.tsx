"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import {
  confirmDraft,
  discardDraft,
  getDrafts,
  updateDraft,
  type DraftAlternative,
  type DraftRow,
  type DraftRowEdit,
  type DraftUnit,
  type LogDraft,
  type MealType,
} from "@/repository/backend/queries";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Loader2, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

const MEAL_TYPES: MealType[] = ["breakfast", "lunch", "snack", "dinner"];

function round(value: number, digits = 0): number {
  const f = 10 ** digits;
  return Math.round(value * f) / f;
}

function targetOf(row: DraftRow): DraftAlternative {
  return row.alternatives.find((a) => a.key === row.target)!;
}

function toEdit(row: DraftRow): DraftRowEdit {
  const { id, target, quantity, unit, serving_size_id, meal_type } = row;
  return { id, target, quantity, unit, serving_size_id, meal_type };
}

/** Unit options for a target, encoded as "grams" | "recipe" | "serving:<id>". */
function unitOptions(target: DraftAlternative) {
  const options = [{ value: "grams", label: "g" }];
  for (const s of target.serving_sizes ?? [])
    options.push({ value: `serving:${s.id}`, label: `× ${s.label} (${round(s.grams)} g)` });
  if (target.kind === "recipe")
    options.push({ value: "recipe", label: `× recipe (${round(target.total_g ?? 0)} g)` });
  return options;
}

function unitValue(row: DraftRow): string {
  return row.unit === "serving" ? `serving:${row.serving_size_id}` : row.unit;
}

/** Switch unit while keeping the same weight. */
function withUnit(row: DraftRow, value: string): DraftRowEdit {
  const target = targetOf(row);
  const edit = toEdit(row);
  if (value.startsWith("serving:")) {
    const id = value.slice("serving:".length);
    const serving = target.serving_sizes?.find((s) => s.id === id);
    const quantity = serving ? round(row.grams / serving.grams, 1) : 1;
    return { ...edit, unit: "serving", serving_size_id: id, quantity: quantity || 1 };
  }
  const unit = value as DraftUnit;
  const quantity =
    unit === "recipe"
      ? round(row.grams / (target.total_g || 1), 2) || 1
      : round(row.grams) || 100;
  return { ...edit, unit, serving_size_id: null, quantity };
}

/** Swap the matched food while keeping the same weight. */
function withTarget(row: DraftRow, key: string): DraftRowEdit {
  return {
    ...toEdit(row),
    target: key,
    unit: "grams",
    serving_size_id: null,
    quantity: round(row.grams) || 100,
  };
}

function alternativeLabel(alt: DraftAlternative): string {
  const brand = alt.brand ? ` (${alt.brand})` : "";
  if (alt.kind === "new") return `New: ${alt.name}${brand}, estimated`;
  if (alt.kind === "recipe") return `Recipe: ${alt.name}`;
  return `${alt.name}${brand}`;
}

function Macros({ macros }: { macros: DraftRow["macros"] }) {
  return (
    <span className="whitespace-nowrap text-xs tabular-nums text-muted-foreground">
      {round(macros.calories_kcal)} kcal · P {round(macros.protein_g)} · C{" "}
      {round(macros.carbs_g)} · F {round(macros.fat_g)}
    </span>
  );
}

function QuantityInput({
  value,
  disabled,
  onCommit,
}: {
  value: number;
  disabled: boolean;
  onCommit: (value: number) => void;
}) {
  // Local text so typing doesn't round-trip to the backend on every key; the
  // parent keys this input by `value`, so a saved change resets it.
  const [text, setText] = useState(String(value));
  const commit = () => {
    const parsed = Number(text.replace(",", "."));
    if (Number.isFinite(parsed) && parsed > 0 && parsed !== value) onCommit(parsed);
    else setText(String(value));
  };
  return (
    <Input
      inputMode="decimal"
      value={text}
      disabled={disabled}
      onChange={(e) => setText(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
      className="h-8 w-20 tabular-nums"
      aria-label="Quantity"
    />
  );
}

function DraftRowEditor({
  row,
  disabled,
  onChange,
  onRemove,
}: {
  row: DraftRow;
  disabled: boolean;
  onChange: (edit: DraftRowEdit) => void;
  onRemove: () => void;
}) {
  const target = targetOf(row);
  return (
    <div className="grid gap-2">
      <div className="flex items-center gap-2">
        <Select
          value={row.target}
          disabled={disabled}
          onValueChange={(key) => onChange(withTarget(row, key))}
        >
          <SelectTrigger className="min-w-0 flex-1 font-medium">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {row.alternatives.map((alt) => (
              <SelectItem key={alt.key} value={alt.key}>
                <span className="truncate">{alternativeLabel(alt)}</span>
                {alt.probability !== null && alt.probability >= 0.01 ? (
                  <span className="ml-auto pl-3 text-xs tabular-nums text-muted-foreground">
                    {Math.round(alt.probability * 100)}%
                  </span>
                ) : null}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          variant="ghost"
          size="icon"
          disabled={disabled}
          onClick={onRemove}
          aria-label="Remove row"
        >
          <X />
        </Button>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <QuantityInput
          key={row.quantity}
          value={row.quantity}
          disabled={disabled}
          onCommit={(quantity) => onChange({ ...toEdit(row), quantity })}
        />
        <Select
          value={unitValue(row)}
          disabled={disabled}
          onValueChange={(value) => onChange(withUnit(row, value))}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {unitOptions(target).map((o) => (
              <SelectItem key={o.value} value={o.value}>
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={row.meal_type}
          disabled={disabled}
          onValueChange={(meal_type) =>
            onChange({ ...toEdit(row), meal_type: meal_type as MealType })
          }
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {MEAL_TYPES.map((m) => (
              <SelectItem key={m} value={m} className="capitalize">
                {m}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span className="ml-auto">
          <Macros macros={row.macros} />
        </span>
      </div>
      {row.said ? (
        <p className="text-xs text-muted-foreground">“{row.said}”</p>
      ) : null}
      {row.flags.map((flag) => (
        <p
          key={flag}
          className="flex items-center gap-1.5 text-xs text-amber-700 dark:text-amber-400"
        >
          <AlertTriangle className="size-3.5 shrink-0" />
          {flag}
        </p>
      ))}
    </div>
  );
}

export function draftsQueryKey(day: string) {
  return ["drafts", day] as const;
}

/** Pending log drafts for a day, each awaiting confirmation. */
export function PendingDrafts({ day }: { day: string }) {
  const { data: drafts } = useQuery({
    queryKey: draftsQueryKey(day),
    queryFn: () => getDrafts(day),
  });
  if (!drafts?.length) return null;
  return (
    <div className="grid gap-4">
      {drafts.map((draft) => (
        <DraftCard key={draft.id} draft={draft} />
      ))}
    </div>
  );
}

function DraftCard({ draft }: { draft: LogDraft }) {
  const queryClient = useQueryClient();
  const queryKey = draftsQueryKey(draft.day);

  const setDraft = (updated: LogDraft | null) =>
    queryClient.setQueryData<LogDraft[]>(queryKey, (prev) =>
      (prev ?? []).flatMap((d) =>
        d.id !== draft.id ? [d] : updated ? [updated] : [],
      ),
    );

  const update = useMutation({
    mutationFn: (rows: DraftRowEdit[]) => updateDraft(draft.id, rows),
    onSuccess: (updated) => setDraft(updated),
    onError: (err) => toast.error(err.message),
  });
  const discard = useMutation({
    mutationFn: () => discardDraft(draft.id),
    onSuccess: () => setDraft(null),
    onError: (err) => toast.error(err.message),
  });
  const confirm = useMutation({
    mutationFn: () => confirmDraft(draft.id),
    onSuccess: async (result) => {
      setDraft(null);
      const failed = result.results.filter((r) => !r.success);
      if (failed.length)
        toast.error(
          `${failed.length} of ${result.results.length} entries failed: ${failed
            .map((f) => f.error)
            .join("; ")}`,
        );
      else toast.success("Logged.");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["getDailyFoodLogsWithFoodsView"] }),
        queryClient.invalidateQueries({ queryKey: ["getDailyMacrosView"] }),
        queryClient.invalidateQueries({ queryKey: ["getDailyMacrosTrend"] }),
      ]);
    },
    onError: (err) => toast.error(err.message),
  });

  const busy = update.isPending || discard.isPending || confirm.isPending;
  const edits = draft.rows.map(toEdit);

  const changeRow = (edit: DraftRowEdit) =>
    update.mutate(edits.map((e) => (e.id === edit.id ? edit : e)));
  const removeRow = (id: string) => {
    const remaining = edits.filter((e) => e.id !== id);
    if (remaining.length) update.mutate(remaining);
    else discard.mutate();
  };

  const total = draft.rows.reduce(
    (acc, r) => ({
      calories_kcal: acc.calories_kcal + r.macros.calories_kcal,
      protein_g: acc.protein_g + r.macros.protein_g,
      carbs_g: acc.carbs_g + r.macros.carbs_g,
      fat_g: acc.fat_g + r.macros.fat_g,
    }),
    { calories_kcal: 0, protein_g: 0, carbs_g: 0, fat_g: 0 },
  );
  const flagged = draft.rows.filter((r) => r.flags.length).length;

  return (
    <Card className="border-dashed">
      <CardContent className="grid gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="secondary">Draft</Badge>
          {flagged ? (
            <Badge variant="outline">
              {flagged} to review
            </Badge>
          ) : null}
          {busy ? (
            <Loader2 className="size-4 animate-spin text-muted-foreground" />
          ) : null}
          {draft.message ? (
            <p className="w-full truncate text-sm text-muted-foreground">
              {draft.message}
            </p>
          ) : null}
        </div>
        {draft.rows.map((row, index) => (
          <div key={row.id} className="grid gap-4">
            {index > 0 ? <Separator /> : null}
            <DraftRowEditor
              row={row}
              disabled={busy}
              onChange={changeRow}
              onRemove={() => removeRow(row.id)}
            />
          </div>
        ))}
        <Separator />
        <div className="flex flex-wrap items-center gap-2">
          <Macros macros={total} />
          <div className="ml-auto flex gap-2">
            <Button
              variant="ghost"
              disabled={busy}
              onClick={() => discard.mutate()}
            >
              Discard
            </Button>
            <Button disabled={busy} onClick={() => confirm.mutate()}>
              Confirm
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
