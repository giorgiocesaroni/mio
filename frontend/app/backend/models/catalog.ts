import { createClient } from "@/repository/supabase/server";

// OpenRouter's public model catalog, shared by the model routes: each model
// lists its input modalities, the request parameters its providers honour
// (`supported_parameters`), its prices and its context length. Parameters a
// model doesn't list are dropped by OpenRouter without an error.

const MODELS_URL = "https://openrouter.ai/api/v1/models";

// What a task's model must support. Mirrors TASK_REQUIREMENTS in
// backend/src/agent/providers.py, which checks every pick when it's used.
export const TASK_REQUIREMENTS: Record<string, { input: string[]; parameters: string[] }> = {
  agent: { input: ["image"], parameters: ["tools"] },
  extract_photo: { input: ["image"], parameters: ["structured_outputs"] },
  extract_text: { input: [], parameters: ["structured_outputs"] },
  resolve: { input: [], parameters: ["structured_outputs"] },
  edit: { input: [], parameters: ["tools"] },
};

export type OpenRouterModel = {
  id: string;
  name: string;
  context_length?: number;
  architecture?: { input_modalities?: string[] };
  supported_parameters?: string[];
  pricing?: { prompt?: string; completion?: string };
};

/** The catalog, cached for an hour; null when OpenRouter can't be reached. */
export async function fetchCatalog(): Promise<OpenRouterModel[] | null> {
  const res = await fetch(MODELS_URL, { next: { revalidate: 3600 } });
  if (!res.ok) return null;
  return ((await res.json()) as { data: OpenRouterModel[] }).data;
}

/** Whether a model can run `task`. Batch variants answer asynchronously, so
 * they can't serve a request. */
export function supports(model: OpenRouterModel, task: string): boolean {
  const required = TASK_REQUIREMENTS[task];
  const inputs = model.architecture?.input_modalities ?? [];
  const parameters = model.supported_parameters ?? [];
  return (
    !model.id.endsWith(":batch") &&
    required.input.every((i) => inputs.includes(i)) &&
    required.parameters.every((p) => parameters.includes(p))
  );
}

/** USD per million tokens, from OpenRouter's per-token price; null when
 * unknown, or variable: routers such as openrouter/auto list -1, since they
 * cost whatever model they route to. */
export function perMillion(price: string | undefined): number | null {
  const value = Number(price);
  return price === undefined || Number.isNaN(value) || value < 0
    ? null
    : value * 1_000_000;
}

/** "Anthropic: Claude Sonnet 5.5" → "Claude Sonnet 5.5"; the id still names
 * the provider. */
export function displayName(model: OpenRouterModel): string {
  return model.name.replace(/^[^:]+:\s*/, "");
}

/** A JSON error response when the request isn't from a signed-in user. */
export async function requireUser(): Promise<Response | null> {
  const supabase = await createClient();
  const { data: auth } = await supabase.auth.getClaims();
  return auth?.claims.sub
    ? null
    : Response.json({ detail: "Not signed in" }, { status: 403 });
}

export function catalogUnavailable(): Response {
  return Response.json(
    { detail: "OpenRouter's model list is unavailable" },
    { status: 502 },
  );
}
