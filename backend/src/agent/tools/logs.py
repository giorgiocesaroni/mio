"""Food logging tools."""

from uuid import UUID

import src.agent.models as models
import src.agent.repository as repository

get_daily_summary_declaration = models.FunctionDeclaration(
    name="get_daily_summary",
    description="Returns log entries for a given day with calculated macros per entry, the total macros and calories consumed, and the latest weight measurement.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "day": {
                "type": "string",
                "description": "The date in YYYY-MM-DD format.",
            }
        },
        "required": ["day"],
    },
)


def get_daily_summary_tool(user_id: str, day: str) -> dict:
    logs = repository.get_logs_by_day(day, user_id)
    daily_macros = repository.get_daily_macros(day, user_id)
    latest_measurement = repository.get_latest_measurement(user_id)
    return {
        "logs": [log.model_dump() for log in logs],
        "daily_macros": daily_macros,
        "latest_measurement": (
            latest_measurement.model_dump(mode="json") if latest_measurement else None
        ),
    }


_LOG_INGREDIENT_GRAMS = {
    "type": "object",
    "properties": {
        "food_id": {
            "type": "string",
            "format": "uuid",
            "description": "ID of the ingredient being logged.",
        },
        "quantity": {
            "type": "number",
            "description": "Quantity consumed in grams.",
        },
        "unit": {
            "type": "string",
            "const": "grams",
        },
        "meal_type": {
            "type": "string",
            "enum": ["breakfast", "lunch", "dinner", "snack"],
            "description": "The meal type.",
        },
        "log_for": {
            "type": "string",
            "description": "The actual time of the meal, in YYYY-MM-DD HH:MM format.",
        },
    },
    "required": ["food_id", "quantity", "unit", "meal_type", "log_for"],
}

_LOG_INGREDIENT_SERVING = {
    "type": "object",
    "properties": {
        "food_id": {
            "type": "string",
            "format": "uuid",
            "description": "ID of the ingredient being logged.",
        },
        "quantity": {
            "type": "number",
            "description": "Number of servings consumed.",
        },
        "unit": {
            "type": "string",
            "const": "serving",
        },
        "serving_size_id": {
            "type": "string",
            "format": "uuid",
            "description": "ID of the serving size.",
        },
        "meal_type": {
            "type": "string",
            "enum": ["breakfast", "lunch", "dinner", "snack"],
            "description": "The meal type.",
        },
        "log_for": {
            "type": "string",
            "description": "The actual time of the meal, in YYYY-MM-DD HH:MM format.",
        },
    },
    "required": ["food_id", "quantity", "unit", "serving_size_id", "meal_type", "log_for"],
}

# ── Entry schemas (assembled into `log_entries`) ──────────────────────────────

_LOG_RECIPE_PROPORTION = {
    "type": "object",
    "properties": {
        "recipe_id": {
            "type": "string",
            "format": "uuid",
            "description": "ID of the recipe being logged.",
        },
        "quantity": {
            "type": "number",
            "description": "Proportion of the recipe consumed (1 = entire recipe, 0.5 = half).",
        },
        "unit": {
            "type": "string",
            "const": "recipe",
        },
        "meal_type": {
            "type": "string",
            "enum": ["breakfast", "lunch", "dinner", "snack"],
            "description": "The meal type.",
        },
        "log_for": {
            "type": "string",
            "description": "The actual time of the meal, in YYYY-MM-DD HH:MM format.",
        },
    },
    "required": ["recipe_id", "quantity", "unit", "meal_type", "log_for"],
}

_LOG_RECIPE_GRAMS = {
    "type": "object",
    "properties": {
        "recipe_id": {
            "type": "string",
            "format": "uuid",
            "description": "ID of the recipe being logged.",
        },
        "quantity": {
            "type": "number",
            "description": "Weight of the recipe consumed in grams.",
        },
        "unit": {
            "type": "string",
            "const": "grams",
        },
        "meal_type": {
            "type": "string",
            "enum": ["breakfast", "lunch", "dinner", "snack"],
            "description": "The meal type.",
        },
        "log_for": {
            "type": "string",
            "description": "The actual time of the meal, in YYYY-MM-DD HH:MM format.",
        },
    },
    "required": ["recipe_id", "quantity", "unit", "meal_type", "log_for"],
}

# ── Batch logging ─────────────────────────────────────────────────────────────


def _updated_totals(user_id: str, days: set[str]) -> dict:
    """Recalculated daily macros for every day a mutation touched."""
    totals = {}
    for day in sorted(days):
        try:
            totals[day] = repository.get_daily_macros(day, user_id)
        except Exception as e:
            totals[day] = {"error": str(e)}
    return totals


def _apply_log_entry(user_id: str, entry: dict) -> str:
    """Apply a single `log_entries` item and return the local day it hit.

    An item is either an ingredient (``food_id``) or a recipe (``recipe_id``);
    ``unit`` then picks the measurement path.
    """
    unit = entry.get("unit")
    quantity = float(entry["quantity"])
    meal_type = entry["meal_type"]
    log_for = entry["log_for"]
    if entry.get("recipe_id"):
        recipe_id = UUID(entry["recipe_id"])
        if unit == "recipe":
            repository.log_recipe_by_proportion(
                recipe_id, quantity, meal_type, log_for, user_id
            )
        elif unit == "grams":
            repository.insert_log_by_grams(
                models.InsertLogByGramsInput(
                    food_id=None,
                    quantity_g=quantity,
                    recipe_id=recipe_id,
                    meal_type=meal_type,  # type: ignore
                    log_for=log_for,
                ),
                user_id,
            )
        else:
            raise ValueError(f"Invalid unit: {unit}. Must be 'recipe' or 'grams'.")
    else:
        if not entry.get("food_id"):
            raise ValueError(
                "Entry needs a food_id (ingredient) or a recipe_id (recipe)."
            )
        food_id = UUID(entry["food_id"])
        if unit == "grams":
            repository.insert_log_by_grams(
                models.InsertLogByGramsInput(
                    food_id=food_id,
                    quantity_g=quantity,
                    recipe_id=None,
                    meal_type=meal_type,  # type: ignore
                    log_for=log_for,
                ),
                user_id,
            )
        elif unit == "serving":
            if not entry.get("serving_size_id"):
                raise ValueError("unit='serving' requires a serving_size_id.")
            repository.insert_log_by_serving_size(
                models.InsertLogByServingSizeInput(
                    food_id=food_id,
                    serving_size_id=UUID(entry["serving_size_id"]),
                    quantity=quantity,
                    meal_type=meal_type,  # type: ignore
                    log_for=log_for,
                ),
                user_id,
            )
        else:
            raise ValueError(f"Invalid unit: {unit}. Must be 'grams' or 'serving'.")
    return log_for[:10]


log_entries_declaration = models.FunctionDeclaration(
    name="log_entries",
    description=(
        "Logs one or more foods (ingredients or recipes) in a single call. "
        "Returns a per-entry result plus the recalculated daily totals for "
        "every day touched, so no separate summary call is needed afterwards."
    ),
    parameters_json_schema={
        "type": "object",
        "properties": {
            "entries": {
                "type": "array",
                "description": "The foods to log, in one batch.",
                "items": {
                    "anyOf": [
                        _LOG_INGREDIENT_GRAMS,
                        _LOG_INGREDIENT_SERVING,
                        _LOG_RECIPE_PROPORTION,
                        _LOG_RECIPE_GRAMS,
                    ],
                },
            },
        },
        "required": ["entries"],
    },
)


def log_entries_tool(user_id: str, entries: list[dict]) -> dict:
    results = []
    days: set[str] = set()
    for index, entry in enumerate(entries):
        try:
            days.add(_apply_log_entry(user_id, entry))
            results.append({"index": index, "success": True})
        except Exception as e:
            results.append({"index": index, "success": False, "error": str(e)})
    return {"results": results, "updated_totals": _updated_totals(user_id, days)}


_UPDATE_LOG_INGREDIENT = {
    "type": "object",
    "properties": {
        "id": {
            "type": "string",
            "format": "uuid",
            "description": "UUID of the log entry to update.",
        },
        "food_id": {
            "type": "string",
            "format": "uuid",
            "description": "New ingredient ID.",
        },
        "quantity_g": {"type": "number", "description": "New quantity in grams."},
        "meal_type": {
            "type": "string",
            "enum": ["breakfast", "lunch", "dinner", "snack"],
            "description": "New meal type.",
        },
        "log_for": {
            "type": "string",
            "description": "New actual time of the meal, in YYYY-MM-DD HH:MM format.",
        },
    },
    "required": ["id"],
}

_UPDATE_LOG_RECIPE = {
    "type": "object",
    "properties": {
        "id": {
            "type": "string",
            "format": "uuid",
            "description": "UUID of the log entry to update.",
        },
        "recipe_id": {
            "type": "string",
            "format": "uuid",
            "description": "New recipe ID.",
        },
        "quantity_g": {"type": "number", "description": "New quantity in grams."},
        "meal_type": {
            "type": "string",
            "enum": ["breakfast", "lunch", "dinner", "snack"],
            "description": "New meal type.",
        },
        "log_for": {
            "type": "string",
            "description": "New actual time of the meal, in YYYY-MM-DD HH:MM format.",
        },
    },
    "required": ["id"],
}

update_logs_declaration = models.FunctionDeclaration(
    name="update_logs",
    description=(
        "Updates one or more existing log entries in a single call. Provide "
        "food_id to update an ingredient log, or recipe_id to update a recipe "
        "log. Only provided fields are changed. Returns a per-entry result "
        "plus the recalculated daily totals for every day touched."
    ),
    parameters_json_schema={
        "type": "object",
        "properties": {
            "updates": {
                "type": "array",
                "description": "The log updates to apply, in one batch.",
                "items": {
                    "anyOf": [_UPDATE_LOG_INGREDIENT, _UPDATE_LOG_RECIPE],
                },
            },
        },
        "required": ["updates"],
    },
)


def update_logs_tool(user_id: str, updates: list[dict]) -> dict:
    ids: list[UUID] = []
    for update in updates:
        try:
            ids.append(UUID(str(update["id"])))
        except Exception:
            continue
    days: set[str] = set(repository.get_log_days(ids, user_id))
    results = []
    for index, update in enumerate(updates):
        try:
            kwargs = dict(update)
            kwargs["id"] = UUID(str(kwargs["id"]))
            repository.update_log(models.UpdateLogInput(**kwargs), user_id)  # type: ignore
            if update.get("log_for"):
                days.add(str(update["log_for"])[:10])
            results.append({"index": index, "success": True})
        except Exception as e:
            results.append({"index": index, "success": False, "error": str(e)})
    return {"results": results, "updated_totals": _updated_totals(user_id, days)}


delete_logs_declaration = models.FunctionDeclaration(
    name="delete_logs",
    description=(
        "Deletes one or more log entries in a single call. Returns a per-entry "
        "result plus the recalculated daily totals for every day touched."
    ),
    parameters_json_schema={
        "type": "object",
        "properties": {
            "log_ids": {
                "type": "array",
                "items": {"type": "string", "format": "uuid"},
                "description": "UUIDs of the log entries to delete.",
            },
        },
        "required": ["log_ids"],
    },
)


def delete_logs_tool(user_id: str, log_ids: list[str]) -> dict:
    parsed: list[tuple[str, UUID]] = []
    results = []
    for raw in log_ids:
        try:
            parsed.append((raw, UUID(str(raw))))
        except Exception:
            results.append(
                {"log_id": raw, "success": False, "error": "Invalid log id."}
            )
    days: set[str] = set(
        repository.get_log_days([uid for _, uid in parsed], user_id)
    )
    for raw, uid in parsed:
        try:
            repository.delete_log(uid, user_id)
            results.append({"log_id": raw, "success": True})
        except Exception as e:
            results.append({"log_id": raw, "success": False, "error": str(e)})
    return {"results": results, "updated_totals": _updated_totals(user_id, days)}