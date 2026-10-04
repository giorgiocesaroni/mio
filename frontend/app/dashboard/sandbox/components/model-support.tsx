"use client";

import { formatPrice } from "@/app/components/model-combobox";
import { Badge } from "@/components/ui/badge";
import { getModelInfo, type ModelInfo } from "@/repository/backend/queries";
import { useQuery } from "@tanstack/react-query";
import { CheckIcon, XIcon } from "lucide-react";

// What the extract and resolve stages ask of their model (see `_complete` in
// backend/src/pipeline/service.py). OpenRouter drops a parameter the model
// doesn't list without an error, so the run goes on without it.
const PIPELINE_PARAMETERS = [
  { parameter: "structured_outputs", label: "Strict JSON schema" },
  { parameter: "reasoning", label: "Reasoning control" },
  { parameter: "temperature", label: "Temperature 0" },
];

function formatContext(tokens: number | null): string | null {
  if (!tokens) return null;
  return tokens >= 1_000_000
    ? `${Number((tokens / 1_000_000).toFixed(1))}M context`
    : `${Math.round(tokens / 1000)}K context`;
}

function Support({ ok, label }: { ok: boolean; label: string }) {
  return (
    <Badge
      variant={ok ? "outline" : "destructive"}
      title={ok ? undefined : "Not supported: OpenRouter drops it from the request"}
    >
      {ok ? <CheckIcon /> : <XIcon />}
      {label}
    </Badge>
  );
}

function Details({ info, photos }: { info: ModelInfo; photos: boolean }) {
  const facts = [
    formatPrice(info) === "varies" ? "price varies" : `${formatPrice(info)} per 1M tokens`,
    formatContext(info.context_length),
  ].filter(Boolean);
  return (
    <div className="grid gap-1.5">
      <p className="text-xs text-muted-foreground">
        <a
          href={`https://openrouter.ai/${info.id}`}
          target="_blank"
          rel="noreferrer"
          className="font-medium text-foreground underline-offset-2 hover:underline"
        >
          {info.name}
        </a>{" "}
        · {facts.join(" · ")}
      </p>
      <div className="flex flex-wrap gap-1.5">
        {photos ? (
          <Support ok={info.input_modalities.includes("image")} label="Photos" />
        ) : null}
        {PIPELINE_PARAMETERS.map(({ parameter, label }) => (
          <Support
            key={parameter}
            ok={info.supported_parameters.includes(parameter)}
            label={label}
          />
        ))}
      </div>
    </div>
  );
}

/** What OpenRouter lists for the model a stage runs with: its price and
 * context, and which of the stage's inputs and parameters it supports. */
export function ModelSupport({
  model,
  photos = false,
}: {
  model: string | undefined;
  photos?: boolean;
}) {
  const { data: info, error } = useQuery({
    queryKey: ["getModelInfo", model],
    queryFn: () => getModelInfo(model!),
    enabled: !!model,
    staleTime: 60 * 60 * 1000,
  });
  if (error) return <p className="text-xs text-destructive">{error.message}</p>;
  if (!info) return <p className="text-xs text-muted-foreground">Loading…</p>;
  return <Details info={info} photos={photos} />;
}
