"""Structured food-logging pipeline.

Replaces the quick-log agent loop with a fixed sequence of steps, where each
model only makes the decision it is good at:

    normalize → route (Jev) → extract (LLM) → retrieve (code)
              → resolve (Jev) → plan (code) → draft (persisted)

Nothing is logged directly: the result is a draft the user reviews, edits, and
confirms. Whatever the router doesn't recognize as a new food log is handed
back to the caller, which falls back to the agent.
"""

import asyncio
import base64
import datetime
import time
import uuid
from typing import AsyncGenerator
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
from src.pipeline.models import (
    DoneStep,
    ExtractedItem,
    Extraction,
    PipelineInput,
    PipelineStep,
    StageName,
    StageStep,
)

# Cheapest model with good vision at this price point; reasoning kept low since
# extraction is perception + lookup, not multi-step reasoning.
EXTRACT_MODEL_ID = "google/gemini-3.8-flash"
EXTRACT_REASONING_EFFORT = "low"
EXTRACT_MAX_COMPLETION_TOKENS = 4096

EXTRACT_PROMPT = """You turn a food log message (text and/or photos) into structured items for a nutrition tracker. The user's local time is {now}.

- One item per distinct food or drink. Split a meal into its components, unless it is a well-known single dish (e.g. "lasagna", "cappuccino").
- Keep the user's quantities. When they give none, assume a typical single portion.
- Fill every field following its description. `per_100g` must be realistic for the food in the given `state`.
- If the message does not describe anything eaten or drunk, return an empty `items` list."""


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
            images.append(await inline_image_url(part.url))
            displayable.append(part.url)
        elif part.data and mime.startswith("image/"):
            images.append(f"data:{mime};base64,{base64.b64encode(part.data).decode()}")
    return text, images, displayable


async def _route(
    user_id: str, session_id: str, text: str, image_count: int
) -> tuple[dict, float]:
    if not text:
        return {
            "route": "pipeline",
            "reason": "Photo without text: assumed to be food to log.",
        }, 0.0
    state = {"message": text, "attached_photos": image_count}
    questions: dict[str, jev.Question] = {
        "intent": Choice(
            instructions="What does the user want their food-tracking assistant to do with `message`?",
            criteria=logic.ROUTE_INTENTS,
        ),
        "refers_to_past": Noul(
            instructions="Does `message` identify the foods only by pointing to an earlier meal or earlier logs (e.g. 'same as yesterday', 'my usual breakfast') instead of naming them?",
        ),
    }
    response, cost = await jev.ask(user_id, session_id, state, questions)
    intent = response.choices["intent"]
    route, reason = logic.route_decision(
        intent.choice, intent.confidence, response.nouls["refers_to_past"].noul
    )
    return {
        "route": route,
        "reason": reason,
        "jev": jev.debug(state, questions, response),
    }, cost


async def _extract(
    user_id: str, model_id: str, text: str, images: list[str], now: str
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
    client = providers.get_client(providers.get_provider(model_id))
    response = await client.chat.completions.create(
        model=model_id,
        messages=messages,  # type: ignore[arg-type]
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "extraction",
                "strict": True,
                "schema": logic.inline_refs(Extraction.model_json_schema()),
            },
        },
        max_completion_tokens=EXTRACT_MAX_COMPLETION_TOKENS,
        extra_body={"reasoning": {"effort": EXTRACT_REASONING_EFFORT}},
    )
    usage = response.usage.model_dump() if response.usage else {}
    cost = await get_openrouter_cost(model_id=model_id, usage=usage) if usage else 0.0
    if usage:
        repository.record_invocation(user_id, model_id, cost, usage, extract_tokens(usage))
    raw = response.choices[0].message.content or ""
    return Extraction.model_validate(logic.parse_json(raw)), cost, usage


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
    session_id: str,
    text: str,
    items: list[ExtractedItem],
    candidates: list[list[dict]],
) -> tuple[list[dict], float, dict | None]:
    """Pick one candidate per item and, speculatively, a serving size per candidate."""
    state = {
        "message": text or "(photo only)",
        "foods": [
            {
                "said": item.said or None,
                "name": item.name,
                "brand": item.brand,
                "amount": logic.amount(item),
            }
            for item in items
        ],
    }
    questions: dict[str, jev.Question] = {}
    for i, (item, cands) in enumerate(zip(items, candidates)):
        if not cands:
            continue
        questions[f"match_{i}"] = Choice(
            instructions=f"Which database entry is the same food as `foods[{i}]`?",
            criteria={
                **{c["key"]: logic.describe_candidate(c) for c in cands},
                "none": "None of these entries is the same food",
            },
        )
        # Speculative fan-out: ask the serving question for every candidate in
        # the same request, and only read the one for the chosen candidate.
        if item.unit in ("piece", "serving"):
            for c in cands:
                if c["kind"] != "ingredient" or not c["serving_sizes"]:
                    continue
                questions[f"serving_{i}_{c['key']}"] = Choice(
                    instructions=f"Which serving size of '{c['name']}' is the unit used in `foods[{i}].amount`?",
                    criteria={
                        **{f"s{n}": ss["label"] for n, ss in enumerate(c["serving_sizes"])},
                        "none": "None of these serving sizes is that unit",
                    },
                )

    if not questions:
        return logic.resolve_answers({}, candidates), 0.0, None
    response, cost = await jev.ask(user_id, session_id, state, questions)
    resolutions = logic.resolve_answers(response.choices, candidates)
    return resolutions, cost, jev.debug(state, questions, response)


# ── Entry point ───────────────────────────────────────────────────────────────


async def run(input: PipelineInput) -> AsyncGenerator[PipelineStep, None]:
    """Run the pipeline, streaming every stage; the last step is a `DoneStep`."""
    started = time.perf_counter()
    session_id = f"pipeline-{uuid.uuid4()}"
    total_cost = 0.0
    stage: StageName = "normalize"

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
        model_id = input.model or EXTRACT_MODEL_ID

        # 1. Normalize
        t = time.perf_counter()
        text, images, displayable = await _normalize(input.message)
        yield StageStep(
            name=stage,
            status="ok",
            summary=f"{len(text)} chars of text, {len(images)} photo(s)",
            ms=_ms(t),
            data={
                "session_id": session_id,
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
        decision, cost = await _route(input.user_id, session_id, text, len(images))
        total_cost += cost
        yield StageStep(
            name=stage,
            status="ok" if cost else "skipped",
            summary=f"{decision['route']}: {decision['reason']}",
            ms=_ms(t),
            cost=cost,
            model="jev" if cost else None,
            data=decision,
        )
        if decision["route"] != "pipeline":
            yield done("handoff", decision["reason"])
            return

        # 3. Extract
        stage = "extract"
        t = time.perf_counter()
        extraction, cost, usage = await _extract(
            input.user_id, model_id, text, images, now.strftime("%Y-%m-%d %H:%M")
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
            model=model_id,
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
        resolutions, cost, jev_debug = await _resolve(
            input.user_id, session_id, text, items, candidates
        )
        total_cost += cost
        yield StageStep(
            name=stage,
            status="ok" if jev_debug else "skipped",
            summary=", ".join(
                f"{item.name} → {r['candidate']['name'] if r['candidate'] else 'new'} ({r['status']})"
                for item, r in zip(items, resolutions)
            ),
            ms=_ms(t),
            cost=cost,
            model="jev" if jev_debug else None,
            data={
                "resolutions": [
                    {"item": item.name, **r} for item, r in zip(items, resolutions)
                ],
                "jev": jev_debug,
            },
        )

        # 6. Plan
        stage = "plan"
        t = time.perf_counter()
        rows = logic.draft_rows(
            items, resolutions, candidates, day, now.strftime("%H:%M"), day == today
        )
        enriched = [logic.enrich_row(row) for row in rows]
        flagged = sum(1 for row in enriched if row["flags"])
        yield StageStep(
            name=stage,
            status="ok",
            summary=f"{len(rows)} row(s), {flagged} flagged for review",
            ms=_ms(t),
            data=enriched,
        )

        # 7. Draft
        stage = "draft"
        t = time.perf_counter()
        draft = await asyncio.to_thread(
            create_draft, input.user_id, day, text, rows
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
        yield StageStep(name=stage, status="error", summary=str(e), ms=0)
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


def create_draft(user_id: str, day: str, message: str, rows: list[dict]) -> dict:
    return _serialize(repository.insert_draft(user_id, day, message, rows))


def list_drafts(user_id: str, day: str) -> list[dict]:
    return [_serialize(d) for d in repository.get_pending_drafts(user_id, day)]


def update_draft(user_id: str, draft_id: UUID, edits: list[dict]) -> dict:
    return _serialize(
        repository.update_pending_rows(
            user_id, draft_id, lambda rows: logic.apply_edits(rows, edits)
        )
    )


def discard_draft(user_id: str, draft_id: UUID) -> None:
    repository.discard_pending(user_id, draft_id)


def confirm_draft(user_id: str, draft_id: UUID) -> dict:
    """Write the draft's logs, creating its new ingredients first.

    The draft is claimed up front so a double click can't log it twice. The
    writes reuse the existing repository functions, which open their own
    connections, so this isn't a single transaction:
    - if creating an ingredient fails, the draft returns to pending, keeping
      the ingredients already created so a retry doesn't duplicate them;
    - once logging starts the draft stays confirmed, and entries that failed
      are reported in the result (retrying would duplicate the others).
    """
    rows = repository.claim_pending(user_id, draft_id)["rows"]
    created = []
    try:
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
    except Exception:
        repository.save_rows(draft_id, rows, release=True)
        raise
    repository.save_rows(draft_id, rows)
    result = tools.log_entries_tool(
        user_id=user_id, entries=[logic.log_entry(row) for row in rows]
    )
    return {"created_ingredients": created, **result}
