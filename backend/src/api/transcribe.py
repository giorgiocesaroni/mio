import asyncio
from dataclasses import dataclass

import httpx
from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
)

from src.agent.providers import get_client
from src.agent.utils import get_openrouter_cost

MODEL_ID = "meta/muse-voice-transcribe-1.0"

_MAX_RETRIES = 3
_RETRY_DELAY_SECONDS = 2.0

_MIME_TO_FILENAME = {
    "audio/wav": "voice.wav",
    "audio/webm": "voice.webm",
    "audio/ogg": "voice.ogg",
    "audio/mpeg": "voice.mp3",
    "audio/mp3": "voice.mp3",
    "audio/flac": "voice.flac",
    "audio/x-m4a": "voice.m4a",
    "audio/m4a": "voice.m4a",
}

_RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}


@dataclass
class TranscriptionResult:
    text: str
    cost: float
    usage: dict


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, (APITimeoutError, APIConnectionError, httpx.TransportError)):
        return True
    if isinstance(exc, APIError):
        return exc.status_code is None or exc.status_code in _RETRYABLE_STATUS
    return False


async def transcribe_audio(audio_data: bytes, mime_type: str) -> TranscriptionResult:
    """Transcribe audio to text using Muse Voice Transcribe 1.0 (via OpenRouter).

    Args:
        audio_data: Raw audio bytes
        mime_type: MIME type of the audio (e.g., audio/wav, audio/ogg)

    Returns:
        TranscriptionResult with text and cost info
    """
    client = get_client("openrouter")
    filename = _MIME_TO_FILENAME.get(mime_type, "voice.wav")

    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = await client.audio.transcriptions.create(
                model=MODEL_ID,
                file=(filename, audio_data, mime_type),
            )
        except Exception as exc:
            if _is_retryable(exc) and attempt < _MAX_RETRIES:
                last_error = exc
                await asyncio.sleep(_RETRY_DELAY_SECONDS * (attempt + 1))
                continue
            raise
        else:
            break
    else:  # pragma: no cover - loop always breaks or raises
        raise RuntimeError(
            f"Transcription failed after {_MAX_RETRIES} retries."
        ) from last_error

    text = (response.text or "").strip()
    if not text:
        raise ValueError("No transcription returned by the transcription API.")

    raw_usage = getattr(response, "usage", None)
    if raw_usage is None:
        usage: dict = {"prompt_tokens": 0, "completion_tokens": 0}
    else:
        dump = (
            raw_usage if isinstance(raw_usage, dict) else raw_usage.model_dump()
        )
        usage = {
            "prompt_tokens": dump.get("input_tokens", dump.get("prompt_tokens", 0))
            or 0,
            "completion_tokens": dump.get(
                "output_tokens", dump.get("completion_tokens", 0)
            )
            or 0,
        }
        if isinstance(dump.get("cost"), (int, float)):
            usage["cost"] = dump["cost"]

    cost = await get_openrouter_cost(model_id=MODEL_ID, usage=usage)

    return TranscriptionResult(
        text=text,
        cost=cost,
        usage=usage,
    )
