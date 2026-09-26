"use client";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type {
  SandboxDoneStep,
  SandboxStageName,
  SandboxStageStep,
} from "@/repository/backend/queries";
import { Loader2 } from "lucide-react";

export const STAGES: { name: SandboxStageName; label: string; kind: string }[] =
  [
    { name: "normalize", label: "Normalize", kind: "code" },
    { name: "route", label: "Route", kind: "Jev" },
    { name: "extract", label: "Extract", kind: "LLM" },
    { name: "retrieve", label: "Retrieve", kind: "code" },
    { name: "resolve", label: "Resolve", kind: "LLM" },
    { name: "draft", label: "Draft", kind: "database" },
  ];

export type Run = {
  id: string;
  text: string;
  images: string[];
  model?: string;
  stages: SandboxStageStep[];
  done?: SandboxDoneStep;
  error?: string;
};

export function formatCost(cost: number): string {
  return cost === 0 ? "$0" : `$${cost.toFixed(cost < 0.001 ? 6 : 4)}`;
}

const OUTCOME_LABELS: Record<SandboxDoneStep["outcome"], string> = {
  drafted: "Drafted",
  handoff: "Handoff",
  nothing: "Nothing",
  error: "Error",
};

type JevAnswer =
  | {
      type: "choice";
      choice: string;
      confidence: number;
      probabilities: Record<string, number>;
    }
  | { type: "noul"; noul: number };

type JevDebug = {
  model: string;
  questions: Record<string, { criteria?: Record<string, unknown> }>;
  answers: Record<string, JevAnswer>;
};

function ProbabilityBar({
  label,
  value,
  highlight,
}: {
  label: string;
  value: number;
  highlight?: boolean;
}) {
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_6rem_3rem] items-center gap-2 text-xs">
      <span
        className={cn(
          "truncate",
          highlight ? "font-medium" : "text-muted-foreground",
        )}
        title={label}
      >
        {label}
      </span>
      <div className="h-1.5 overflow-hidden rounded-full bg-muted">
        <div
          className={cn(
            "h-full rounded-full",
            highlight ? "bg-primary" : "bg-muted-foreground/40",
          )}
          style={{ width: `${Math.round(value * 100)}%` }}
        />
      </div>
      <span className="text-right tabular-nums text-muted-foreground">
        {value.toFixed(2)}
      </span>
    </div>
  );
}

/** Every Jev answer with its full distribution, labelled by criteria text. */
function JevAnswers({ jev }: { jev: JevDebug }) {
  return (
    <div className="grid gap-3">
      {Object.entries(jev.answers).map(([key, answer]) => {
        const criteria = jev.questions[key]?.criteria ?? {};
        const optionLabel = (option: string) => {
          const description = criteria[option];
          return typeof description === "string"
            ? `${option} · ${description}`
            : option;
        };
        return (
          <div key={key} className="grid gap-1">
            <div className="flex items-center gap-2 text-xs">
              <code className="font-medium">{key}</code>
              {answer.type === "choice" ? (
                <span className="text-muted-foreground">
                  → {answer.choice} · confidence{" "}
                  {answer.confidence.toFixed(2)}
                </span>
              ) : null}
            </div>
            {answer.type === "choice" ? (
              Object.entries(answer.probabilities)
                .sort(([, a], [, b]) => b - a)
                .map(([option, p]) => (
                  <ProbabilityBar
                    key={option}
                    label={optionLabel(option)}
                    value={p}
                    highlight={option === answer.choice}
                  />
                ))
            ) : (
              <ProbabilityBar label="yes" value={answer.noul} highlight />
            )}
          </div>
        );
      })}
    </div>
  );
}

function jevOf(stage: SandboxStageStep): JevDebug | null {
  const data = stage.data as { jev?: JevDebug | null } | null;
  return data?.jev ?? null;
}

function StageRow({
  label,
  kind,
  stage,
  isPending,
}: {
  label: string;
  kind: string;
  stage?: SandboxStageStep;
  isPending: boolean;
}) {
  const jev = stage ? jevOf(stage) : null;
  return (
    <li className="grid grid-cols-[1rem_minmax(0,1fr)] gap-3">
      <span
        className={cn(
          "mt-1.5 size-2.5 rounded-full border",
          !stage && "border-muted-foreground/40",
          stage?.status === "ok" && "border-primary bg-primary",
          stage?.status === "skipped" && "border-muted-foreground/60",
          stage?.status === "error" && "border-destructive bg-destructive",
        )}
      />
      <div className="grid min-w-0 gap-1 pb-4">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="font-medium">{label}</span>
          <Badge variant="outline">{stage?.model ?? kind}</Badge>
          {stage?.status === "skipped" ? (
            <Badge variant="secondary">skipped</Badge>
          ) : null}
          {stage?.status === "error" ? (
            <Badge variant="destructive">error</Badge>
          ) : null}
          {isPending ? (
            <Loader2 className="size-3.5 animate-spin text-muted-foreground" />
          ) : null}
          {stage ? (
            <span className="ml-auto text-xs tabular-nums text-muted-foreground">
              {stage.ms} ms
              {stage.cost ? ` · ${formatCost(stage.cost)}` : ""}
            </span>
          ) : null}
        </div>
        {stage ? (
          <p className="whitespace-pre-wrap break-words text-sm text-muted-foreground">
            {stage.summary}
          </p>
        ) : null}
        {jev ? (
          <div className="mt-1 rounded-md border p-3">
            <JevAnswers jev={jev} />
          </div>
        ) : null}
        {stage?.data ? (
          <details className="text-xs">
            <summary className="cursor-pointer select-none text-muted-foreground hover:text-foreground">
              Raw data
            </summary>
            <pre className="mt-2 max-h-96 overflow-auto rounded-md bg-muted p-3 font-mono text-[11px] leading-relaxed">
              {JSON.stringify(stage.data, null, 2)}
            </pre>
          </details>
        ) : null}
      </div>
    </li>
  );
}

export function PipelineRun({ run }: { run: Run }) {
  const isRunning = !run.done && !run.error;
  const byName = new Map(run.stages.map((s) => [s.name, s]));
  // Stages after a handoff or an early exit never arrive; only the next
  // expected stage shows a spinner while the run is in flight.
  const nextIndex = STAGES.findIndex((s) => !byName.has(s.name));
  const visible = run.done
    ? STAGES.filter((s) => byName.has(s.name))
    : STAGES;

  return (
    <section className="grid gap-4 rounded-xl border p-4">
      <header className="grid gap-2">
        <div className="flex flex-wrap items-center gap-2">
          {run.done ? (
            <Badge
              variant={run.done.outcome === "error" ? "destructive" : "default"}
            >
              {OUTCOME_LABELS[run.done.outcome]}
            </Badge>
          ) : run.error ? (
            <Badge variant="destructive">Error</Badge>
          ) : (
            <Badge variant="secondary">Running</Badge>
          )}
          {run.done ? (
            <span className="ml-auto text-xs tabular-nums text-muted-foreground">
              {(run.done.total_ms / 1000).toFixed(1)} s ·{" "}
              {formatCost(run.done.total_cost)}
            </span>
          ) : null}
        </div>
        {run.text ? (
          <p className="whitespace-pre-wrap text-sm">{run.text}</p>
        ) : null}
        {run.images.length ? (
          <div className="flex flex-wrap gap-2">
            {run.images.map((url) => (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                key={url}
                src={url}
                alt=""
                className="size-16 rounded-md border object-cover"
              />
            ))}
          </div>
        ) : null}
      </header>
      <ol className="grid">
        {visible.map((s) => (
          <StageRow
            key={s.name}
            label={s.label}
            kind={s.kind}
            stage={byName.get(s.name)}
            isPending={isRunning && STAGES.indexOf(s) === nextIndex}
          />
        ))}
      </ol>
      {run.done ? (
        <p className="whitespace-pre-wrap rounded-md bg-muted p-3 text-sm">
          {run.done.message}
        </p>
      ) : null}
      {run.error ? (
        <p className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {run.error}
        </p>
      ) : null}
    </section>
  );
}
