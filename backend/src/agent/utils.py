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
