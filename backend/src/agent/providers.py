from anthropic import AsyncAnthropic

# Every LLM task runs on Claude Haiku 5.5: the agent (chat, questions, and
# whatever depends on the conversation), routing, extraction, resolution, and
# the entry editor. Transcription and embeddings run on Gemini.
MODEL = "claude-haiku-5-5"

# Haiku 5.5 defaults to medium effort; every task here reasons briefly.
EFFORT = "low"

# USD per million tokens, by prompt length: a prompt over 100K tokens is billed
# on the higher card. Cache reads are 0.1x the input rate, 5-minute cache
# writes 1.25x.
PRICE_CARDS = [
    (100_000, {"input": 0.10, "output": 0.50}),
    (None, {"input": 0.50, "output": 2.50}),
]
CACHE_READ_FACTOR = 0.1
CACHE_WRITE_FACTOR = 1.25

# How long one model call may take (for a stream, the wait for each chunk).
LLM_TIMEOUT_SECONDS = 120

_client: AsyncAnthropic | None = None


def get_client() -> AsyncAnthropic:
    """The Anthropic client, which reads ANTHROPIC_API_KEY."""
    global _client
    if _client is None:
        # The client's default is 10 minutes, with two retries: a model that
        # never finishes would hold a chat for half an hour.
        _client = AsyncAnthropic(timeout=LLM_TIMEOUT_SECONDS, max_retries=1)
    return _client


def cost(usage: dict) -> float:
    """The USD cost of one call, from its `usage` as the API reports it."""
    uncached = usage.get("input_tokens") or 0
    cache_read = usage.get("cache_read_input_tokens") or 0
    cache_write = usage.get("cache_creation_input_tokens") or 0
    output = usage.get("output_tokens") or 0
    prompt = uncached + cache_read + cache_write
    card = next(c for limit, c in PRICE_CARDS if limit is None or prompt <= limit)
    return (
        uncached * card["input"]
        + cache_read * card["input"] * CACHE_READ_FACTOR
        + cache_write * card["input"] * CACHE_WRITE_FACTOR
        + output * card["output"]
    ) / 1e6
