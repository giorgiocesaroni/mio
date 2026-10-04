import {
  catalogUnavailable,
  displayName,
  fetchCatalog,
  perMillion,
  requireUser,
} from "../catalog";

export const runtime = "nodejs";

/** What OpenRouter lists for one model (`id`): its inputs, the parameters
 * its providers honour, its prices and its context length. */
export async function GET(request: Request): Promise<Response> {
  const denied = await requireUser();
  if (denied) return denied;

  const id = new URL(request.url).searchParams.get("id") ?? "";
  const catalog = await fetchCatalog();
  if (!catalog) return catalogUnavailable();
  const model = catalog.find((m) => m.id === id);
  if (!model) {
    return Response.json({ detail: `Unknown model '${id}'` }, { status: 404 });
  }
  return Response.json({
    id: model.id,
    name: displayName(model),
    input_modalities: model.architecture?.input_modalities ?? [],
    supported_parameters: model.supported_parameters ?? [],
    context_length: model.context_length ?? null,
    input_per_million: perMillion(model.pricing?.prompt),
    output_per_million: perMillion(model.pricing?.completion),
  });
}
