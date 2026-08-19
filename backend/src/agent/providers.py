import os
from openai import AsyncOpenAI

PROVIDERS = {
    "mimo": {
        "base_url": "https://api.xiaomimimo.com/v1",
        "api_key_env": "MIMO_API_KEY",
        # MiMo's OpenAI-compatible API accepts its own "thinking" extension.
        "supports_thinking_extension": True,
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
        "supports_thinking_extension": False,
    },
}

# Curated models, each mapped to the provider that serves it.
AVAILABLE_MODELS = [
    {
        "id": "google/gemini-3.7-flash",
        "provider": "openrouter",
        "name": "Gemini 3.7 Flash",
    },
    {
        "id": "openai/gpt-5.6-luna",
        "provider": "openrouter",
        "name": "GPT-5.6 Luna",
    },
    {
        "id": "mimo-v2.5",
        "provider": "mimo",
        "name": "MiMo-V2.5",
    },
    {
        "id": "qwen/qwen3.8-27b",
        "provider": "openrouter",
        "name": "Qwen3.8 27B",
    },
    {
        "id": "stepfun/step-3.7-flash",
        "provider": "openrouter",
        "name": "Step 3.7 Flash",
    },
    {
        "id": "minimax/minimax-m3",
        "provider": "openrouter",
        "name": "MiniMax M3",
    },
    {
        "id": "bytedance-seed/seed-2-1-turbo",
        "provider": "openrouter",
        "name": "Seed 2.1 Turbo",
    },
]

MODEL_IDS = [m["id"] for m in AVAILABLE_MODELS]

DEFAULT_MODEL_ID = os.getenv("MODEL_ID", "openai/gpt-5.6-luna")

_clients: dict[str, AsyncOpenAI] = {}


def get_provider(model_id: str) -> str:
    for model in AVAILABLE_MODELS:
        if model["id"] == model_id:
            return model["provider"]
    raise ValueError(f"Unknown model: {model_id}")


def get_client(provider: str) -> AsyncOpenAI:
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider}")
    if provider not in _clients:
        config = PROVIDERS[provider]
        _clients[provider] = AsyncOpenAI(
            base_url=config["base_url"],
            api_key=os.getenv(config["api_key_env"]),
        )
    return _clients[provider]


def get_provider_config(model_id: str) -> dict:
    provider = get_provider(model_id)
    return PROVIDERS[provider]
