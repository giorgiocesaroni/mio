"""Structured food-logging pipeline.

A fixed sequence of steps, where each model only makes the decision it is
good at:

    normalize → route (Jev) → extract (LLM) → retrieve (code)
              → resolve (LLM) → draft (persisted)

Every chat message starts here. Nothing is logged directly: the result is a
draft the user reviews, edits, and confirms. Whatever the router doesn't
recognize as a new, self-contained food log is handed back to the caller,
which falls back to the agent; the agent's `log_food` tool runs the pipeline
again without the router.
"""

import asyncio
import base64
import datetime
import json
import time
import uuid
from typing import AsyncGenerator, TypeVar
from uuid import UUID
from zoneinfo import ZoneInfo

from typesafe_sdk import Choice, Noul

import src.agent.embeddings as embeddings
import src.agent.models as agent_models
import src.agent.providers as providers
import src.agent.repository as agent_repository
import src.agent.tools as tools
import src.pipeline.jev as jev
import src.pipeline.logic as logic
import src.pipeline.repository as repository
from src.agent.utils import extract_tokens, get_openrouter_cost, inline_image_url
from pydantic import BaseModel

from src.pipeline.models import (
    DoneStep,
    DraftError,
    DraftVia,
    ExtractedItem,
    Extraction,
    Resolution,
    PipelineInput,
    PipelineStep,
    StageName,
    StageStep,
)

# Reasoning counts toward this, and some models reason at length whatever the
# effort, so it's generous; only the tokens used are paid for.
LLM_MAX_COMPLETION_TOKENS = 16384

EXTRACT_PROMPT = """You turn a food log message (text and/or photos) into structured items for a nutrition tracker. The user's local time is {now}.

- One item per distinct food or drink. Split a meal into its components only when the user lists them; keep a dish they name (e.g. "lasagna", "espresso zuccherato") as one item, since it may be one of their saved recipes.
- Keep the user's quantities. When they give none, assume a typical single portion.
- Fill every field following its description. `per_100g` must be realistic for the food in the given `state`.
- If the message does not describe anything eaten or drunk, return an empty `items` list."""

RESOLVE_PROMPT = """You decide how foods a user ate are logged in their nutrition tracker. The user's local time is {now}; the log is for {day}. Their message was: {message}

For each food in `foods` (by index), return exactly one row:
- `target`: the key of the candidate that is the same food, or "new" when none is. The user's own entries come first: a matching brand is strong evidence, and raw vs cooked entries of the same food are still the same food. A saved recipe matches when the user names that dish.
- `unit` and `quantity`: when the user stated a weight, "grams" with exactly that weight. Otherwise "serving" with the target's `serving` key when they counted units the entry defines (slices, pieces, cutlets...); "recipe" with a fraction when they ate part of a saved recipe (half = 0.5, a portion of a multi-portion dish is a fraction); otherwise "grams" with the eaten weight, starting from `estimated_grams`.
- `weight_state`: whether the logged amount is raw or cooked weight. If the target is raw but the user ate it cooked (or the reverse), convert the grams to the target's state and set `weight_state` to it.
- `meal_type` and `time` (HH:MM): as stated in the message; otherwise infer them sensibly from the local time.
- `confidence`: "high" when the match and amount are clear; "medium" when you had to assume something; "low" when unsure.
- `note`: when confidence isn't high, one short sentence for the user, in the language of their message, saying what you assumed (e.g. which variant, or an estimated weight). Otherwise null."""


_Output = TypeVar("_Output", bound=BaseModel)


def _ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


# ── Stages ────────────────────────────────────────────────────────────────────


async def _normalize(message: agent_models.MessageType) -> tuple[str, list[str], list[str]]:
    """Return (text, model-ready image URLs, displayable image URLs)."""
    text = "\n".join(p.text for p in message.parts if p.text).strip()
    images: list[str] = []
    displayable: list[str] = []
    for part in message.parts:
        mime = part.mime_type or ""
        if part.url and not mime.startswith("audio/"):
            images.append(
                part.url if part.url.startswith("data:") else await inline_image_url(part.url)
            )
            displayable.append(part.url)
        elif part.data and mime.startswith("image/"):
            images.append(f"data:{mime};base64,{base64.b64encode(part.data).decode()}")
    return text, images, displayable


async def _route(
    user_id: str, input: PipelineInput, text: str, image_count: int
) -> tuple[dict, float]:
    state = logic.route_state(text, image_count, input.last_reply, input.pending_draft)
    questions: dict[str, jev.Question] = {
        "depends_on_conversation": Noul(
            instructions=(
                "Does `message` (with its `attached_photos`) only make sense given "
                "the conversation: answering something `assistant_last_reply` "
                "asked, correcting `pending_draft`, or identifying foods by "
                "pointing to earlier meals or logs (e.g. 'same as yesterday', 'my "
                "usual breakfast') instead of naming them? A message naming new "
                "foods, or a photo when nothing was asked for, stands on its own "
                "even mid-conversation."
            ),
        ),
    }
    # A photo without text has no intent to read; only its context decides.
    if text:
        questions["intent"] = Choice(
            instructions="What does the user want their food-tracking assistant to do with `message`?",
            criteria=logic.ROUTE_INTENTS,
        )
    response, cost = await jev.ask(user_id, f"route-{uuid.uuid4()}", state, questions)
    intent = response.choices.get("intent")
    route, reason = logic.route_decision(
        intent.choice if intent else None,
        intent.confidence if intent else 1.0,
        response.nouls["depends_on_conversation"].noul,
    )
    return {
        "route": route,
        "reason": reason,
        "jev": jev.debug(state, questions, response),
    }, cost


def _extract_model(images: list[str]) -> str:
    return providers.PHOTO_EXTRACT_MODEL if images else providers.TEXT_EXTRACT_MODEL


async def _complete(
    user_id: str, model_id: str, messages: list[dict], output: type[_Output]
) -> tuple[_Output, float, dict]:
    """One structured-output completion, validated into `output`."""
    client = providers.get_client()
    response = await client.chat.completions.create(
        model=model_id,
        messages=messages,  # type: ignore[arg-type]
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": output.__name__.lower(),
                "strict": True,
                "schema": logic.inline_refs(output.model_json_schema()),
            },
        },
        max_completion_tokens=LLM_MAX_COMPLETION_TOKENS,
        extra_body={"reasoning": {"effort": providers.REASONING_EFFORT}},
    )
    usage = response.usage.model_dump() if response.usage else {}
    cost = await get_openrouter_cost(model_id=model_id, usage=usage) if usage else 0.0
    if usage:
        repository.record_invocation(user_id, model_id, cost, usage, extract_tokens(usage))
    choice = response.choices[0]
    raw = choice.message.content or ""
    if choice.finish_reason == "length":
        reasoning = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
        spent = f", {reasoning} of them reasoning" if reasoning else ""
        raise RuntimeError(
            f"{model_id} ran out of output tokens "
            f"({LLM_MAX_COMPLETION_TOKENS}{spent}) before finishing its answer"
        )
    if not raw.strip():
        raise RuntimeError(
            f"{model_id} returned no content (finish reason: {choice.finish_reason})"
        )
    return output.model_validate(logic.parse_json(raw)), cost, usage


async def _extract(
    user_id: str, text: str, images: list[str], now: str
) -> tuple[Extraction, float, dict]:
    content: list[dict] = []
    if text:
        content.append({"type": "text", "text": text})
    for url in images:
        content.append({"type": "image_url", "image_url": {"url": url}})
    messages = [
        {"role": "system", "content": EXTRACT_PROMPT.format(now=now)},
        {"role": "user", "content": content},
    ]
    return await _complete(user_id, _extract_model(images), messages, Extraction)


async def _retrieve(user_id: str, items: list[ExtractedItem]) -> list[list[dict]]:
    async def search(query: str) -> tuple[list, list]:
        # One embedding per query, shared by both searches.
        embedding = await asyncio.to_thread(embeddings.generate_embedding, query)
        return await asyncio.gather(
            asyncio.to_thread(
                agent_repository.search_ingredients,
                query, logic.CANDIDATES_PER_KIND, user_id, embedding,
            ),
            asyncio.to_thread(
                agent_repository.search_recipes,
                query, logic.CANDIDATES_PER_KIND, user_id, embedding,
            ),
        )

    async def candidates_for(item: ExtractedItem) -> list[dict]:
        results = await asyncio.gather(*(search(q) for q in logic.search_queries(item)))
        ingredients = logic.closest([i for found, _ in results for i in found])
        recipes = logic.closest([r for _, found in results for r in found])
        nutrition = await asyncio.to_thread(
            repository.recipe_nutrition, [str(r.id) for r in recipes], user_id
        )
        candidates = [
            logic.ingredient_candidate(f"c{n}", i) for n, i in enumerate(ingredients)
        ]
        candidates += [
            logic.recipe_candidate(f"c{len(candidates) + n}", r, nutrition.get(str(r.id)))
            for n, r in enumerate(recipes)
        ]
        return candidates

    return list(await asyncio.gather(*(candidates_for(item) for item in items)))


async def _resolve(
    user_id: str,
    text: str,
    items: list[ExtractedItem],
    candidates: list[list[dict]],
    day: str,
    now: str,
) -> tuple[Resolution, float, dict]:
    """Match each food to a candidate and decide how to log it, in one call."""
    foods = logic.resolver_foods(items, candidates)
    messages = [
        {
            "role": "system",
            "content": RESOLVE_PROMPT.format(
                now=now, day=day, message=json.dumps(text or "(photo only)")
            ),
        },
        {"role": "user", "content": json.dumps({"foods": foods}, ensure_ascii=False)},
    ]
    resolution, cost, usage = await _complete(
        user_id, providers.RESOLVE_MODEL, messages, Resolution
    )
    return resolution, cost, {"foods": foods, "usage": usage}


# ── Entry point ───────────────────────────────────────────────────────────────


async def run(input: PipelineInput) -> AsyncGenerator[PipelineStep, None]:
    """Run the pipeline, streaming every stage; the last step is a `DoneStep`."""
    started = time.perf_counter()
    total_cost = 0.0
    stage: StageName = "normalize"
    t = started

    def done(outcome, message: str, draft: dict | None = None) -> DoneStep:
        return DoneStep(
            outcome=outcome,
            message=message,
            total_ms=_ms(started),
            total_cost=total_cost,
            draft=draft,
        )

    try:
        timezone = agent_repository.get_user_timezone(input.user_id)
        now = datetime.datetime.now(tz=ZoneInfo(timezone))
        today = now.strftime("%Y-%m-%d")
        day = input.day or today

        # 1. Normalize
        t = time.perf_counter()
        text, images, displayable = await _normalize(input.message)
        yield StageStep(
            name=stage,
            status="ok",
            summary=f"{len(text)} chars of text, {len(images)} photo(s)",
            ms=_ms(t),
            data={
                "text": text,
                "images": displayable,
                "timezone": timezone,
                "day": day,
                "now": now.strftime("%Y-%m-%d %H:%M"),
            },
        )
        if not text and not images:
            yield done("nothing", "Empty message.")
            return

        # 2. Route
        stage = "route"
        t = time.perf_counter()
        if input.skip_route:
            decision, cost = {"route": "pipeline", "reason": "Requested by the agent."}, 0.0
        else:
            decision, cost = await _route(input.user_id, input, text, len(images))
        total_cost += cost
        yield StageStep(
            name=stage,
            status="skipped" if input.skip_route else "ok",
            summary=f"{decision['route']}: {decision['reason']}",
            ms=_ms(t),
            cost=cost,
            model=None if input.skip_route else "jev",
            data=decision,
        )
        if decision["route"] != "pipeline":
            yield done("handoff", decision["reason"])
            return

        # 3. Extract
        stage = "extract"
        t = time.perf_counter()
        extraction, cost, usage = await _extract(
            input.user_id, text, images, now.strftime("%Y-%m-%d %H:%M")
        )
        total_cost += cost
        items = extraction.items
        yield StageStep(
            name=stage,
            status="ok",
            summary=f"{len(items)} item(s): "
            + ", ".join(f"{logic.amount(i)} {i.name}" for i in items),
            ms=_ms(t),
            cost=cost,
            model=_extract_model(images),
            data={"items": [i.model_dump() for i in items], "usage": usage},
        )
        if not items:
            yield done("nothing", "No food found in the message.")
            return

        # 4. Retrieve
        stage = "retrieve"
        t = time.perf_counter()
        candidates = await _retrieve(input.user_id, items)
        yield StageStep(
            name=stage,
            status="ok",
            summary=", ".join(f"{item.name}: {len(c)}" for item, c in zip(items, candidates)),
            ms=_ms(t),
            data=[
                {"item": item.name, "queries": logic.search_queries(item), "candidates": c}
                for item, c in zip(items, candidates)
            ],
        )

        # 5. Resolve
        stage = "resolve"
        t = time.perf_counter()
        resolution, cost, debug = await _resolve(
            input.user_id,
            text,
            items,
            candidates,
            day,
            now.strftime("%Y-%m-%d %H:%M"),
        )
        total_cost += cost
        rows = logic.draft_rows(
            items, candidates, resolution, day, now.strftime("%H:%M"), day == today
        )
        enriched = [logic.enrich_row(row) for row in rows]
        yield StageStep(
            name=stage,
            status="ok",
            summary=", ".join(
                f"{logic.row_label(row)} ({row['confidence']})" for row in rows
            ),
            ms=_ms(t),
            cost=cost,
            model=providers.RESOLVE_MODEL,
            data={"resolution": resolution.model_dump(), "rows": enriched, **debug},
        )

        # 6. Draft
        stage = "draft"
        t = time.perf_counter()
        draft = await asyncio.to_thread(
            create_draft, input.user_id, day, text, rows, total_cost, input.via
        )
        yield StageStep(
            name=stage,
            status="ok",
            summary=f"Saved draft {draft['id']}, waiting for confirmation",
            ms=_ms(t),
            data={"draft_id": draft["id"]},
        )
        yield done("drafted", logic.draft_message(rows), draft)
    except Exception as e:
        yield StageStep(name=stage, status="error", summary=str(e), ms=_ms(t))
        yield done("error", f"{stage} failed: {e}")


# ── Drafts ────────────────────────────────────────────────────────────────────


def _serialize(draft: dict) -> dict:
    return {
        "id": str(draft["id"]),
        "created_at": draft["created_at"].isoformat(),
        "day": draft["day"].isoformat(),
        "status": draft["status"],
        "message": draft["message"],
        "rows": [logic.enrich_row(row) for row in draft["rows"]],
    }


def create_draft(
    user_id: str, day: str, message: str, rows: list[dict], cost: float, via: DraftVia
) -> dict:
    return _serialize(repository.insert_draft(user_id, day, message, rows, cost, via))


def add_draft_cost(draft_id: str, cost: float) -> None:
    """Count more of what logging these foods cost, e.g. the agent's turn."""
    repository.add_draft_cost(UUID(draft_id), cost)


def get_draft(user_id: str, draft_id: UUID) -> dict | None:
    draft = repository.get_draft(user_id, draft_id)
    return _serialize(draft) if draft else None


async def draft_food(
    user_id: str, description: str, image_urls: list[str], day: str | None
) -> dict:
    """Draft a food log from the agent's description, skipping the router.

    This is how the agent logs food, so every log is the same kind of draft
    the user confirms.
    """
    parts = [agent_models.UserMessagePart(text=description)] + [
        agent_models.UserMessagePart(url=url, mime_type="image/*") for url in image_urls
    ]
    message = agent_models.RunAgentUserMessage(parts=parts)
    async for step in run(
        PipelineInput(
            user_id=user_id, message=message, day=day, skip_route=True, via="agent"
        )
    ):
        if step.type == "done":
            if step.outcome == "drafted" and step.draft:
                return step.draft
            raise DraftError(step.message)
    raise DraftError("The pipeline ended without a result.")


def get_log_costs() -> list[dict]:
    """What creating a draft from chat costs on average, by route: straight
    through the pipeline, or through the agent (its turn included)."""
    return [
        {**row, "cost_per_log": row["total_cost"] / row["logs"]}
        for row in repository.get_log_costs()
    ]


def list_day_entries(user_id: str, day: str) -> dict:
    """A day's pending drafts and logs, in one response so they update together."""
    drafts, logs = repository.get_day_entries(user_id, day)
    return {"drafts": [_serialize(d) for d in drafts], "logs": logs}


async def _revise(
    user_id: str, day: str, current: str, meal_type: str, hhmm: str,
    said: str | None, instruction: str,
) -> list[dict]:
    """Rows for an entry after a correction in the user's words.

    The entry and the correction go through the same extract → retrieve →
    resolve steps as a new log, so the correction can switch to a food that
    wasn't among the original matches, and foods it adds become extra rows.
    """
    instruction = instruction.strip()
    if not instruction:
        raise DraftError("Describe what should change.")
    timezone = agent_repository.get_user_timezone(user_id)
    now = datetime.datetime.now(tz=ZoneInfo(timezone))
    message = logic.revision_message(current, meal_type, hhmm, said, instruction)
    extraction, _, _ = await _extract(
        user_id, message, [], now.strftime("%Y-%m-%d %H:%M")
    )
    if not extraction.items:
        raise DraftError("Couldn't tell what to change; try rephrasing.")
    candidates = await _retrieve(user_id, extraction.items)
    resolution, _, _ = await _resolve(
        user_id, message, extraction.items, candidates, day,
        now.strftime("%Y-%m-%d %H:%M"),
    )
    return logic.draft_rows(
        extraction.items, candidates, resolution, day, now.strftime("%H:%M"),
        day == now.strftime("%Y-%m-%d"),
    )


async def revise_draft_row(
    user_id: str, draft_id: UUID, row_id: str, instruction: str
) -> dict:
    """Apply a correction in the user's words to one draft row."""
    draft = await asyncio.to_thread(repository.get_pending_draft, user_id, draft_id)
    row = next((r for r in draft["rows"] if r["id"] == row_id), None)
    if row is None:
        raise DraftError(f"Unknown row '{row_id}'.")
    new_rows = await _revise(
        user_id, draft["day"].isoformat(), logic.row_label(row), row["meal_type"],
        row["log_for"][-5:], row.get("said"), instruction,
    )
    updated = await asyncio.to_thread(
        repository.update_pending_rows,
        user_id,
        draft_id,
        lambda rows: logic.replace_row(rows, row_id, new_rows),
    )
    return _serialize(updated)


async def revise_logs(
    user_id: str, day: str, log_ids: list[str], instruction: str
) -> dict:
    """Apply a correction in the user's words to logged entries (one card).

    The corrected entries are written before the old ones are deleted, so a
    failure leaves the original log in place.
    """
    wanted = set(log_ids)
    logs = [
        log
        for log in await asyncio.to_thread(agent_repository.get_logs_by_day, day, user_id)
        if str(log.id) in wanted
    ]
    if not logs or len(logs) != len(wanted):
        raise DraftError("Entry not found; it may have been deleted.")
    current, meal_type, hhmm = logic.describe_logs(logs)
    new_rows = await _revise(
        user_id, day, current, meal_type, hhmm, None, instruction
    )
    result = await asyncio.to_thread(_write_rows, user_id, new_rows)
    if any(not r["success"] for r in result["results"]):
        return result
    deleted = await asyncio.to_thread(tools.delete_logs_tool, user_id, list(wanted))
    return {**result, "deleted": deleted["results"]}


def delete_logs(user_id: str, log_ids: list[str]) -> dict:
    return tools.delete_logs_tool(user_id=user_id, log_ids=log_ids)


def delete_draft_row(user_id: str, draft_id: UUID, row_id: str) -> dict | None:
    """Remove one row; returns the draft, or None once its last row is gone."""
    draft = repository.remove_row(user_id, draft_id, row_id)
    return _serialize(draft) if draft else None


def discard_draft(user_id: str, draft_id: UUID) -> None:
    repository.discard_pending(user_id, draft_id)


def confirm_draft(
    user_id: str, draft_id: UUID, row_ids: list[str] | None = None
) -> dict:
    """Log some rows of a draft (all when `row_ids` is None).

    New ingredients are created first. The writes reuse the existing
    repository functions, which open their own connections, so this isn't a
    single transaction:
    - if creating an ingredient fails, the rows go back to the draft, keeping
      the ingredients already created so a retry doesn't duplicate them;
    - once logging starts the rows stay taken, and entries that failed are
      reported in the result (retrying would duplicate the others).
    """
    rows = repository.take_rows(user_id, draft_id, row_ids)
    try:
        created = _create_new_ingredients(user_id, rows)
    except Exception:
        repository.put_back_rows(draft_id, rows)
        raise
    result = tools.log_entries_tool(
        user_id=user_id, entries=[logic.log_entry(row) for row in rows]
    )
    return {"created_ingredients": created, **result}


def _create_new_ingredients(user_id: str, rows: list[dict]) -> list[dict]:
    """Create the ingredients of rows targeting "new"; ids are set on the rows."""
    created = []
    for row in rows:
        target = logic.alternative(row)
        if target["kind"] != "new" or target.get("id"):
            continue
        ingredient = agent_repository.insert_ingredient(
            agent_models.InsertIngredientInput(
                name=target["name"],
                brand=target.get("brand"),
                state=target["state"],
                **{k: round(v) for k, v in target["per_100g"].items()},
            ),
            user_id,
        )
        target["id"] = str(ingredient.id)
        created.append({"id": target["id"], "name": ingredient.name})
    return created


def _write_rows(user_id: str, rows: list[dict]) -> dict:
    created = _create_new_ingredients(user_id, rows)
    result = tools.log_entries_tool(
        user_id=user_id, entries=[logic.log_entry(row) for row in rows]
    )
    return {"created_ingredients": created, **result}
