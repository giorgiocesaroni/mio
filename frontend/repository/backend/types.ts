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
  | "plan"
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
  probability: number | null;
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

/** The editable subset of a row, as sent back to the backend. */
export type DraftRowEdit = Pick<
  DraftRow,
  "id" | "target" | "quantity" | "unit" | "serving_size_id" | "meal_type"
>;

export type LogDraft = {
  id: string;
  created_at: string;
  day: string;
  status: "pending" | "confirmed" | "discarded";
  message: string | null;
  rows: DraftRow[];
};

export type ConfirmDraftResult = {
  created_ingredients: { id: string; name: string }[];
  results: { index: number; success: boolean; error?: string }[];
};
