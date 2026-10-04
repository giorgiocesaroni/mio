import { createClient } from "@/repository/supabase/server";

// Takes over /backend/models from the catch-all proxy to the Python backend:
// searching OpenRouter's catalog needs neither the backend nor shipping all
// of it to the browser.
export const runtime = "nodejs";

const MODELS_URL = "https://openrouter.ai/api/v1/models";
const MAX_RESULTS = 50;

// What a task's model must support. Mirrors TASK_REQUIREMENTS in
// backend/src/agent/providers.py, which checks every pick when it's saved.
const TASK_REQUIREMENTS: Record<string, { input: string[]; parameters: string[] }> = {
  agent: { input: ["image"], parameters: ["tools"] },
  extract_photo: { input: ["image"], parameters: ["structured_outputs"] },
  extract_text: { input: [], parameters: ["structured_outputs"] },
  resolve: { input: [], parameters: ["structured_outputs"] },
  edit: { input: [], parameters: ["tools"] },
};

type OpenRouterModel = {
  id: string;
  name: string;
  architecture?: { input_modalities?: string[] };
  supported_parameters?: string[];
  pricing?: { prompt?: string; completion?: string };
};

function supports(model: OpenRouterModel, task: string): boolean {
  const required = TASK_REQUIREMENTS[task];
  const inputs = model.architecture?.input_modalities ?? [];
  const parameters = model.supported_parameters ?? [];
  // Batch variants answer asynchronously, so they can't serve a request.
  return (
    !model.id.endsWith(":batch") &&
    required.input.every((i) => inputs.includes(i)) &&
    required.parameters.every((p) => parameters.includes(p))
  );
}

/** USD per million tokens, from OpenRouter's per-token price; null when
 * unknown, or variable: routers such as openrouter/auto list -1, since they
 * cost whatever model they route to. */
function perMillion(price: string | undefined): number | null {
  const value = Number(price);
  return price === undefined || Number.isNaN(value) || value < 0
    ? null
    : value * 1_000_000;
}

/** The models that can do `task` and match every word of `q` in their id or
 * name, in OpenRouter's order (newest first). */
export async function GET(request: Request): Promise<Response> {
  const supabase = await createClient();
  const { data: auth } = await supabase.auth.getClaims();
  if (!auth?.claims.sub) {
    return Response.json({ detail: "Not signed in" }, { status: 403 });
  }

  const params = new URL(request.url).searchParams;
  const task = params.get("task") ?? "";
  if (!(task in TASK_REQUIREMENTS)) {
    return Response.json({ detail: `Unknown task '${task}'` }, { status: 400 });
  }
  const words = (params.get("q") ?? "").toLowerCase().split(/\s+/).filter(Boolean);

  const res = await fetch(MODELS_URL, { next: { revalidate: 3600 } });
  if (!res.ok) {
    return Response.json(
      { detail: `OpenRouter models: HTTP ${res.status}` },
      { status: 502 },
    );
  }
  const { data } = (await res.json()) as { data: OpenRouterModel[] };

  const models = data
    .filter((m) => supports(m, task))
    .filter((m) => {
      const haystack = `${m.id} ${m.name}`.toLowerCase();
      return words.every((w) => haystack.includes(w));
    })
    .slice(0, MAX_RESULTS)
    .map((m) => ({
      id: m.id,
      // "Anthropic: Claude Sonnet 5.5" → "Claude Sonnet 5.5"; the id still
      // names the provider.
      name: m.name.replace(/^[^:]+:\s*/, ""),
      input_per_million: perMillion(m.pricing?.prompt),
      output_per_million: perMillion(m.pricing?.completion),
    }));
  return Response.json(models);
}
