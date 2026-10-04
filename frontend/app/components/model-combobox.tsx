"use client";

import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  searchModels,
  type ModelOption,
  type ModelTask,
} from "@/repository/backend/queries";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { CheckIcon, ChevronsUpDownIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { cn } from "cn";

const SEARCH_DEBOUNCE_MS = 250;

/** A model id without its provider, e.g. 'claude-sonnet-5.5'. */
export function modelLabel(id: string): string {
  return id.split("/").pop() ?? id;
}

export function usd(value: number): string {
  if (value === 0) return "$0";
  if (value < 0.01) return "<$0.01";
  if (value < 1) return `$${value.toFixed(2)}`;
  if (value < 10) return `$${Number(value.toFixed(2))}`;
  return `$${Math.round(value)}`;
}

/** e.g. '$0.10 / $0.50'; routers, priced as whatever they route to, vary. */
export function formatPrice(option: ModelOption): string {
  const { input_per_million: input, output_per_million: output } = option;
  if (input === null || output === null) return "varies";
  if (input === 0 && output === 0) return "free";
  return `${usd(input)} / ${usd(output)}`;
}

/** Picks one of the OpenRouter models that can do `task`, searched on the
 * server as the user types. `value` null is the configured default. */
export function ModelCombobox({
  id,
  task,
  value,
  onChange,
  defaultModel,
  disabled,
}: {
  id?: string;
  task: ModelTask;
  value: string | null;
  onChange: (value: string | null) => void;
  defaultModel?: string;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(query.trim()), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [query]);

  const { data: options, isFetching, error } = useQuery({
    queryKey: ["searchModels", task, debounced],
    queryFn: () => searchModels(task, debounced),
    enabled: open,
    staleTime: 5 * 60 * 1000,
    placeholderData: keepPreviousData,
  });

  const defaultLabel = defaultModel ? `Default (${modelLabel(defaultModel)})` : "Default";
  const select = (model: string | null) => {
    onChange(model);
    setOpen(false);
    setQuery("");
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          id={id}
          variant="outline"
          role="combobox"
          aria-expanded={open}
          disabled={disabled}
          className="h-8 max-w-full justify-between gap-2 font-normal"
        >
          <span className="truncate">{value ? modelLabel(value) : defaultLabel}</span>
          <ChevronsUpDownIcon className="size-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80 max-w-[calc(100vw-2rem)] p-0" align="start">
        {/* Filtering happens on the server, over the whole catalog. */}
        <Command shouldFilter={false}>
          <CommandInput
            placeholder="Search models…"
            value={query}
            onValueChange={setQuery}
          />
          <CommandList>
            <CommandEmpty>
              {error
                ? `Couldn't load models: ${(error as Error).message}`
                : isFetching
                  ? "Searching…"
                  : "No model can do this."}
            </CommandEmpty>
            {!debounced ? (
              <CommandGroup>
                <CommandItem value="__default" onSelect={() => select(null)}>
                  <CheckIcon className={cn("size-4", value ? "opacity-0" : "opacity-100")} />
                  {defaultLabel}
                </CommandItem>
              </CommandGroup>
            ) : null}
            {options?.length ? (
              <CommandGroup heading="Price per 1M tokens in / out">
                {options.map((option) => (
                  <CommandItem
                    key={option.id}
                    value={option.id}
                    onSelect={() => select(option.id)}
                  >
                    <CheckIcon
                      className={cn("size-4", value === option.id ? "opacity-100" : "opacity-0")}
                    />
                    <div className="grid min-w-0 flex-1">
                      <span className="truncate">{option.name}</span>
                      <span className="truncate text-xs text-muted-foreground">
                        {option.id}
                      </span>
                    </div>
                    <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                      {formatPrice(option)}
                    </span>
                  </CommandItem>
                ))}
              </CommandGroup>
            ) : null}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
