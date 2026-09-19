export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const FORWARDED_REQUEST_HEADERS = ["accept", "authorization", "content-type"];

async function proxy(
  request: Request,
  { params }: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const apiBaseUrl = process.env.API_BASE_URL?.replace(/\/$/, "");
  if (!apiBaseUrl) {
    return new Response("API_BASE_URL is not configured", { status: 500 });
  }

  const { path } = await params;
  const incomingUrl = new URL(request.url);
  const targetUrl = `${apiBaseUrl}/${path.join("/")}${incomingUrl.search}`;
  const headers = new Headers();

  for (const name of FORWARDED_REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }

  const init: RequestInit & { duplex?: "half" } = {
    method: request.method,
    headers,
    cache: "no-store",
  };

  if (request.method !== "GET" && request.method !== "HEAD" && request.body) {
    init.body = request.body;
    init.duplex = "half";
  }

  const upstream = await fetch(targetUrl, init);
  const responseHeaders = new Headers(upstream.headers);

  // Do not let the proxy or an intermediary buffer an SSE response.
  responseHeaders.delete("content-length");
  responseHeaders.delete("content-encoding");
  if (responseHeaders.get("content-type")?.startsWith("text/event-stream")) {
    responseHeaders.set("cache-control", "no-cache, no-transform");
    responseHeaders.set("x-accel-buffering", "no");
  }

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}

export const GET = proxy;
export const HEAD = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
