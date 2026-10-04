import io
import os
import subprocess
import tempfile
import uuid
from pathlib import Path

import supabase
from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener

# iPhone photos are HEIC by default; let Pillow decode them like any image.
register_heif_opener()

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

IMAGE_MAX_DIMENSION = 1600
IMAGE_JPEG_QUALITY = 82

# What every model and browser reads; any other image (HEIC, AVIF, TIFF...)
# is always converted to JPEG.
PORTABLE_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


class UnreadableImageError(ValueError):
    """An image in a format that can't be decoded, so it can't be converted."""


def _compress_image(data: bytes, mime_type: str) -> tuple[bytes, str]:
    """Re-encode an image to a compressed JPEG capped at IMAGE_MAX_DIMENSION px.

    Returns (compressed_bytes, stored_mime_type). A portable image (see
    PORTABLE_IMAGE_TYPES) is returned unchanged when it can't be processed or
    compression wouldn't help; any other image is always converted, and
    raises UnreadableImageError when it can't be decoded.
    """
    if not mime_type.startswith("image/") or mime_type == "image/gif":
        return data, mime_type
    portable = mime_type in PORTABLE_IMAGE_TYPES
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.load()
            has_orientation = img.getexif().get(274, 1) != 1
            img = ImageOps.exif_transpose(img)
            if img.mode in ("RGBA", "LA", "P", "CMYK"):
                rgba = img.convert("RGBA")
                background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
                background.alpha_composite(rgba)
                img = background.convert("RGB")
            else:
                img = img.convert("RGB")
            if max(img.size) > IMAGE_MAX_DIMENSION:
                img.thumbnail(
                    (IMAGE_MAX_DIMENSION, IMAGE_MAX_DIMENSION),
                    Image.Resampling.LANCZOS,
                )
            output = io.BytesIO()
            img.save(output, format="JPEG", quality=IMAGE_JPEG_QUALITY, optimize=True)
            compressed = output.getvalue()
            if len(compressed) < len(data) or has_orientation or not portable:
                return compressed, "image/jpeg"
    except (UnidentifiedImageError, OSError, ValueError) as e:
        if not portable:
            raise UnreadableImageError(f"Can't read this {mime_type} image.") from e
    return data, mime_type


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

    if mime_type.startswith("image/"):
        data, stored_mime = _compress_image(data, mime_type)

    if is_audio and _needs_conversion(mime_type):
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        try:
            converted_path = _convert_audio_to_ogg(tmp_path)
            data = Path(converted_path).read_bytes()
            stored_mime = "audio/ogg"
        finally:
            os.unlink(tmp_path)
            if os.path.exists(converted_path):
                os.unlink(converted_path)

    storage_path = f"{path_prefix}{MIMETYPE_TO_EXT.get(stored_mime, ext)}"
    client.storage.from_(BUCKET).upload(
        storage_path,
        data,
        {"content-type": stored_mime, "upsert": "false"},
    )
    public_url = client.storage.from_(BUCKET).get_public_url(storage_path)
    return public_url, stored_mime
