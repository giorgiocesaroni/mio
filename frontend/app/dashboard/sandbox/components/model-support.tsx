"use client";

import { getModelInfo } from "@/repository/backend/queries";
import { useQuery } from "@tanstack/react-query";

/** OpenRouter's catalog entry for the model a stage runs with, untouched:
 * its inputs, `supported_parameters` (any other parameter is dropped from
 * the request without an error), pricing and context. */
export function ModelSupport({ model }: { model: string | undefined }) {
  const { data: entry, error } = useQuery({
    queryKey: ["getModelInfo", model],
    queryFn: () => getModelInfo(model!),
    enabled: !!model,
    staleTime: 60 * 60 * 1000,
  });
  if (error) return <p className="text-xs text-destructive">{error.message}</p>;
  return (
    <details className="text-xs">
      <summary className="cursor-pointer select-none text-muted-foreground hover:text-foreground">
        Raw data
      </summary>
      <pre className="mt-2 max-h-96 overflow-auto rounded-md bg-muted p-3 font-mono text-[11px] leading-relaxed">
        {entry ? JSON.stringify(entry, null, 2) : "Loading…"}
      </pre>
    </details>
  );
}
