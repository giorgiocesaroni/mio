import os
from openai import AsyncOpenAI

PROVIDERS = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
    },
}

# Every LLM call but transcription and embeddings uses one of these, picked for
# its task; the environment variables are for trying others.
#
# The agent chats, reads photos, and extracts the foods it logs.
AGENT_MODEL = os.getenv("AGENT_MODEL", "deepseek/deepseek-v4.1-flash")
# Extraction outside chat: the sandbox and corrections to drafts and logs.
EXTRACT_MODEL = os.getenv("EXTRACT_MODEL", "deepseek/deepseek-v4.1-flash")
# Matching extracted foods to the user's database: text only, structured output.
RESOLVE_MODEL = os.getenv("RESOLVE_MODEL", "openai/gpt-6-luna")

REASONING_EFFORT = "low"

# Display names, including models used in the past, for the usage page.
MODEL_NAMES = {
    "google/gemini-3.8-flash": "Gemini 3.8 Flash",
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
