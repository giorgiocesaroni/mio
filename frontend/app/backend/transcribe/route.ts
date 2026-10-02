import { createClient } from "@/repository/supabase/server";

// Takes over /backend/transcribe from the catch-all proxy to the Python
// backend, so a voice memo doesn't wait for Cloud Run to start.
export const runtime = "nodejs";

const MODEL_ID = "openai/gpt-transcribe";
const MAX_RETRIES = 3;
const RETRY_DELAY_MS = 2000;
const RETRYABLE_STATUS = new Set([408, 425, 429, 500, 502, 503, 504]);

type Transcription = { text?: string; usage?: { cost?: number } };

/** Transcribes with GPT Transcribe via OpenRouter, retrying transient errors.
 * Browsers' native formats (WebM/Opus, MP4/AAC) are sent as recorded. */
async function transcribe(file: File): Promise<Transcription> {
  for (let attempt = 0; ; attempt++) {
    const body = new FormData();
    body.append("model", MODEL_ID);
    body.append("file", file);
    let res: Response | null = null;
    try {
      res = await fetch("https://openrouter.ai/api/v1/audio/transcriptions", {
        method: "POST",
        headers: { Authorization: `Bearer ${process.env.OPENROUTER_API_KEY}` },
        body,
      });
    } catch (error) {
      if (attempt >= MAX_RETRIES) throw error;
    }
    if (res?.ok) return res.json();
    if (res && (!RETRYABLE_STATUS.has(res.status) || attempt >= MAX_RETRIES)) {
      throw new Error(`HTTP ${res.status} ${await res.text().catch(() => "")}`);
    }
    await new Promise((r) => setTimeout(r, RETRY_DELAY_MS * (attempt + 1)));
  }
}

export async function POST(request: Request): Promise<Response> {
  const supabase = await createClient();
  const { data: auth } = await supabase.auth.getClaims();
  const userId = auth?.claims.sub;
  if (!userId) return Response.json({ detail: "Not signed in" }, { status: 403 });

  const file = (await request.formData()).get("file");
  if (!(file instanceof File) || file.size === 0) {
    return Response.json({ detail: "Empty file" }, { status: 400 });
  }
  if (!file.type.startsWith("audio/")) {
    return Response.json({ detail: "Audio file required" }, { status: 400 });
  }

  let result: Transcription;
  try {
    result = await transcribe(file);
  } catch (error) {
    console.error("Transcription failed", error);
    return Response.json(
      { detail: `Transcription failed: ${(error as Error).message}` },
      { status: 500 },
    );
  }
  const text = result.text?.trim();
  if (!text) {
    return Response.json(
      { detail: "Transcription failed: no text returned" },
      { status: 500 },
    );
  }

  // OpenRouter reports the cost; transcription has no token counts.
  const { error } = await supabase.from("llm_invocations").insert({
    user_id: userId,
    model_id: MODEL_ID,
    total_cost: result.usage?.cost ?? 0,
    raw_usage_metadata: result.usage ?? {},
    uncached_input_tokens: 0,
    cached_input_tokens: 0,
    output_tokens: 0,
  });
  if (error) console.error("Could not record the transcription cost", error);

  return Response.json({ text });
}
