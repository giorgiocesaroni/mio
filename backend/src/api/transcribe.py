import asyncio
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass

import httpx
from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
)

from src.agent.providers import get_client
from src.agent.utils import get_openrouter_cost

MODEL_ID = "openai/gpt-transcribe"

logger = logging.getLogger(__name__)

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

_TRANSCRIBE_SAMPLE_RATE_HZ = 16000


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


def _resample_to_16k_wav(data: bytes) -> bytes:
    """Resample any audio to 16kHz mono WAV (Meta requirement) via ffmpeg."""
    with tempfile.NamedTemporaryFile(suffix=".src", delete=False) as tmp:
        tmp.write(data)
        src_path = tmp.name
    out_path = src_path + ".16k.wav"
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i", src_path,
                "-ar", str(_TRANSCRIBE_SAMPLE_RATE_HZ),
                "-ac", "1",
                "-c:a", "pcm_s16le",
                out_path,
            ],
            check=True,
            capture_output=True,
        )
        with open(out_path, "rb") as f:
            return f.read()
    finally:
        for path in (src_path, out_path):
            if os.path.exists(path):
                os.unlink(path)


async def transcribe_audio(audio_data: bytes, mime_type: str) -> TranscriptionResult:
    """Transcribe audio to text using GPT Transcribe (via OpenRouter).

    Args:
        audio_data: Raw audio bytes
        mime_type: MIME type of the audio (e.g., audio/wav, audio/ogg)

    Returns:
        TranscriptionResult with text and cost info
    """
    client = get_client("openrouter")
    try:
        audio_data = _resample_to_16k_wav(audio_data)
        mime_type = "audio/wav"
    except Exception as exc:
        logger.warning("transcribe resample failed, sending original: %s", exc)
    filename = _MIME_TO_FILENAME.get(mime_type, "voice.wav")
    logger.info(
        "transcribe start: model=%s file=%s mime=%s bytes=%d",
        MODEL_ID,
        filename,
        mime_type,
        len(audio_data),
    )

    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = await client.audio.transcriptions.create(
                model=MODEL_ID,
                file=(filename, audio_data, mime_type),
            )
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            body = getattr(exc, "body", None)
            logger.warning(
                "transcribe attempt %d/%d failed: %s status=%s body=%s",
                attempt + 1,
                _MAX_RETRIES + 1,
                exc,
                status,
                body,
            )
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
    logger.info(
        "transcribe success: chars=%d usage=%s",
        len(text),
        getattr(response, "usage", None),
    )
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
