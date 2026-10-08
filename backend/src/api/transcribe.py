import asyncio
import base64
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass

import httpx
from google import genai

MODEL_ID = "gemini-3.5-transcribe"

# USD per million tokens: audio in, text out.
_USD_PER_INPUT_TOKEN = 2.00 / 1e6
_USD_PER_OUTPUT_TOKEN = 12.00 / 1e6

logger = logging.getLogger(__name__)

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    """The Gemini client, which reads GOOGLE_API_KEY."""
    global _client
    if _client is None:
        _client = genai.Client()
    return _client


_MAX_RETRIES = 3
_RETRY_DELAY_SECONDS = 2.0

_RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}

_TRANSCRIBE_SAMPLE_RATE_HZ = 16000


@dataclass
class TranscriptionResult:
    text: str
    cost: float
    usage: dict


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    return status in _RETRYABLE_STATUS


def _resample_to_16k_wav(data: bytes) -> bytes:
    """Resample any audio to 16kHz mono WAV via ffmpeg: small, and a format
    the model takes."""
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
    """Transcribe audio to text using Gemini 3.5 Transcribe.

    Args:
        audio_data: Raw audio bytes
        mime_type: MIME type of the audio (e.g., audio/wav, audio/ogg)

    Returns:
        TranscriptionResult with text and cost info
    """
    try:
        audio_data = _resample_to_16k_wav(audio_data)
        mime_type = "audio/wav"
    except Exception as exc:
        logger.warning("transcribe resample failed, sending original: %s", exc)
        # Gemini lists MP4/AAC recordings as audio/m4a, without codec parameters.
        mime_type = mime_type.split(";")[0].strip()
        if mime_type in ("audio/mp4", "audio/x-m4a"):
            mime_type = "audio/m4a"
    logger.info(
        "transcribe start: model=%s mime=%s bytes=%d",
        MODEL_ID,
        mime_type,
        len(audio_data),
    )

    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            interaction = await _get_client().aio.interactions.create(
                model=MODEL_ID,
                input=[
                    {
                        "type": "audio",
                        "data": base64.b64encode(audio_data).decode(),
                        "mime_type": mime_type,
                    }
                ],
                # Voice messages aren't kept on Google's side.
                store=False,
            )
        except Exception as exc:
            logger.warning(
                "transcribe attempt %d/%d failed: %s",
                attempt + 1,
                _MAX_RETRIES + 1,
                exc,
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

    text = (interaction.output_text or "").strip()
    raw_usage = interaction.usage
    logger.info("transcribe success: chars=%d usage=%s", len(text), raw_usage)
    if not text:
        raise ValueError("No transcription returned by the transcription API.")

    # Shaped like the Anthropic usage the rest of the app records.
    usage = {
        "input_tokens": (raw_usage.total_input_tokens if raw_usage else 0) or 0,
        "output_tokens": (raw_usage.total_output_tokens if raw_usage else 0) or 0,
    }
    cost = (
        usage["input_tokens"] * _USD_PER_INPUT_TOKEN
        + usage["output_tokens"] * _USD_PER_OUTPUT_TOKEN
    )

    return TranscriptionResult(
        text=text,
        cost=cost,
        usage=usage,
    )
