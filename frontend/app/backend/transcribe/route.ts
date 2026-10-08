import { GoogleGenAI } from "@google/genai";
import { createClient } from "@/repository/supabase/server";

// Takes over /backend/transcribe from the catch-all proxy to the Python
// backend, so a voice memo doesn't wait for Cloud Run to start.
export const runtime = "nodejs";

const MODEL_ID = "gemini-3.5-transcribe";
// USD per million tokens: audio in, text out.
const USD_PER_INPUT_TOKEN = 2.0 / 1e6;
const USD_PER_OUTPUT_TOKEN = 12.0 / 1e6;
const MAX_RETRIES = 3;
const RETRY_DELAY_MS = 2000;
const RETRYABLE_STATUS = new Set([408, 425, 429, 500, 502, 503, 504]);

type Transcription = {
  text?: string;
  usage: { input_tokens: number; output_tokens: number };
};

const ai = new GoogleGenAI({ apiKey: process.env.GOOGLE_API_KEY });

/** The MIME type Gemini takes for a recording: codec parameters dropped, and
 * Safari's MP4/AAC under the name Gemini lists it by. */
function audioMimeType(type: string): string {
  const base = type.split(";")[0].trim();
  return base === "audio/mp4" || base === "audio/x-m4a" ? "audio/m4a" : base;
}

/** Transcribes with Gemini 3.5 Transcribe, retrying transient errors.
 * Browsers' native formats (WebM/Opus, MP4/AAC) are sent as recorded. */
async function transcribe(file: File): Promise<Transcription> {
  const data = Buffer.from(await file.arrayBuffer()).toString("base64");
  for (let attempt = 0; ; attempt++) {
    try {
      const interaction = await ai.interactions.create({
        model: MODEL_ID,
        input: [
          { type: "audio", data, mime_type: audioMimeType(file.type) },
        ],
        // Voice messages aren't kept on Google's side.
        store: false,
      });
      return {
        text: interaction.output_text,
        usage: {
          input_tokens: interaction.usage?.total_input_tokens ?? 0,
          output_tokens: interaction.usage?.total_output_tokens ?? 0,
        },
      };
    } catch (error) {
      const status = (error as { status?: number }).status;
      const retryable = status === undefined || RETRYABLE_STATUS.has(status);
      if (!retryable || attempt >= MAX_RETRIES) throw error;
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

  const { error } = await supabase.from("llm_invocations").insert({
    user_id: userId,
    model_id: MODEL_ID,
    total_cost:
      result.usage.input_tokens * USD_PER_INPUT_TOKEN +
      result.usage.output_tokens * USD_PER_OUTPUT_TOKEN,
    raw_usage_metadata: result.usage,
    uncached_input_tokens: result.usage.input_tokens,
    cached_input_tokens: 0,
    output_tokens: result.usage.output_tokens,
  });
  if (error) console.error("Could not record the transcription cost", error);

  return Response.json({ text });
}
