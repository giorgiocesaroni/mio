"use client";

import { ModelCombobox } from "@/app/components/model-combobox";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  getModelInfo,
  getModelParameters,
  type ModelTask,
} from "@/repository/backend/queries";
import { useQuery } from "@tanstack/react-query";

const PRE = "max-h-72 overflow-auto whitespace-pre-wrap break-all rounded-md bg-muted p-3 font-mono text-[11px] leading-relaxed";

/** The request parameters typed for a stage, or why they can't be sent. */
export function parseParameters(
  text: string,
): { value: Record<string, unknown> } | { error: string } {
  try {
    const value: unknown = JSON.parse(text);
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      return { error: "Parameters must be a JSON object." };
    }
    return { value: value as Record<string, unknown> };
  } catch (e) {
    return { error: (e as Error).message };
  }
}

/** One LLM stage of the sandbox: its model, what OpenRouter lists for it
 * (verbatim), and the request parameters the stage sends, editable.
 * `parameters` null sends the backend's own (shown as the starting text). */
export function StageCard({
  id,
  title,
  description,
  task,
  model,
  onModelChange,
  defaultModel,
  parameters,
  onParametersChange,
  disabled,
}: {
  id: string;
  title: string;
  description: string;
  task: ModelTask;
  model: string | null;
  onModelChange: (model: string | null) => void;
  defaultModel: string | undefined;
  parameters: string | null;
  onParametersChange: (parameters: string | null) => void;
  disabled: boolean;
}) {
  const effective = model ?? defaultModel;
  const { data: entry, error: entryError } = useQuery({
    queryKey: ["getModelInfo", effective],
    queryFn: () => getModelInfo(effective!),
    enabled: !!effective,
    staleTime: 60 * 60 * 1000,
  });
  const { data: sent } = useQuery({
    queryKey: ["getModelParameters", effective],
    queryFn: () => getModelParameters(effective!),
    enabled: !!effective,
    staleTime: 60 * 60 * 1000,
  });

  const text = parameters ?? (sent ? JSON.stringify(sent, null, 2) : "");
  const parsed = parameters === null ? null : parseParameters(parameters);

  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle>
          <Label htmlFor={`${id}-model`}>{title}</Label>
        </CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        <ModelCombobox
          id={`${id}-model`}
          task={task}
          value={model}
          onChange={onModelChange}
          defaultModel={defaultModel}
          disabled={disabled}
        />
        {entryError ? (
          <p className="text-xs text-destructive">{entryError.message}</p>
        ) : (
          <div className="grid gap-3 text-xs sm:grid-cols-2">
            <div className="grid min-w-0 content-start gap-1">
              <p className="text-muted-foreground">OpenRouter: reasoning</p>
              <pre className={PRE}>
                {entry ? JSON.stringify(entry.reasoning ?? null, null, 2) : "Loading…"}
              </pre>
            </div>
            <div className="grid min-w-0 content-start gap-1">
              <p className="text-muted-foreground">OpenRouter: supported_parameters</p>
              <pre className={PRE}>
                {entry ? JSON.stringify(entry.supported_parameters ?? null, null, 2) : "Loading…"}
              </pre>
            </div>
          </div>
        )}
        <div className="grid gap-1 text-xs">
          <div className="flex items-center gap-2">
            <Label htmlFor={`${id}-parameters`} className="text-xs font-normal text-muted-foreground">
              Request parameters {parameters === null ? "(the backend's)" : "(edited)"}
            </Label>
            {parameters !== null ? (
              <Button
                variant="ghost"
                size="sm"
                className="ml-auto h-6 px-2 text-xs"
                onClick={() => onParametersChange(null)}
                disabled={disabled}
              >
                Reset
              </Button>
            ) : null}
          </div>
          <Textarea
            id={`${id}-parameters`}
            value={text}
            onChange={(e) => onParametersChange(e.target.value)}
            disabled={disabled || (parameters === null && !sent)}
            spellCheck={false}
            className="min-h-28 font-mono text-[11px] leading-relaxed"
          />
          {parsed && "error" in parsed ? (
            <p className="text-destructive">{parsed.error}</p>
          ) : null}
        </div>
        <details className="text-xs">
          <summary className="cursor-pointer select-none text-muted-foreground hover:text-foreground">
            Raw data
          </summary>
          <pre className="mt-2 max-h-96 overflow-auto rounded-md bg-muted p-3 font-mono text-[11px] leading-relaxed">
            {entry ? JSON.stringify(entry, null, 2) : "Loading…"}
          </pre>
        </details>
      </CardContent>
    </Card>
  );
}
