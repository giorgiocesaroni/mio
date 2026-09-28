"""Jev (TypeSafe's System One model) client for the pipeline's decisions."""

import os

from typesafe_sdk import AsyncTypeSafeClient, Choice, Noul, SystemOneResponse, Usage

import src.pipeline.repository as repository

# Jev is billed per input token only ($0.042 / Mtok for jev-1.13). Only used
# when the provider doesn't report the cost (OpenRouter does).
USD_PER_INPUT_TOKEN = 0.042 / 1_000_000

Question = Choice | Noul


class _Usage(Usage):
    cost: float | None = None  # Reported by OpenRouter; the SDK's Usage drops it.


class Response(SystemOneResponse):
    id: str | None = None  # OpenRouter generation id
    usage: _Usage


def _via_openrouter() -> bool:
    return not os.getenv("TYPESAFE_API_KEY")


def _client() -> AsyncTypeSafeClient:
    """Direct TypeSafe access when configured, otherwise Jev via OpenRouter."""
    if not _via_openrouter():
        return AsyncTypeSafeClient()
    return AsyncTypeSafeClient(
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api",
        model="~typesafe/jev-latest",
    )


async def ask(
    user_id: str, session_id: str, state: dict, questions: dict[str, Question]
) -> tuple[Response, float]:
    async with _client() as client:
        response = await client.system_one(
            state,
            questions,
            response_model=Response,
            # Groups a run's Jev calls in OpenRouter's logs.
            extra_body={"session_id": session_id} if _via_openrouter() else None,
        )
    input_tokens = response.usage.input_tokens or 0
    output_tokens = response.usage.output_tokens or 0
    cost = (
        response.usage.cost
        if response.usage.cost is not None
        else input_tokens * USD_PER_INPUT_TOKEN
    )
    repository.record_invocation(
        user_id,
        # OpenRouter already reports "typesafe/…"; TypeSafe reports "jev-…".
        response.model
        if response.model.startswith("typesafe/")
        else f"typesafe/{response.model}",
        cost,
        response.usage.model_dump(),
        (input_tokens, 0, output_tokens),
    )
    return response, cost


def debug(state: dict, questions: dict[str, Question], response: Response) -> dict:
    return {
        "model": response.model,
        "usage": response.usage.model_dump(),
        "id": response.id,
        "state": state,
        "questions": {k: q.model_dump() for k, q in questions.items()},
        "answers": {k: a.model_dump() for k, a in response.answers.items()},
    }
