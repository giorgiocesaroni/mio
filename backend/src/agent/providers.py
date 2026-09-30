import os
from openai import AsyncOpenAI

PROVIDERS = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
    },
}

# Every LLM call but transcription and embeddings uses one of these, picked for
# its task; the environment variables are for trying others. Messages are
# routed by Jev (`src/pipeline/jev.py`), which has its own model.
#
# The agent: chat, questions, and whatever depends on the conversation.
AGENT_MODEL = os.getenv("AGENT_MODEL", "openai/gpt-6-luna")
# Extracting foods from a message and resolving them against the database:
# DeepSeek without reasoning, since both are mechanical and its reasoning only
# adds latency and tokens.
PHOTO_EXTRACT_MODEL = os.getenv("PHOTO_EXTRACT_MODEL", "deepseek/deepseek-v4.1-flash")
TEXT_EXTRACT_MODEL = os.getenv("TEXT_EXTRACT_MODEL", "deepseek/deepseek-v4.1-flash")
RESOLVE_MODEL = os.getenv("RESOLVE_MODEL", "deepseek/deepseek-v4.1-flash")
# Applying a correction to an entry through small editing tools.
EDIT_MODEL = os.getenv("EDIT_MODEL", "deepseek/deepseek-v4.1-flash")

# Every call reasons at low effort unless its model is listed here.
REASONING_EFFORT = "low"
NO_REASONING_MODELS = {"deepseek/deepseek-v4.1-flash"}


def reasoning_extra_body(model_id: str) -> dict:
    """The OpenRouter `extra_body` that controls reasoning for one model.

    Turning it off is per model: a model used for both a reasoning-heavy and a
    mechanical task would otherwise have to pick one. Set `effort` instead when
    the model should reason, so its provider can spend the right amount.
    """
    if model_id in NO_REASONING_MODELS:
        return {"reasoning": {"enabled": False}}
    return {"reasoning": {"effort": REASONING_EFFORT}}


# Display names, including models used in the past, for the usage page.
MODEL_NAMES = {
    "google/gemini-3.8-flash": "Gemini 3.8 Flash",
    "typesafe/jev-1.13-20260917": "Jev 1.13",
    "openai/gpt-6-luna": "GPT-6 Luna",
    "deepseek/deepseek-v4.1-flash": "DeepSeek V4.1 Flash",
    "z-ai/glm-5.3-flash": "GLM 5.3 Flash",
    "xiaomi/mimo-v2.6-pro": "MiMo-V2.6-Pro",
    "xiaomi/mimo-v2.6-flash": "MiMo-V2.6-Flash",
}

_clients: dict[str, AsyncOpenAI] = {}


def get_client(provider: str = "openrouter") -> AsyncOpenAI:
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider}")
    if provider not in _clients:
        config = PROVIDERS[provider]
        _clients[provider] = AsyncOpenAI(
            base_url=config["base_url"],
            api_key=os.getenv(config["api_key_env"]),
        )
    return _clients[provider]
