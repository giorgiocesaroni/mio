from typing import Optional
from google.genai import types


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


def get_google_genai_cost(
    *,
    model_id: str,
    usage_metadata: types.GenerateContentResponseUsageMetadata,
) -> float:
    model_cost_million_tokens = {
        "gemini-3-flash-preview": {
            "text_image_video_input": 0.50,
            "cached_text_image_video_input": 0.05,
            "audio_input": 1.00,
            "cached_audio_input": 0.10,
            "output": 3.00,
        },
        "gemini-3.1-flash-lite": {
            "text_image_video_input": 0.25,
            "cached_text_image_video_input": 0.025,
            "audio_input": 0.50,
            "cached_audio_input": 0.05,
            "output": 1.50,
        },
        "gemini-3.5-flash": {
            "text_image_video_input": 1.50,
            "cached_text_image_video_input": 0.15,
            "audio_input": 1.50,
            "cached_audio_input": 0.15,
            "output": 9.00,
        },
        "gemini-2.5-flash-lite": {
            "text_image_video_input": 0.10,
            "cached_text_image_video_input": 0.01,
            "audio_input": 0.30,
            "cached_audio_input": 0.03,
            "output": 0.40,
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

    # Add prompt tokens cost.
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

    # Add output (candidates + thoughts) tokens cost.
    total_cost += (
        (
            (usage_metadata.candidates_token_count or 0)
            + (usage_metadata.thoughts_token_count or 0)
        )
        * model_cost_million_tokens[model_id]["output"]
        / 1e6
    )

    return total_cost
