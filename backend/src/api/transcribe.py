import asyncio
import base64
from dataclasses import dataclass
import httpx
from google.genai import Client, errors, types
from src.agent.utils import get_google_genai_cost

_client: Client | None = None

MODEL_ID = "gemini-3.1-flash-lite"

_MAX_RETRIES = 3
_RETRY_DELAY_SECONDS = 2.0


def _get_client() -> Client:
    global _client
    if _client is None:
        _client = Client()
    return _client


@dataclass
class TranscriptionResult:
    text: str
    cost: float
    usage: dict


async def transcribe_audio(audio_data: bytes, mime_type: str) -> TranscriptionResult:
    """Transcribe audio to text using Gemini 3.1 Flash Lite.

    Args:
        audio_data: Raw audio bytes
        mime_type: MIME type of the audio (e.g., audio/wav, audio/ogg)

    Returns:
        TranscriptionResult with text and cost info
    """
    client = _get_client()
    b64_audio = base64.b64encode(audio_data).decode()

    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = await client.aio.models.generate_content(
                model=MODEL_ID,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_bytes(
                                data=base64.b64decode(b64_audio),
                                mime_type=mime_type,
                            ),
                            types.Part.from_text(
                                text="Transcribe this audio exactly as spoken. Output only the transcription with no additional text, labels, or formatting."
                            ),
                        ],
                    )
                ],
                config=types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(
                        thinking_level=types.ThinkingLevel.MINIMAL
                    )
                ),
            )
        except (errors.ServerError, httpx.TransportError) as exc:
            last_error = exc
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(_RETRY_DELAY_SECONDS * (attempt + 1))
                continue
        else:
            break
    else:
        raise RuntimeError(
            f"Transcription failed after {_MAX_RETRIES} retries."
        ) from last_error

    if not response.text:
        raise ValueError("No transcription returned from Gemini API.")

    usage_metadata = response.usage_metadata
    cost = get_google_genai_cost(
        model_id=MODEL_ID,
        usage_metadata=usage_metadata,
    )

    usage = {
        "prompt_tokens": getattr(usage_metadata, "prompt_token_count", 0) or 0,
        "completion_tokens": getattr(usage_metadata, "candidates_token_count", 0) or 0,
    }

    return TranscriptionResult(
        text=response.text.strip(),
        cost=cost,
        usage=usage,
    )
