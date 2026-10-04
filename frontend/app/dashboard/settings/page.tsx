"use client";

import { ModelCombobox } from "@/app/components/model-combobox";
import { DashboardPage } from "@/app/dashboard/components/dashboard-page";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  getModelDefaults,
  setModelPreferences,
  type ModelChoices,
  type ModelTask,
} from "@/repository/backend/queries";
import { getModelPreferences } from "@/repository/supabase/queries";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

const PREFERENCES_QUERY_KEY = ["getModelPreferences"];

const TASKS: { task: ModelTask; label: string; description: string }[] = [
  {
    task: "agent",
    label: "Chat",
    description: "Answers questions and handles what isn't a new food log.",
  },
  {
    task: "extract_photo",
    label: "Reading photos",
    description: "Turns a meal photo (and its text) into foods and amounts.",
  },
  {
    task: "extract_text",
    label: "Reading text",
    description: "Turns a written or spoken meal into foods and amounts.",
  },
  {
    task: "resolve",
    label: "Matching foods",
    description: "Matches each food to your saved foods and recipes.",
  },
  {
    task: "edit",
    label: "Corrections",
    description: "Applies a correction to a draft or a logged entry.",
  },
];

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const { data: preferences } = useQuery({
    queryKey: PREFERENCES_QUERY_KEY,
    queryFn: getModelPreferences,
  });
  const { data: defaults } = useQuery({
    queryKey: ["getModelDefaults"],
    queryFn: getModelDefaults,
    staleTime: Infinity,
  });

  const save = useMutation({
    mutationFn: setModelPreferences,
    onMutate: async (next: ModelChoices) => {
      await queryClient.cancelQueries({ queryKey: PREFERENCES_QUERY_KEY });
      const previous = queryClient.getQueryData<ModelChoices>(PREFERENCES_QUERY_KEY);
      queryClient.setQueryData(PREFERENCES_QUERY_KEY, next);
      return { previous };
    },
    onError: (err, _next, context) => {
      queryClient.setQueryData(PREFERENCES_QUERY_KEY, context?.previous);
      toast.error(`Couldn't save: ${err instanceof Error ? err.message : String(err)}`);
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: PREFERENCES_QUERY_KEY }),
  });

  const pick = (task: ModelTask, model: string | null) => {
    const next = { ...preferences };
    if (model) next[task] = model;
    else delete next[task];
    save.mutate(next);
  };

  return (
    <DashboardPage title="Settings" bodyClassName="gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Models</CardTitle>
          <CardDescription>
            The models the app uses for each task, from OpenRouter. Only models
            that can do a task are listed. The sandbox picks its own.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-5">
          {TASKS.map(({ task, label, description }) => (
            <div
              key={task}
              className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2"
            >
              <div className="grid min-w-0 gap-0.5">
                <Label htmlFor={`model-${task}`}>{label}</Label>
                <p className="text-sm text-muted-foreground">{description}</p>
              </div>
              <ModelCombobox
                id={`model-${task}`}
                task={task}
                value={preferences?.[task] ?? null}
                onChange={(model) => pick(task, model)}
                defaultModel={defaults?.[task]}
                disabled={!preferences || save.isPending}
              />
            </div>
          ))}
        </CardContent>
      </Card>
    </DashboardPage>
  );
}
