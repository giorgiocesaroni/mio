import { renderAppIcon } from "@/app/lib/app-icon";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ size: string }> },
) {
  const { size } = await params;
  const parsed = Number.parseInt(size, 10);

  if (!Number.isFinite(parsed) || parsed < 16 || parsed > 1024) {
    return new Response("Unsupported icon size", { status: 400 });
  }

  return renderAppIcon(parsed, { maskable: new URL(_request.url).searchParams.has("maskable") });
}
