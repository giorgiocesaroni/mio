import os
from openai import AsyncOpenAI

from src.agent.utils import fetch_openrouter_models

PROVIDERS = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
    },
}

# Every LLM call but transcription and embeddings uses one of these, picked for
# its task, unless the request picks another (the app's settings, or the
# sandbox's); the environment variables are for trying others. Messages are
# routed by Jev (`src/pipeline/jev.py`), which has its own model.
#
# GPT-6 Luna runs every task by default, reasoning at low effort.
#
# The agent: chat, questions, and whatever depends on the conversation.
AGENT_MODEL = os.getenv("AGENT_MODEL", "openai/gpt-6-luna")
# Extracting foods from a message, then resolving them against the database.
PHOTO_EXTRACT_MODEL = os.getenv("PHOTO_EXTRACT_MODEL", "openai/gpt-6-luna")
TEXT_EXTRACT_MODEL = os.getenv("TEXT_EXTRACT_MODEL", "openai/gpt-6-luna")
RESOLVE_MODEL = os.getenv("RESOLVE_MODEL", "openai/gpt-6-luna")
# Applying a correction to an entry through small editing tools.
EDIT_MODEL = os.getenv("EDIT_MODEL", "openai/gpt-6-luna")

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
# the frontend's model catalog (frontend/app/backend/models/catalog.ts).
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


def model_for(task: str, models: dict[str, str]) -> str:
    """The model a task runs with: the one picked for the request (the app's
    settings, or the sandbox's), or the configured one."""
    return models.get(task) or TASK_DEFAULTS[task]


# Every call reasons briefly unless its model is listed here: at low effort,
# or within REASONING_MAX_TOKENS for a model that only takes a budget.
REASONING_EFFORT = "low"
NO_REASONING_MODELS = {"deepseek/deepseek-v4.1-flash"}
# Lowest first; "none" is left out, since these models should still reason.
EFFORTS = ["minimal", "low", "medium", "high", "xhigh", "max"]
# Roughly what low effort spends; Qwen 3.8 Omni Flash, budget-only, spent
# 6.5K reasoning tokens (79 s) on one extraction when asked for low effort.
REASONING_MAX_TOKENS = 1024


async def reasoning_extra_body(model_id: str) -> dict:
    """The OpenRouter `extra_body` that controls reasoning for one model.

    Turning it off is per model: a model used for both a reasoning-heavy and a
    mechanical task would otherwise have to pick one. Otherwise the model's
    OpenRouter catalog entry (`reasoning`) says what it takes: an effort
    level (low, or its lowest when it lacks low), or only a token budget.
    Anything else, or no catalog, asks for low effort.
    """
    if model_id in NO_REASONING_MODELS:
        return {"reasoning": {"enabled": False}}
    try:
        entry = (await fetch_openrouter_models()).get(model_id) or {}
    except Exception:
        entry = {}
    reasoning = entry.get("reasoning") or {}
    efforts = reasoning.get("supported_efforts") or []
    if efforts and REASONING_EFFORT not in efforts:
        lowest = next((e for e in EFFORTS if e in efforts), None)
        if lowest:
            return {"reasoning": {"effort": lowest}}
    if not efforts and reasoning.get("supports_max_tokens"):
        return {"reasoning": {"max_tokens": REASONING_MAX_TOKENS}}
    return {"reasoning": {"effort": REASONING_EFFORT}}


# How long one model call may take (for a stream, the wait for each chunk).
LLM_TIMEOUT_SECONDS = 120

_clients: dict[str, AsyncOpenAI] = {}


def get_client(provider: str = "openrouter") -> AsyncOpenAI:
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider}")
    if provider not in _clients:
        config = PROVIDERS[provider]
        _clients[provider] = AsyncOpenAI(
            base_url=config["base_url"],
            api_key=os.getenv(config["api_key_env"]),
            # The client's default is 10 minutes, with two retries: a model
            # that never finishes would hold a chat for half an hour.
            timeout=LLM_TIMEOUT_SECONDS,
            max_retries=1,
        )
    return _clients[provider]
