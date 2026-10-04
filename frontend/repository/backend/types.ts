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

/** What the assistant is doing right now, shown while it works. */
export type StatusStep = {
  type: "status";
  text: string;
};

export type RunAgentStep = ToolCallStep | MessageStep | UserMessageStep | ContentTokenStep | ToolCallStartStep | ErrorStep | DraftStep | StatusStep;

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
  logs: UsageLogCost[];
};

/** Drafts created from chat, by the path that created them. */
export type UsageLogCost = {
  via: "pipeline" | "agent";
  logs: number;
  total_cost: number;
  cost_per_log: number;
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
  // Degradations the stage survived, e.g. a food the resolver skipped.
  warnings: string[];
};

export type SandboxDoneStep = {
  type: "done";
  outcome: "drafted" | "handoff" | "nothing" | "error";
  message: string;
  total_ms: number;
  total_cost: number;
  draft: LogDraft | null;
  warnings: string[];
};

export type SandboxStep = SandboxStageStep | SandboxDoneStep | ErrorStep;

// The tasks a model can be picked for.
export type ModelTask =
  | "agent"
  | "extract_photo"
  | "extract_text"
  | "resolve"
  | "edit";

// One OpenRouter model a task can run with; prices in USD per million tokens.
export type ModelOption = {
  id: string;
  name: string;
  input_per_million: number | null;
  output_per_million: number | null;
};

// What OpenRouter lists for one model: the parameters it doesn't list are
// dropped from requests without an error.
export type ModelInfo = ModelOption & {
  input_modalities: string[];
  supported_parameters: string[];
  context_length: number | null;
};

// The model of each task, as {task: model id}.
export type ModelChoices = Partial<Record<ModelTask, string>>;

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
  // The draft-local group this row belongs to, when it is a component of a
  // dish logged as several foods; null for a standalone food.
  dish_id?: string | null;
  // The dish this row is a component of, when it was logged as several foods.
  dish?: string | null;
  // A usual component nobody mentioned (cooking oil, dressing...).
  assumed?: boolean;
  alternatives: DraftAlternative[];
  target: string;
  quantity: number;
  unit: DraftUnit;
  serving_size_id: string | null;
  meal_type: MealType;
  log_for: string;
  // Derived by the backend when it writes the rows.
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
  // What created it; sandbox runs are debug drafts, kept out of the day's list.
  via: "pipeline" | "agent" | "sandbox" | null;
  rows: DraftRow[];
};

/** A logged food, with the columns of `v_daily_food_logs_with_foods`. */
export type DayLog = {
  log_id: string;
  log_for: string;
  log_created_at: string;
  log_food_id: string;
  log_recipe_id: string | null;
  // Groups the component rows of one dish, when it was logged as several foods.
  log_dish_id: string | null;
  log_dish_name: string | null;
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
