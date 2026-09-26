export type ToolCallStep = {
  type: "tool_call";
  name: string;
  args: Record<string, unknown>;
};

export type ToolCallStartStep = {
  type: "tool_call_start";
  name: string;
};

export type ContentTokenStep = {
  type: "content_token";
  token: string;
};

export type MessageStep = {
  type: "message";
  text: string;
};

export type UserMessageStep = {
  type: "user_message";
  text: string;
  data?: string;
  mime_type?: string;
};

export type ErrorStep = {
  type: "error";
  text: string;
};

/** Quick log produced a log draft awaiting confirmation. */
export type DraftStep = {
  type: "draft";
  draft: LogDraft;
};

export type RunAgentStep = ToolCallStep | MessageStep | UserMessageStep | ContentTokenStep | ToolCallStartStep | ErrorStep | DraftStep;

export type Model = {
  id: string;
  provider: string;
  name: string;
};

export type ModelsResponse = {
  models: Model[];
  default: string;
};

export type UsageModel = {
  model_id: string;
  invocations: number;
  total_cost: number;
  uncached_input_tokens: number;
  cached_input_tokens: number;
  output_tokens: number;
  cost_per_message: number;
};

export type UsageOverview = {
  total: {
    total_invocations: number;
    total_cost: number;
    prompt_tokens: number;
    completion_tokens: number;
  };
  models: UsageModel[];
  daily: Array<{
    day: string;
    total_cost: number;
    models: Array<{ model_id: string; cost: number }>;
  }>;
};

// ── Sandbox (structured logging pipeline prototype) ──────────────────────────

export type SandboxStageName =
  | "normalize"
  | "route"
  | "extract"
  | "retrieve"
  | "resolve"
  | "draft";

export type SandboxStageStep = {
  type: "stage";
  name: SandboxStageName;
  status: "ok" | "skipped" | "error";
  summary: string;
  ms: number;
  cost: number;
  model: string | null;
  data: unknown;
};

export type SandboxDoneStep = {
  type: "done";
  outcome: "drafted" | "handoff" | "nothing" | "error";
  message: string;
  total_ms: number;
  total_cost: number;
  draft: LogDraft | null;
};

export type SandboxStep = SandboxStageStep | SandboxDoneStep | ErrorStep;

export type MealType = "breakfast" | "lunch" | "dinner" | "snack";

export type Per100g = {
  calories_kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
};

export type DraftServingSize = {
  id: string;
  label: string;
  label_plural: string;
  grams: number;
};

export type DraftAlternative = {
  key: string;
  kind: "ingredient" | "recipe" | "new";
  id: string | null;
  name: string;
  brand?: string | null;
  state?: "raw" | "cooked";
  per_100g: Per100g;
  serving_sizes?: DraftServingSize[];
  total_g?: number;
  // Only set on drafts made by the earlier Jev resolver.
  probability?: number | null;
};

export type DraftUnit = "grams" | "serving" | "recipe";

export type DraftRow = {
  id: string;
  said: string;
  alternatives: DraftAlternative[];
  target: string;
  quantity: number;
  unit: DraftUnit;
  serving_size_id: string | null;
  meal_type: MealType;
  log_for: string;
  // Derived by the backend.
  grams: number;
  macros: Per100g;
  flags: string[];
};

export type LogDraft = {
  id: string;
  created_at: string;
  day: string;
  status: "pending" | "confirmed" | "discarded";
  message: string | null;
  rows: DraftRow[];
};

/** A logged food, with the columns of `v_daily_food_logs_with_foods`. */
export type DayLog = {
  log_id: string;
  log_for: string;
  log_created_at: string;
  log_food_id: string;
  log_recipe_id: string | null;
  log_quantity_g: number | null;
  log_serving_size_id: string | null;
  log_quantity: number | null;
  log_serving_size_label: string | null;
  log_serving_size_label_plural: string | null;
  log_serving_size_grams: number | null;
  food_name: string;
  food_protein_g: number | null;
  food_carbs_g: number | null;
  food_fat_g: number | null;
  food_calories_kcal: number | null;
  recipe_name: string | null;
};

/** A day's pending drafts and logs, read together so they never overlap. */
export type DayEntries = {
  drafts: LogDraft[];
  logs: DayLog[];
};

export type ConfirmDraftResult = {
  created_ingredients: { id: string; name: string }[];
  results: { index: number; success: boolean; error?: string }[];
};
