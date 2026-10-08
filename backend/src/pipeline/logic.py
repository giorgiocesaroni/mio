"""Pure logic of the structured logging pipeline and its drafts.

A draft row looks like:

    {
      "id": "r0",
      "said": "cotolette AIA",               # the user's words
      "dish_id": null,                       # the draft-local group this row belongs to
      "dish": null,                          # the dish's name, when it has several components
      "assumed": false,                      # a usual component nobody mentioned
      "alternatives": [                      # what the user may pick from
        {"key": "c0", "kind": "ingredient", "id": "…", "name": "AIA chicken cutlet",
         "brand": "AIA", "state": "raw", "per_100g": {...},
         "serving_sizes": [...], "probability": 0.97},
        {"key": "new", "kind": "new", "name": "Breaded chicken cutlet", ...},
      ],
      "target": "c0",                        # chosen alternative
      "auto_target": "c0",                   # what the pipeline chose
      "confidence": "high",                  # the resolver's: high/medium/low
      "note": null,                          # the resolver's assumption, if any
      "quantity": 2, "unit": "serving", "serving_size_id": "…",
      "meal_type": "dinner", "log_for": "2026-09-26 20:15",
      "item_state": "cooked",                # state the amount refers to
      "grams_estimated": false,
    }

`enrich_row` adds the derived `grams`, `macros`, and `flags`. Rows only
change through the pipeline or the entry editor, and alternatives are always
what retrieval found for this user, so a client can never introduce an id of
its own.
"""

import copy
import json
import math
import re

from src.pipeline.models import (
    DraftError,
    ExtractedDish,
    ExtractedItem,
    Extraction,
    Resolution,
    ResolvedRecipe,
    ResolvedRow,
    StageStep,
)

# ── Configuration ─────────────────────────────────────────────────────────────

CANDIDATES_PER_KIND = 4

# A matched ingredient whose calories differ from the extraction's estimate
# (same state) by both this factor and this many kcal per 100 g is likely a
# different food, e.g. a sausage ragù matched to plain sausage.
MISMATCH_KCAL_RATIO = 2.0
MISMATCH_KCAL_MIN_DIFF = 100

# Drafts created by the earlier Jev resolver store a numeric confidence.
LEGACY_MATCH_MIN_CONFIDENCE = 0.6

MEAL_TYPES = ("breakfast", "lunch", "dinner", "snack")

MEAL_DEFAULT_TIMES = {
    "breakfast": "08:00",
    "lunch": "13:00",
    "snack": "16:30",
    "dinner": "20:00",
}

# ── Parsing ───────────────────────────────────────────────────────────────────


def parse_json(content: str) -> dict:
    """Parse a JSON object, tolerating Markdown fences around it."""
    fenced = re.search(r"```(?:json)?\s*(.*?)```", content, re.DOTALL)
    return json.loads(fenced.group(1) if fenced else content)


def inline_refs(schema: dict) -> dict:
    """Inline pydantic's `$defs`, since some strict-mode providers reject `$ref` siblings."""
    defs = schema.pop("$defs", {})

    def walk(node):
        if isinstance(node, dict):
            if "$ref" in node:
                target = defs[node["$ref"].split("/")[-1]]
                return walk({**target, **{k: v for k, v in node.items() if k != "$ref"}})
            return {k: walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    return walk(schema)


def parse_hhmm(value: str | None) -> str | None:
    """Normalize a model-provided time ('8:30', '2026-09-26 08:30', ...) to HH:MM."""
    match = re.search(r"(\d{1,2}):(\d{2})", value or "")
    if not match or int(match.group(1)) > 23 or int(match.group(2)) > 59:
        return None
    return f"{int(match.group(1)):02d}:{match.group(2)}"


def infer_meal_type(hhmm: str) -> str:
    hour = int(hhmm[:2])
    if hour < 11:
        return "breakfast"
    if hour < 15:
        return "lunch"
    if hour < 18:
        return "snack"
    return "dinner"


def amount(item: ExtractedItem) -> str:
    match item.unit:
        case "g" | "ml":
            return f"{item.quantity:g} {item.unit}"
        case "recipe":
            return f"{item.quantity:g} × recipe"
        case _:
            plural = "" if item.quantity == 1 or item.unit.endswith("s") else "s"
            return f"{item.quantity:g} {item.unit}{plural}"


def extraction_summary(extraction: Extraction) -> str:
    def dish(d: ExtractedDish) -> str:
        parts = ", ".join(
            f"{amount(c)} {c.name}{' (assumed)' if c.assumed else ''}" for c in d.components
        )
        return parts if len(d.components) == 1 else f"{dish_label(d.name)} ({parts})"

    return "; ".join(dish(d) for d in extraction.dishes)


def dish_label(name: str) -> str:
    """A dish's display name: the model's own casing, with the first letter
    capitalized in case it ignored the instruction and returned all lowercase."""
    return name[:1].upper() + name[1:] if name else name


# ── Routing ───────────────────────────────────────────────────────────────────

ROUTE_INTENTS = {
    "log_food": "Record foods or drinks they ate, are eating, or will eat",
    "edit_logs": "Correct, change, move, or remove foods that are already logged or drafted",
    "ask": "Get an answer or advice, e.g. about nutrition, their intake, or their progress, without logging anything",
    "other": "Anything else, such as setting goals, recording body weight, or managing recipes and ingredients",
    "unclear": "The message could mean more than one of these",
}

# Longest assistant reply the router reads; its end is where a question is.
ROUTE_REPLY_MAX_CHARS = 600


def route_state(
    text: str, image_count: int, last_reply: str | None, pending_draft: list[str] | None
) -> dict:
    """What the router sees: the message, plus the conversation it may depend on."""
    if last_reply and len(last_reply) > ROUTE_REPLY_MAX_CHARS:
        last_reply = "…" + last_reply[-ROUTE_REPLY_MAX_CHARS:]
    return {
        "message": text,
        "attached_photos": image_count,
        "assistant_last_reply": last_reply,
        "pending_draft": pending_draft,
    }


def route_decision(intent: str | None, depends_on_conversation: bool) -> tuple[str, str]:
    """Return (route, reason): "pipeline" for new food logs, "agent" otherwise.

    `intent` is None for a photo without text, which is a new meal unless it
    answers or corrects what came before.
    """
    if depends_on_conversation:
        return "agent", "Depends on the conversation."
    if intent is None:
        return "pipeline", "Photo of a new meal."
    if intent != "log_food":
        return "agent", f"Intent is '{intent}', not a new log."
    return "pipeline", "New food log."


# ── Status ────────────────────────────────────────────────────────────────────

# What the pipeline does next once a stage is done, shown to the user.
STATUS_AFTER_STAGE = {
    "normalize": "Reading your message",
    "route": "Extracting foods",
    "extract": "Retrieving your foods",
    "retrieve": "Resolving quantities",
    "resolve": "Saving the draft",
}


def status_after(step: StageStep) -> str | None:
    """The status once `step` is done, or None when the pipeline stops there."""
    if step.status == "error":
        return None
    if step.name == "route" and (step.data or {}).get("route") != "pipeline":
        return None
    return STATUS_AFTER_STAGE.get(step.name)


# ── Retrieval and resolution ──────────────────────────────────────────────────


def search_queries(item: ExtractedItem) -> list[str]:
    """The user's own words keep specific terms ("pan bauletto") that the
    normalized English name can paraphrase away; search with both."""
    normalized = f"{item.brand} {item.name}" if item.brand else item.name
    return list(dict.fromkeys(q for q in (item.said.strip(), normalized) if q))


def dish_queries(dish: ExtractedDish) -> list[str]:
    """Where a dish is more than one food, its saved recipes are searched by
    the dish's name; a single food is searched like any other item."""
    if len(dish.components) < 2:
        return []
    return list(dict.fromkeys(q for q in (dish.said.strip(), dish.name) if q))


def closest(found: list) -> list:
    """Dedupe results from several queries, keeping each entry's best distance."""
    best: dict = {}
    for entry in found:
        current = best.get(entry.id)
        if current is None or (entry.distance or 1) < (current.distance or 1):
            best[entry.id] = entry
    return sorted(best.values(), key=lambda e: e.distance or 1)[:CANDIDATES_PER_KIND]


def ingredient_candidate(key: str, i) -> dict:
    return {
        "key": key,
        "kind": "ingredient",
        "id": str(i.id),
        "name": i.name,
        "brand": i.brand,
        "state": i.state,
        "distance": i.distance,
        "per_100g": {
            "calories_kcal": float(i.calories_kcal),
            "protein_g": float(i.protein_g),
            "carbs_g": float(i.carbs_g),
            "fat_g": float(i.fat_g),
        },
        "serving_sizes": [s.model_dump() for s in i.serving_sizes],
    }


def recipe_candidate(key: str, r, nutrition: dict | None) -> dict:
    return {
        "key": key,
        "kind": "recipe",
        "id": str(r.id),
        "name": r.name,
        "distance": r.distance,
        "total_g": nutrition["total_g"] if nutrition else 0.0,
        "per_100g": (
            nutrition["per_100g"]
            if nutrition
            else {"calories_kcal": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}
        ),
    }


def resolver_dishes(
    extraction: Extraction,
    candidates: list[list[dict]],
    dish_recipes: list[list[dict]],
) -> list[dict]:
    """What the resolver sees: each dish with its saved-recipe candidates and
    its components with theirs, ids replaced by keys. A component's `item` is
    its index among all components."""
    dishes = []
    index = 0
    for dish, recipes in zip(extraction.dishes, dish_recipes):
        components = []
        for item in dish.components:
            components.append(
                {
                    "item": index,
                    "said": item.said or None,
                    "name": item.name,
                    "brand": item.brand,
                    "amount": amount(item),
                    "estimated_grams": item.grams,
                    "estimated_state": item.state,
                    "assumed": item.assumed,
                    "candidates": [_resolver_candidate(c) for c in candidates[index]],
                }
            )
            index += 1
        entry = {"said": dish.said or None, "name": dish.name}
        if recipes:
            entry["estimated_total_grams"] = round(sum(c.grams for c in dish.components))
            entry["saved_recipes"] = [_resolver_candidate(c) for c in recipes]
        entry["components"] = components
        dishes.append(entry)
    return dishes


def _resolver_candidate(c: dict) -> dict:
    if c["kind"] == "recipe":
        return {
            "key": c["key"],
            "kind": "saved recipe",
            "name": c["name"],
            "total_grams": round(c["total_g"]),
            "kcal_per_100g": round(c["per_100g"]["calories_kcal"]),
        }
    return {
        "key": c["key"],
        "kind": "ingredient",
        "name": c["name"],
        "brand": c.get("brand"),
        "state": c.get("state"),
        "kcal_per_100g": round(c["per_100g"]["calories_kcal"]),
        "serving_sizes": [
            {"key": f"s{n}", "label": ss["label"], "grams": round(ss["grams"], 1)}
            for n, ss in enumerate(c.get("serving_sizes", []))
        ],
    }


# How each kind of target can be measured.
UNITS_BY_KIND = {
    "ingredient": ("grams", "serving"),
    "new": ("grams",),
    "recipe": ("grams", "recipe"),
}

_ALTERNATIVE_FIELDS = (
    "key", "kind", "id", "name", "brand", "state", "per_100g", "serving_sizes", "total_g"
)


def _new_alternative(item: ExtractedItem) -> dict:
    # Creating a new ingredient from the extraction's estimate is always an
    # option, so the user can reject every database match.
    return {
        "key": "new",
        "kind": "new",
        "id": None,
        "name": item.name.capitalize(),
        "brand": item.brand,
        "state": item.state,
        "per_100g": item.per_100g.model_dump(),
        "serving_sizes": [],
    }


def _validated(
    resolved: ResolvedRow | None, item: ExtractedItem, alternatives: list[dict]
) -> tuple[dict, list[str]]:
    """Check the resolver's row against what exists; repair what doesn't.

    Returns the row fields and notes about any repairs, so an invalid answer
    degrades to a flagged, editable row instead of failing the draft.
    """
    fallback = {
        "target": "new",
        "unit": "grams",
        "serving_size_id": None,
        "quantity": item.quantity if item.unit == "g" else item.grams,
        "item_state": item.state,
    }
    if resolved is None:
        return fallback, ["The resolver skipped this food"]
    target = next((a for a in alternatives if a["key"] == resolved.target), None)
    if target is None:
        return fallback, [f"Unknown match '{resolved.target}'"]

    fields = {
        "target": target["key"],
        "unit": resolved.unit,
        "serving_size_id": None,
        "quantity": resolved.quantity,
        "item_state": resolved.weight_state,
    }
    repairs = []
    if resolved.unit not in UNITS_BY_KIND[target["kind"]]:
        repairs.append(f"Unit '{resolved.unit}' doesn't apply")
    elif resolved.unit == "serving":
        sizes = target.get("serving_sizes", [])
        index = (
            int(resolved.serving[1:])
            if resolved.serving and resolved.serving[1:].isdigit()
            else -1
        )
        if 0 <= index < len(sizes):
            fields["serving_size_id"] = sizes[index]["id"]
        else:
            repairs.append("Unknown serving size")
    if not math.isfinite(resolved.quantity) or resolved.quantity <= 0:
        repairs.append("Invalid quantity")
    if repairs:
        fields.update(
            unit="grams",
            serving_size_id=None,
            quantity=item.quantity if item.unit == "g" else item.grams,
            item_state=item.state,
        )
    elif item.unit == "g" and (
        fields["unit"] != "grams" or fields["item_state"] == item.state
    ):
        # A weight the user stated is logged as that weight, even when the
        # resolver re-expressed it as servings or a recipe fraction, or changed
        # the grams without converting between raw and cooked (e.g. applying a
        # revision's correction a second time).
        fields.update(
            unit="grams",
            serving_size_id=None,
            quantity=item.quantity,
            item_state=item.state,
        )
    return fields, repairs


def nutrition_mismatch(item: ExtractedItem, target: dict) -> str | None:
    """A note when the matched ingredient's calories are far from what the
    extraction estimated for the food, so the match is likely wrong.

    Only compares the same state: raw and cooked weights legitimately differ.
    """
    if target["kind"] != "ingredient" or target.get("state") != item.state:
        return None
    estimated = item.per_100g.calories_kcal
    matched = target["per_100g"]["calories_kcal"]
    low, high = sorted((estimated, matched))
    if high - low < MISMATCH_KCAL_MIN_DIFF or high < low * MISMATCH_KCAL_RATIO:
        return None
    return (
        f"{target['name']} has {matched:.0f} kcal/100 g, but {item.name} "
        f"is usually about {estimated:.0f}: check it's the same food."
    )


def _when(
    resolved_time: str | None,
    resolved_meal: str | None,
    day: str,
    now_hhmm: str,
    is_today: bool,
) -> tuple[str, str]:
    """(meal type, 'day HH:MM') from the resolver's answer, defaulting to now."""
    meal_type = resolved_meal if resolved_meal in MEAL_TYPES else None
    hhmm = parse_hhmm(resolved_time)
    if not hhmm:
        if is_today:
            hhmm = now_hhmm
        elif meal_type:
            hhmm = MEAL_DEFAULT_TIMES[meal_type]
        else:
            hhmm = "12:00"
    if meal_type is None:
        meal_type = infer_meal_type(hhmm)
    return meal_type, f"{day} {hhmm}"


def _recipe_row(
    dish: ExtractedDish,
    recipes: list[dict],
    resolved: ResolvedRecipe | None,
    day: str,
    now_hhmm: str,
    is_today: bool,
) -> dict | None:
    """The row for a dish the resolver matched to a saved recipe, or None when
    it didn't or the match isn't valid, so the dish is logged by its components."""
    if resolved is None or not math.isfinite(resolved.quantity) or resolved.quantity <= 0:
        return None
    if not any(r["key"] == resolved.target for r in recipes):
        return None
    alternatives = [{k: r[k] for k in _ALTERNATIVE_FIELDS if k in r} for r in recipes]
    alternatives.sort(key=lambda a: a["key"] != resolved.target)
    meal_type, log_for = _when(
        resolved.time, resolved.meal_type, day, now_hhmm, is_today
    )
    return {
        "said": dish.said,
        "dish": dish_label(dish.name),
        "alternatives": alternatives,
        "auto_target": resolved.target,
        "target": resolved.target,
        "unit": "recipe",
        "serving_size_id": None,
        "quantity": resolved.quantity,
        "item_state": "cooked",
        "confidence": resolved.confidence,
        "note": resolved.note,
        "meal_type": meal_type,
        "log_for": log_for,
        "grams_estimated": False,
    }


def missing_rows(
    extraction: Extraction,
    resolution: Resolution,
    dish_recipes: list[list[dict]],
) -> list[int]:
    """Component indices the resolver returned no row for.

    A dish matched to one of its saved recipes needs no per-component rows, so
    its components count as covered — but only when that match would survive
    `_recipe_row`, since an invalid one falls back to per-component rows.
    """
    covered = {r.item for r in resolution.rows}
    by_dish = {r.dish: r for r in resolution.recipes}
    recipe_dishes = set()
    for d, recipes in enumerate(dish_recipes):
        resolved = by_dish.get(d)
        if (
            resolved is not None
            and math.isfinite(resolved.quantity)
            and resolved.quantity > 0
            and any(c["key"] == resolved.target for c in recipes)
        ):
            recipe_dishes.add(d)
    missing = []
    index = 0
    for d, dish in enumerate(extraction.dishes):
        for _ in dish.components:
            if d not in recipe_dishes and index not in covered:
                missing.append(index)
            index += 1
    return missing


def draft_rows(
    extraction: Extraction,
    candidates: list[list[dict]],
    dish_recipes: list[list[dict]],
    resolution: Resolution,
    day: str,
    now_hhmm: str,
    is_today: bool,
) -> list[dict]:
    by_item = {r.item: r for r in resolution.rows}
    by_dish = {r.dish: r for r in resolution.recipes}
    rows = []
    index = 0
    for d, dish in enumerate(extraction.dishes):
        recipe = _recipe_row(
            dish, dish_recipes[d], by_dish.get(d), day, now_hhmm, is_today
        )
        if recipe:
            rows.append(recipe)
            index += len(dish.components)
            continue
        for item in dish.components:
            cands = candidates[index]
            alternatives = [
                {k: c[k] for k in _ALTERNATIVE_FIELDS if k in c} for c in cands
            ] + [_new_alternative(item)]
            resolved = by_item.get(index)
            fields, repairs = _validated(resolved, item, alternatives)
            mismatch = nutrition_mismatch(
                item, next(a for a in alternatives if a["key"] == fields["target"])
            )
            if mismatch:
                repairs.append(mismatch.rstrip("."))
            meal_type, log_for = _when(
                resolved.time if resolved else None,
                resolved.meal_type if resolved else None,
                day, now_hhmm, is_today,
            )

            # The chosen match first, then the other candidates in retrieval order.
            alternatives.sort(key=lambda a: a["key"] != fields["target"])
            multi = len(dish.components) > 1
            rows.append(
                {
                    "said": item.said,
                    "dish_id": f"d{d}" if multi else None,
                    "dish": dish_label(dish.name) if multi else None,
                    "assumed": item.assumed,
                    "alternatives": alternatives,
                    "auto_target": fields["target"],
                    **fields,
                    "confidence": "low" if repairs else (resolved.confidence if resolved else "low"),
                    "note": "; ".join(repairs) + "." if repairs else (resolved.note if resolved else None),
                    "meal_type": meal_type,
                    "log_for": log_for,
                    "grams_estimated": fields["unit"] == "grams" and item.unit != "g",
                }
            )
            index += 1
    return [{"id": f"r{n}", **row} for n, row in enumerate(rows)]


def alternative(row: dict, key: str | None = None) -> dict:
    key = key or row["target"]
    for alt in row["alternatives"]:
        if alt["key"] == key:
            return alt
    raise DraftError(f"Unknown alternative '{key}'.")


def row_grams(row: dict) -> float:
    target = alternative(row)
    match row["unit"]:
        case "serving":
            serving = next(
                (s for s in target.get("serving_sizes", []) if s["id"] == row["serving_size_id"]),
                None,
            )
            return row["quantity"] * serving["grams"] if serving else 0.0
        case "recipe":
            return row["quantity"] * (target.get("total_g") or 0.0)
        case _:
            return row["quantity"]


def row_flags(row: dict) -> list[str]:
    target = alternative(row)
    flags = []
    untouched = not row.get("user_edited") and row["target"] == row["auto_target"]
    confidence = row.get("confidence")
    if target["kind"] == "new":
        flags.append("New ingredient: nutrition facts are estimated")
    if untouched and row.get("note"):
        flags.append(row["note"])
    elif untouched and target["kind"] != "new":
        if isinstance(confidence, (int, float)):
            if confidence < LEGACY_MATCH_MIN_CONFIDENCE:
                flags.append(f"Uncertain match ({confidence:.2f})")
        elif confidence != "high":
            flags.append("Uncertain match")
    if (
        target["kind"] == "ingredient"
        and row["unit"] == "grams"
        and target.get("state")
        and target["state"] != row["item_state"]
    ):
        flags.append(
            f"Amount is {row['item_state']} weight, but the entry is {target['state']}"
        )
    if row.get("assumed") and untouched:
        flags.append("Assumed: not mentioned, but usual for this dish")
    if row["grams_estimated"] and not row.get("user_edited"):
        flags.append("Weight is estimated")
    return flags


def enrich_row(row: dict) -> dict:
    grams = row_grams(row)
    per_100g = alternative(row)["per_100g"]
    return {
        **row,
        "grams": grams,
        "macros": {k: v * grams / 100 for k, v in per_100g.items()},
        "flags": row_flags(row),
    }


def amount_label(row: dict) -> str:
    """The row's amount as the user would read it, e.g. '2 slices'."""
    if row["unit"] == "serving":
        serving = next(
            (
                s
                for s in alternative(row)["serving_sizes"]
                if s["id"] == row["serving_size_id"]
            ),
            None,
        )
        label = (
            (serving["label"] if row["quantity"] == 1 else serving["label_plural"])
            if serving
            else "serving"
        )
        return f"{row['quantity']:g} {label}"
    if row["unit"] == "recipe":
        return f"{row['quantity']:g} × recipe"
    return f"{row['quantity']:g} g"


def row_label(row: dict) -> str:
    return f"{amount_label(row)} {alternative(row)['name']}"


def draft_message(rows: list[dict]) -> str:
    by_meal: dict[str, list[str]] = {}
    for row in rows:
        by_meal.setdefault(row["meal_type"], []).append(row_label(row))
    return (
        "Draft: "
        + "; ".join(f"{', '.join(labels)} ({meal})" for meal, labels in by_meal.items())
        + "."
    )


# ── Editing and confirmation ──────────────────────────────────────────────────


def log_rows(logs: list) -> list[dict]:
    """Draft rows for logged entries shown as one card (a single log, a dish,
    or the logs a saved recipe was dispatched into), so the entry editor can
    edit them like a draft dish. A recipe's logs become a dish named after it."""
    first = logs[0]
    dish = first.dish_name or (first.recipe.name if first.recipe else None)
    rows = []
    for n, log in enumerate(logs):
        food = log.ingredient
        if food is None:
            raise DraftError("This entry can't be edited: one of its foods is missing.")
        serving = next(
            (s for s in food.serving_sizes if s.id == log.serving_size_id), None
        )
        rows.append(
            {
                "id": f"r{n}",
                "log_id": str(log.id),
                "said": "",
                "dish_id": "d0" if len(logs) > 1 else None,
                "dish": dish if len(logs) > 1 else None,
                "assumed": False,
                "alternatives": [
                    {
                        "key": "c0",
                        "kind": "ingredient",
                        "id": str(food.id),
                        "name": food.name,
                        "brand": food.brand,
                        "state": food.state,
                        "per_100g": {
                            "calories_kcal": float(food.calories_kcal),
                            "protein_g": float(food.protein_g),
                            "carbs_g": float(food.carbs_g),
                            "fat_g": float(food.fat_g),
                        },
                        "serving_sizes": [s.model_dump() for s in food.serving_sizes],
                    }
                ],
                "target": "c0",
                "auto_target": "c0",
                "confidence": "high",
                "note": None,
                "quantity": float(log.quantity or 0) if serving else float(log.quantity_g or 0),
                "unit": "serving" if serving else "grams",
                "serving_size_id": str(serving.id) if serving else None,
                "meal_type": log.meal_type,
                "log_for": log.log_for_local or log.log_for.strftime("%Y-%m-%d %H:%M"),
                "item_state": food.state,
                "grams_estimated": False,
            }
        )
    return rows


def group_key(row: dict) -> str:
    """What groups a draft row with its dish's other rows: the dish it is a
    component of, or the row itself for a standalone food."""
    return row.get("dish_id") or row["id"]


class EntryEditor:
    """A working copy of one entry's rows (a draft dish, or a logged card)
    that a correction edits one operation at a time.

    Whatever no operation touches is carried over exactly, so a correction
    can't drift the foods or amounts it doesn't mention. Foods have keys ('f0',
    'f1', ...) shared across rows: every row's alternatives, plus whatever a
    search found or the editor created, so an operation can only reference a
    food the user's search results or the entry already contain.
    """

    def __init__(self, rows: list[dict]):
        if not rows:
            raise DraftError("Nothing to edit.")
        self.original = copy.deepcopy(rows)
        self.rows = copy.deepcopy(rows)
        self.dish_name: str | None = next((r["dish"] for r in rows if r.get("dish")), None)
        self.foods: dict[str, dict] = {}
        # (row id, alternative key) → food key
        self._links: dict[tuple[str, str], str] = {}
        self._next_row = max(int(r["id"][1:]) for r in rows) + 1
        for row in self.rows:
            for alt in row["alternatives"]:
                self._links[(row["id"], alt["key"])] = self.register(alt)

    # ── Foods ──

    def register(self, food: dict) -> str:
        """The key of a food, registering it the first time it's seen. A food
        with an id is one food wherever it appears."""
        if food.get("id"):
            for key, known in self.foods.items():
                if known.get("id") == food["id"] and known["kind"] == food["kind"]:
                    return key
        key = f"f{len(self.foods)}"
        self.foods[key] = {k: food[k] for k in _ALTERNATIVE_FIELDS if k in food and k != "key"}
        return key

    def create(self, name: str, brand: str | None, state: str, per_100g: dict) -> str:
        return self.register(
            {
                "kind": "new",
                "id": None,
                "name": name,
                "brand": brand,
                "state": state,
                "per_100g": per_100g,
                "serving_sizes": [],
            }
        )

    def food_view(self, key: str) -> dict:
        food = self.foods[key]
        view = {
            "key": key,
            "kind": {
                "ingredient": "food",
                "recipe": "saved recipe",
                "new": "new food (estimated nutrition)",
            }[food["kind"]],
            "name": food["name"],
            "brand": food.get("brand"),
            "state": food.get("state"),
            "per_100g": {k: round(v, 1) for k, v in food["per_100g"].items()},
        }
        if food["kind"] == "recipe":
            view["total_grams"] = round(food.get("total_g") or 0)
        if food.get("serving_sizes"):
            view["serving_sizes"] = [
                {"key": f"s{n}", "label": s["label"], "grams": round(s["grams"], 1)}
                for n, s in enumerate(food["serving_sizes"])
            ]
        return view

    def _food(self, key: str) -> dict:
        if key not in self.foods:
            raise DraftError(f"Unknown food '{key}': use a key from the entry or a search.")
        return self.foods[key]

    # ── Rows ──

    def _row(self, row_id: str) -> dict:
        for row in self.rows:
            if row["id"] == row_id:
                return row
        raise DraftError(f"Unknown row '{row_id}'.")

    def _food_key(self, row: dict) -> str:
        return self._links[(row["id"], row["target"])]

    def _link(self, row: dict, food_key: str) -> str:
        """The row's alternative for a food, added when the row lacks it."""
        for alt in row["alternatives"]:
            if self._links.get((row["id"], alt["key"])) == food_key:
                return alt["key"]
        food = self.foods[food_key]
        if food["kind"] == "new":
            # A row has at most one "new" alternative; the created food replaces it.
            row["alternatives"] = [a for a in row["alternatives"] if a["key"] != "new"]
            key = "new"
        else:
            taken = {a["key"] for a in row["alternatives"]}
            key = next(f"x{n}" for n in range(len(taken) + 1) if f"x{n}" not in taken)
        row["alternatives"].append({"key": key, **copy.deepcopy(food)})
        self._links[(row["id"], key)] = food_key
        return key

    def _amount(
        self,
        food: dict,
        quantity: float,
        unit: str,
        serving: str | None,
        weight_state: str | None,
        default_state: str,
    ) -> dict:
        """Validated amount fields for a row logging `food`."""
        if unit not in UNITS_BY_KIND[food["kind"]]:
            raise DraftError(
                f"Unit '{unit}' doesn't apply to {food['name']}; "
                f"use {' or '.join(UNITS_BY_KIND[food['kind']])}."
            )
        if not math.isfinite(quantity) or quantity <= 0:
            raise DraftError("The quantity must be a positive number.")
        serving_size_id = None
        if unit == "serving":
            sizes = food.get("serving_sizes", [])
            index = int(serving[1:]) if serving and serving[1:].isdigit() else -1
            if not 0 <= index < len(sizes):
                raise DraftError(f"Unknown serving '{serving}' for {food['name']}.")
            serving_size_id = sizes[index]["id"]
        return {
            "quantity": quantity,
            "unit": unit,
            "serving_size_id": serving_size_id,
            "item_state": (
                "cooked" if food["kind"] == "recipe" else weight_state or default_state
            ),
        }

    @staticmethod
    def _trusted(row: dict) -> None:
        """The user said so: nothing about the row is a guess anymore."""
        row.update(auto_target=row["target"], confidence="high", note=None)

    # ── Operations ──

    def swap_food(self, row_id: str, food_key: str) -> None:
        row = self._row(row_id)
        food = self._food(food_key)
        grams = row_grams(row)
        row["target"] = self._link(row, food_key)
        # Servings and recipe fractions belong to the old food: keep the weight.
        if row["unit"] != "grams" or "grams" not in UNITS_BY_KIND[food["kind"]]:
            row.update(unit="grams", quantity=round(grams, 1), serving_size_id=None)
        if food["kind"] == "recipe":
            row["item_state"] = "cooked"
        self._trusted(row)

    def set_amount(
        self,
        row_id: str,
        quantity: float,
        unit: str,
        serving: str | None,
        weight_state: str | None,
    ) -> None:
        row = self._row(row_id)
        row.update(
            self._amount(
                alternative(row), quantity, unit, serving, weight_state, row["item_state"]
            ),
            grams_estimated=False,
        )
        self._trusted(row)

    def add_food(
        self,
        food_key: str,
        quantity: float,
        unit: str,
        serving: str | None,
        weight_state: str | None,
    ) -> str:
        food = self._food(food_key)
        template = (self.rows or self.original)[0]
        row = {
            "id": f"r{self._next_row}",
            "said": "",
            "dish_id": None,
            "dish": None,
            "assumed": False,
            "alternatives": [],
            "meal_type": template["meal_type"],
            "log_for": template["log_for"],
            "grams_estimated": False,
            **self._amount(food, quantity, unit, serving, weight_state, food.get("state") or "raw"),
        }
        self._next_row += 1
        row["target"] = self._link(row, food_key)
        self._trusted(row)
        self.rows.append(row)
        return row["id"]

    def remove_food(self, row_id: str) -> None:
        self.rows.remove(self._row(row_id))

    def scale(self, factor: float) -> None:
        if not math.isfinite(factor) or factor <= 0:
            raise DraftError("The factor must be a positive number.")
        for row in self.rows:
            row["quantity"] = round(row["quantity"] * factor, 3)
            row["grams_estimated"] = False

    def set_time(self, hhmm: str | None, meal_type: str | None) -> None:
        time = parse_hhmm(hhmm) if hhmm else None
        if hhmm and not time:
            raise DraftError(f"Invalid time '{hhmm}': use HH:MM.")
        if meal_type is not None and meal_type not in MEAL_TYPES:
            raise DraftError(f"Invalid meal type '{meal_type}'.")
        for row in self.rows:
            if time:
                row["log_for"] = f"{row['log_for'][:10]} {time}"
            if meal_type:
                row["meal_type"] = meal_type

    def rename_dish(self, name: str) -> None:
        if not name.strip():
            raise DraftError("The dish needs a name.")
        self.dish_name = dish_label(name.strip())

    # ── State ──

    def view(self) -> dict:
        """The entry as the model sees it after each operation."""
        first = (self.rows or self.original)[0]
        rows = []
        for row in self.rows:
            grams = row_grams(row)
            per_100g = alternative(row)["per_100g"]
            current = self._food_key(row)
            others = [
                self._links[(row["id"], a["key"])]
                for a in row["alternatives"]
                if self._links[(row["id"], a["key"])] != current
            ]
            rows.append(
                {
                    "row": row["id"],
                    "food": current,
                    "name": alternative(row)["name"],
                    "amount": amount_label(row),
                    "grams": round(grams, 1),
                    "weight_state": row["item_state"],
                    "kcal": round(per_100g["calories_kcal"] * grams / 100),
                    "user_said": row.get("said") or None,
                    "other_matches": others,
                }
            )
        return {
            "dish": self.dish_name if len(self.rows) > 1 else None,
            "meal_type": first["meal_type"],
            "time": first["log_for"][-5:],
            "rows": rows,
        }

    def changed(self) -> bool:
        return self.rows != self.original or (
            len(self.rows) > 1 and self.dish_name != self.original[0].get("dish")
        )

    def result(self) -> list[dict]:
        """The edited rows, grouped as one dish when there are several."""
        rows = copy.deepcopy(self.rows)
        if len(rows) > 1:
            dish_id = next((r["dish_id"] for r in rows if r.get("dish_id")), "d0")
            name = self.dish_name or dish_label(
                " and ".join(alternative(r)["name"] for r in rows)
            )
            for row in rows:
                row.update(dish_id=dish_id, dish=name)
        elif rows:
            rows[0]["dish_id"] = None
            if alternative(rows[0])["kind"] != "recipe":
                rows[0]["dish"] = None
        return rows


def replace_dish(rows: list[dict], key: str, new_rows: list[dict]) -> list[dict]:
    """Put `new_rows` where the `key` group was, dropping its old rows.

    `new_rows` may carry ids of their own (from the editor, or a pipeline
    run); both are remapped so they can't collide with the rows that stay."""
    indices = [n for n, r in enumerate(rows) if group_key(r) == key]
    if not indices:
        raise DraftError(f"Unknown dish '{key}'.")
    kept = [r for n, r in enumerate(rows) if n not in indices]
    next_row = max((int(r["id"][1:]) for r in rows), default=-1) + 1

    # Remap the new rows' dish ids, keeping each distinct dish together and
    # clear of the ids the surviving rows still use.
    used = {r["dish_id"] for r in kept if r.get("dish_id")}
    next_dish = max((int(d[1:]) for d in used), default=-1) + 1
    dish_ids: dict[str, str] = {}
    for row in new_rows:
        old = row.get("dish_id")
        if old and old not in dish_ids:
            dish_ids[old] = f"d{next_dish}"
            next_dish += 1
    renamed = [
        {
            **row,
            "id": f"r{next_row + n}",
            "dish_id": dish_ids.get(row.get("dish_id") or "", row.get("dish_id")),
        }
        for n, row in enumerate(new_rows)
    ]

    # Rebuild in order: the new rows take the first slot of the old group.
    result: list[dict] = []
    inserted = False
    for n, row in enumerate(rows):
        if n in indices:
            if not inserted:
                result.extend(renamed)
                inserted = True
            continue
        result.append(row)
    return result


def log_entry(
    row: dict, dish_id: str | None = None, dish_name: str | None = None
) -> dict:
    """The `log_entries` entry for a row whose target exists (or was created).

    `dish_id`/`dish_name` group a component dish's rows in the log; recipes
    are grouped by their own `recipe_id` instead.
    """
    target = alternative(row)
    base = {"meal_type": row["meal_type"], "log_for": row["log_for"]}
    if target["kind"] == "recipe":
        return {**base, "recipe_id": target["id"], "quantity": row["quantity"], "unit": row["unit"]}
    # A "new" target has an id once its ingredient was created on confirm.
    entry = {**base, "food_id": target["id"], "quantity": row["quantity"], "unit": row["unit"]}
    if row["unit"] == "serving":
        entry["serving_size_id"] = row["serving_size_id"]
    if dish_id:
        entry["dish_id"] = dish_id
        entry["dish_name"] = dish_name
    return entry
