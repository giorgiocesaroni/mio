"use client";

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
import { getModelParameters } from "@/repository/backend/queries";
import { useQuery } from "@tanstack/react-query";

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

/** One LLM stage of the sandbox: the request parameters it sends, editable.
 * `parameters` null sends the backend's own (shown as the starting text). */
export function StageCard({
  id,
  title,
  description,
  parameters,
  onParametersChange,
  disabled,
}: {
  id: string;
  title: string;
  description: string;
  parameters: string | null;
  onParametersChange: (parameters: string | null) => void;
  disabled: boolean;
}) {
  const { data: sent } = useQuery({
    queryKey: ["getModelParameters"],
    queryFn: getModelParameters,
    staleTime: 60 * 60 * 1000,
  });

  const text = parameters ?? (sent ? JSON.stringify(sent, null, 2) : "");
  const parsed = parameters === null ? null : parseParameters(parameters);

  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
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
      </CardContent>
    </Card>
  );
}
