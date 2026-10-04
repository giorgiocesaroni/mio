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

# The tasks a user can pick a model for, and the configured model of each.
TASK_DEFAULTS = {
    "agent": AGENT_MODEL,
    "extract_photo": PHOTO_EXTRACT_MODEL,
    "extract_text": TEXT_EXTRACT_MODEL,
    "resolve": RESOLVE_MODEL,
    "edit": EDIT_MODEL,
}

# What a task's model must support, as OpenRouter's /models lists it: input
# modalities, and request parameters (tools for tool calls, structured_outputs
# for strict JSON schemas). The agent reads photos sent in chat. Mirrored by
# the frontend's model search (frontend/app/backend/models/route.ts).
TASK_REQUIREMENTS = {
    "agent": {"input": ["image"], "parameters": ["tools"]},
    "extract_photo": {"input": ["image"], "parameters": ["structured_outputs"]},
    "extract_text": {"input": [], "parameters": ["structured_outputs"]},
    "resolve": {"input": [], "parameters": ["structured_outputs"]},
    "edit": {"input": [], "parameters": ["tools"]},
}


def supports(model: dict, task: str) -> bool:
    """Whether an OpenRouter /models entry can run `task`. Batch variants
    answer asynchronously, so they can't serve a request."""
    required = TASK_REQUIREMENTS[task]
    inputs = (model.get("architecture") or {}).get("input_modalities") or []
    parameters = model.get("supported_parameters") or []
    return (
        not model["id"].endswith(":batch")
        and all(i in inputs for i in required["input"])
        and all(p in parameters for p in required["parameters"])
    )


def model_for(task: str, preferences: dict) -> str:
    """The model a task runs with: the user's pick, or the configured one."""
    return preferences.get(task) or TASK_DEFAULTS[task]


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
