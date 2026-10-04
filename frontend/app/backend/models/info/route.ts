import { catalogUnavailable, fetchCatalog, requireUser } from "../catalog";

export const runtime = "nodejs";

/** OpenRouter's catalog entry for one model (`id`), exactly as it lists it. */
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
  return Response.json(model);
}
