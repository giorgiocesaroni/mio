"use client";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Textarea } from "@/components/ui/textarea";
import { deleteLogs, reviseLogs } from "@/repository/backend/queries";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Check,
  Loader2,
  MoreVertical,
  Pencil,
  Trash2,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { DAY_ENTRIES_QUERY_KEY } from "./day-entries";
import { readModelPreferences } from "@/lib/model-preferences";

/** The label before an entry's name, e.g. "Recipe" or "Draft". */
export function EntryPill({ children }: { children: React.ReactNode }) {
  return (
    <span className="mr-2 rounded-md bg-muted px-2 py-1 text-xs font-normal text-muted-foreground">
      {children}
    </span>
  );
}

export type EntryDialog = "edit" | "delete" | null;

/** The ⋮ menu every entry card has: Confirm (drafts only), Edit, Delete…. */
export function EntryMenu({
  onConfirm,
  onOpen,
  disabled,
}: {
  onConfirm?: () => void;
  onOpen: (dialog: Exclude<EntryDialog, null>) => void;
  disabled?: boolean;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon-xs"
          className="text-muted-foreground hover:text-foreground"
          disabled={disabled}
          aria-label="Entry actions"
          // Cards can be clickable (recipes expand); the menu shouldn't toggle them.
          onClick={(e) => e.stopPropagation()}
        >
          {disabled ? <Loader2 className="animate-spin" /> : <MoreVertical />}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
        {onConfirm ? (
          <DropdownMenuItem onSelect={onConfirm}>
            <Check />
            Confirm
          </DropdownMenuItem>
        ) : null}
        <DropdownMenuItem onSelect={() => onOpen("edit")}>
          <Pencil />
          Edit
        </DropdownMenuItem>
        <DropdownMenuItem
          variant="destructive"
          onSelect={() => onOpen("delete")}
        >
          <Trash2 />
          Delete…
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/** Corrections are described in words and applied by the LLM, never by hand. */
export function ReviseDialog({
  open,
  onOpenChange,
  description,
  pending,
  onApply,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  description: string;
  pending: boolean;
  onApply: (instruction: string) => void;
}) {
  const [instruction, setInstruction] = useState("");
  const canApply = !pending && instruction.trim().length > 0;
  const apply = () => canApply && onApply(instruction.trim());

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent onClick={(e) => e.stopPropagation()}>
        <DialogHeader>
          <DialogTitle>Edit entry</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <Textarea
          autoFocus
          value={instruction}
          disabled={pending}
          onChange={(e) => setInstruction(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              apply();
            }
          }}
          placeholder="What should change? E.g. “it was two slices” or “the wholegrain one”"
          aria-label="Correction"
        />
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button disabled={!canApply} onClick={apply}>
            {pending ? <Loader2 className="animate-spin" /> : null}
            Apply
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function DeleteDialog({
  open,
  onOpenChange,
  name,
  pending,
  onDelete,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  name: string;
  pending: boolean;
  onDelete: () => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent onClick={(e) => e.stopPropagation()}>
        <DialogHeader>
          <DialogTitle>Delete entry?</DialogTitle>
          <DialogDescription>{name} will be removed.</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button variant="destructive" disabled={pending} onClick={onDelete}>
            {pending ? <Loader2 className="animate-spin" /> : null}
            Delete
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

const LOG_QUERY_KEYS = [
  DAY_ENTRIES_QUERY_KEY,
  ["getDailyMacrosView"],
  ["getDailyMacrosTrend"],
];

export function useInvalidateLogs() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all(
      LOG_QUERY_KEYS.map((queryKey) =>
        queryClient.invalidateQueries({ queryKey }),
      ),
    );
}

/** Edit and delete for a logged entry (one card: one log, or a recipe's logs). */
export function useLogEntryActions(day: string, logIds: string[]) {
  const invalidateLogs = useInvalidateLogs();
  const [dialog, setDialog] = useState<EntryDialog>(null);

  const revise = useMutation({
    mutationFn: (instruction: string) =>
      reviseLogs(day, logIds, instruction, readModelPreferences()),
    onSuccess: async (result) => {
      const failed = result.results.filter((r) => !r.success);
      if (failed.length)
        toast.error(`Update failed: ${failed.map((f) => f.error).join("; ")}`);
      setDialog(null);
      await invalidateLogs();
    },
    onError: (err) => toast.error(err.message),
  });
  const remove = useMutation({
    mutationFn: () => deleteLogs(logIds),
    onSuccess: async () => {
      setDialog(null);
      await invalidateLogs();
    },
    onError: (err) => toast.error(err.message),
  });
  return { dialog, setDialog, revise, remove };
}
