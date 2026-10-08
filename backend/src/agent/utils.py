import base64
import collections

import httpx

_IMAGE_CACHE: collections.OrderedDict[str, tuple[bytes, str]] = collections.OrderedDict()
_IMAGE_CACHE_MAX_ENTRIES = 64


async def fetch_image(url: str) -> tuple[bytes, str]:
    """Fetch image bytes from a URL with an in-memory LRU cache.

    Returns (image_bytes, mime_type).
    """
    cached = _IMAGE_CACHE.get(url)
    if cached is not None:
        _IMAGE_CACHE.move_to_end(url)
        return cached
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
    data = response.content
    mime = response.headers.get("content-type", "image/jpeg")
    _IMAGE_CACHE[url] = (data, mime)
    _IMAGE_CACHE.move_to_end(url)
    while len(_IMAGE_CACHE) > _IMAGE_CACHE_MAX_ENTRIES:
        _IMAGE_CACHE.popitem(last=False)
    return data, mime


async def inline_image_url(url: str) -> str:
    """Return the image at URL as a base64 data URL, cached."""
    data, mime = await fetch_image(url)
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def summarize_large_numbers(num: int) -> str:
    if num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    if num >= 1_000:
        return f"{num / 1_000:.1f}K"
    return str(num)


def truncate_for_llm(text: str, max_length: int) -> str:
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text


def image_block(url: str) -> dict:
    """An Anthropic image content block for a data URL (base64) or a web URL."""
    if url.startswith("data:"):
        header, _, data = url.partition(",")
        media_type = header.removeprefix("data:").split(";")[0] or "image/jpeg"
        return {
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": data},
        }
    return {"type": "image", "source": {"type": "url", "url": url}}


def extract_tokens(usage: dict) -> tuple[int, int, int]:
    """Return (uncached_input_tokens, cached_input_tokens, output_tokens) from
    an Anthropic `usage`; cache writes count as uncached input."""
    uncached = (usage.get("input_tokens") or 0) + (
        usage.get("cache_creation_input_tokens") or 0
    )
    return uncached, usage.get("cache_read_input_tokens") or 0, usage.get("output_tokens") or 0
