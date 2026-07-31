import base64
import collections
import time
from typing import Optional

import httpx
from google.genai import types

_OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
_OPENROUTER_MODELS_CACHE_TTL_SECONDS = 300
_OPENROUTER_MODELS_CACHE: tuple[float, dict[str, dict]] = (0.0, {})

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


def extract_tokens(usage: dict) -> tuple[int, int, int]:
    """Return (uncached_input_tokens, cached_input_tokens, output_tokens)."""
    prompt_tokens = usage.get("prompt_tokens", 0) or 0
    completion_tokens = usage.get("completion_tokens", 0) or 0
    cached_tokens = 0
    details = usage.get("prompt_tokens_details")
    if isinstance(details, dict):
        cached_tokens = details.get("cached_tokens", 0) or 0
    return max(prompt_tokens - cached_tokens, 0), cached_tokens, completion_tokens


def get_mimo_cost(*, model_id: str, usage: dict) -> float:
    model_cost_million_tokens = {
        "mimo-v2.5": {
            "input": 0.112,
            "cached_input": 0.0028,
            "output": 0.224,
        },
    }
    if model_id not in model_cost_million_tokens:
        raise ValueError(f"Unknown model: {model_id}")
    pricing = model_cost_million_tokens[model_id]
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    cached_tokens = 0
    details = usage.get("prompt_tokens_details")
    if isinstance(details, dict):
        cached_tokens = details.get("cached_tokens", 0) or 0
    uncached_prompt_tokens = prompt_tokens - cached_tokens
    total_cost = (
        uncached_prompt_tokens * pricing["input"] / 1e6
        + cached_tokens * pricing["cached_input"] / 1e6
        + completion_tokens * pricing["output"] / 1e6
    )
    return total_cost


def get_google_genai_cost(
    *,
    model_id: str,
    usage_metadata: types.GenerateContentResponseUsageMetadata,
) -> float:
    model_cost_million_tokens = {
        "gemini-3.1-flash-lite": {
            "text_image_video_input": 0.25,
            "cached_text_image_video_input": 0.025,
            "audio_input": 0.50,
            "cached_audio_input": 0.05,
            "output": 1.50,
        },
    }
    if model_id not in model_cost_million_tokens:
        raise ValueError(f"Unknown model: {model_id}")
    total_cost = 0.0

    def _get_cached_tokens(
        modalities: list[str], cache_tokens_details: Optional[list]
    ) -> int:
        if cache_tokens_details is None:
            return 0
        cached_tokens = 0
        for detail in cache_tokens_details:
            if detail.modality in modalities:
                cached_tokens += detail.token_count or 0
        return cached_tokens

    if usage_metadata.prompt_tokens_details is not None:
        for detail in usage_metadata.prompt_tokens_details:
            modality = detail.modality
            token_count = detail.token_count or 0
            match modality:
                case "AUDIO":
                    cached = _get_cached_tokens(
                        ["AUDIO"], usage_metadata.cache_tokens_details
                    )
                    total_cost += (
                        (token_count - cached)
                        * model_cost_million_tokens[model_id]["audio_input"]
                        / 1e6
                    )
                    total_cost += (
                        cached
                        * model_cost_million_tokens[model_id]["cached_audio_input"]
                        / 1e6
                    )
                case "TEXT" | "IMAGE" | "VIDEO":
                    cached = _get_cached_tokens(
                        [modality], usage_metadata.cache_tokens_details
                    )
                    total_cost += (
                        (token_count - cached)
                        * model_cost_million_tokens[model_id]["text_image_video_input"]
                        / 1e6
                    )
                    total_cost += (
                        cached
                        * model_cost_million_tokens[model_id][
                            "cached_text_image_video_input"
                        ]
                        / 1e6
                    )

    total_cost += (
        (
            (usage_metadata.candidates_token_count or 0)
            + (usage_metadata.thoughts_token_count or 0)
        )
        * model_cost_million_tokens[model_id]["output"]
        / 1e6
    )

    return total_cost


async def _fetch_openrouter_models() -> dict[str, dict]:
    """Fetch OpenRouter model pricing, cached briefly. Returns {model_id: pricing}."""
    global _OPENROUTER_MODELS_CACHE
    cached_at, cached = _OPENROUTER_MODELS_CACHE
    if cached and time.time() - cached_at < _OPENROUTER_MODELS_CACHE_TTL_SECONDS:
        return cached
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(_OPENROUTER_MODELS_URL)
        response.raise_for_status()
    data = response.json().get("data", [])
    models = {m["id"]: m for m in data if "pricing" in m}
    _OPENROUTER_MODELS_CACHE = (time.time(), models)
    return models


def _apply_overrides(pricing: dict, prompt_tokens: int) -> dict:
    """Apply OpenRouter volume-discount overrides whose threshold is met."""
    best_override = None
    for override in pricing.get("overrides", []):
        min_prompt_tokens = override.get("min_prompt_tokens", 0)
        if prompt_tokens >= min_prompt_tokens and (
            best_override is None
            or min_prompt_tokens > best_override.get("min_prompt_tokens", 0)
        ):
            best_override = override
    if best_override is None:
        return pricing
    merged = dict(pricing)
    merged.update({k: v for k, v in best_override.items() if k != "min_prompt_tokens"})
    return merged


async def get_openrouter_cost(*, model_id: str, usage: dict) -> float:
    """Compute the USD cost of an OpenRouter invocation.

    Prefers the cost returned directly by OpenRouter in the usage object (most
    accurate), falling back to the model's published pricing fetched from the
    /models endpoint.
    """
    reported_cost = usage.get("cost")
    if isinstance(reported_cost, (int, float)) and reported_cost > 0:
        return float(reported_cost)

    prompt_tokens = usage.get("prompt_tokens", 0) or 0
    completion_tokens = usage.get("completion_tokens", 0) or 0
    cached_tokens = 0
    details = usage.get("prompt_tokens_details")
    if isinstance(details, dict):
        cached_tokens = details.get("cached_tokens", 0) or 0

    models = await _fetch_openrouter_models()
    model = models.get(model_id)
    if model is None:
        return 0.0
    pricing = _apply_overrides(model["pricing"], prompt_tokens)

    def _price(key: str) -> float:
        return float(pricing.get(key, 0) or 0)

    uncached_prompt_tokens = max(prompt_tokens - cached_tokens, 0)
    cached_price = _price("input_cache_read") or _price("prompt")
    total_cost = (
        uncached_prompt_tokens * _price("prompt")
        + cached_tokens * cached_price
        + completion_tokens * _price("completion")
        + _price("request")
    )
    return total_cost
