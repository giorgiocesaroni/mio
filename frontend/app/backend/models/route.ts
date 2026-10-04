import {
  TASK_REQUIREMENTS,
  catalogUnavailable,
  displayName,
  fetchCatalog,
  perMillion,
  requireUser,
  supports,
} from "./catalog";

// Takes over /backend/models from the catch-all proxy to the Python backend:
// searching OpenRouter's catalog needs neither the backend nor shipping all
// of it to the browser.
export const runtime = "nodejs";

const MAX_RESULTS = 50;

/** The models that can do `task` and match every word of `q` in their id or
 * name, in OpenRouter's order (newest first). */
export async function GET(request: Request): Promise<Response> {
  const denied = await requireUser();
  if (denied) return denied;

  const params = new URL(request.url).searchParams;
  const task = params.get("task") ?? "";
  if (!(task in TASK_REQUIREMENTS)) {
    return Response.json({ detail: `Unknown task '${task}'` }, { status: 400 });
  }
  const words = (params.get("q") ?? "").toLowerCase().split(/\s+/).filter(Boolean);

  const catalog = await fetchCatalog();
  if (!catalog) return catalogUnavailable();

  const models = catalog
    .filter((m) => supports(m, task))
    .filter((m) => {
      const haystack = `${m.id} ${m.name}`.toLowerCase();
      return words.every((w) => haystack.includes(w));
    })
    .slice(0, MAX_RESULTS)
    .map((m) => ({
      id: m.id,
      name: displayName(m),
      input_per_million: perMillion(m.pricing?.prompt),
      output_per_million: perMillion(m.pricing?.completion),
    }));
  return Response.json(models);
}
