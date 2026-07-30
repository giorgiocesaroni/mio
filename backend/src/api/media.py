import os
import subprocess
import tempfile
import uuid
from pathlib import Path

import supabase

_supabase_client: supabase.Client | None = None

BUCKET = "media"

MIMETYPE_TO_EXT = {
    "audio/wav": ".wav",
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/flac": ".flac",
    "audio/x-m4a": ".m4a",
    "audio/m4a": ".m4a",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

# MiMo accepts these audio formats natively
MIMO_AUDIO_TYPES = {"audio/mpeg", "audio/wav", "audio/flac", "audio/x-m4a", "audio/m4a", "audio/ogg"}


def _get_client() -> supabase.Client:
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = supabase.create_client(
            os.getenv("SUPABASE_URL", ""),
            os.getenv("SUPABASE_KEY", ""),
        )
    return _supabase_client


def _convert_audio_to_ogg(input_path: str) -> str:
    """Convert audio file to OGG Opus using ffmpeg. Returns path to converted file."""
    output_path = input_path.rsplit(".", 1)[0] + ".ogg"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i", input_path,
            "-c:a", "libopus",
            "-b:a", "64k",
            "-ar", "48000",
            output_path,
        ],
        check=True,
        capture_output=True,
    )
    return output_path


def _needs_conversion(mime_type: str) -> bool:
    """Check if this audio type needs conversion to be accepted by MiMo."""
    return mime_type not in MIMO_AUDIO_TYPES


def upload_media(user_id: str, data: bytes, mime_type: str) -> tuple[str, str]:
    """Upload media to Supabase Storage, converting audio if needed.

    Returns (public_url, stored_mime_type).
    """
    client = _get_client()
    ext = MIMETYPE_TO_EXT.get(mime_type, ".bin")
    path_prefix = f"{user_id}/{uuid.uuid4().hex}"

    is_audio = mime_type.startswith("audio/")
    stored_mime = mime_type

    if is_audio and _needs_conversion(mime_type):
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        try:
            converted_path = _convert_audio_to_ogg(tmp_path)
            data = Path(converted_path).read_bytes()
            stored_mime = "audio/ogg"
            ext = ".ogg"
        finally:
            os.unlink(tmp_path)
            if os.path.exists(converted_path):
                os.unlink(converted_path)

    storage_path = f"{path_prefix}{ext}"
    client.storage.from_(BUCKET).upload(
        storage_path,
        data,
        {"content-type": stored_mime, "upsert": "false"},
    )
    public_url = client.storage.from_(BUCKET).get_public_url(storage_path)
    return public_url, stored_mime
