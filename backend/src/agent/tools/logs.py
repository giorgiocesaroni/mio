"""Food logging tools."""

from typing import Optional
from uuid import UUID

import src.agent.models as models
import src.agent.repository as repository

get_daily_summary_declaration = models.FunctionDeclaration(
    name="get_daily_summary",
    description="Returns log entries for a given day, the total macros and calories consumed, the latest weight measurement, and the current goal.",
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
    current_goal = repository.get_current_goal(user_id)
    return {
        "logs": [log.model_dump() for log in logs],
        "daily_macros": daily_macros,
        "latest_measurement": (
            latest_measurement.model_dump(mode="json") if latest_measurement else None
        ),
        "current_goal": current_goal.model_dump(mode="json") if current_goal else None,
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

log_ingredient_declaration = models.FunctionDeclaration(
    name="log_ingredient",
    description="Logs an ingredient. Use unit='grams' for weight, or unit='serving' with a serving_size_id for servings.",
    parameters_json_schema={
        "anyOf": [_LOG_INGREDIENT_GRAMS, _LOG_INGREDIENT_SERVING],
    },
)


def log_ingredient_tool(
    user_id: str,
    quantity: float,
    unit: str,
    meal_type: str,
    log_for: str,
    food_id: str | None = None,
    serving_size_id: str | None = None,
) -> dict:
    fid = UUID(food_id) if food_id else None
    if unit == "grams":
        repository.insert_log_by_grams(
            models.InsertLogByGramsInput(
                food_id=fid,
                quantity_g=quantity,
                recipe_id=None,
                meal_type=meal_type,  # type: ignore
                log_for=log_for,
            ),
            user_id,
        )
    elif unit == "serving":
        repository.insert_log_by_serving_size(
            models.InsertLogByServingSizeInput(
                food_id=fid,
                serving_size_id=UUID(serving_size_id) if serving_size_id else None,
                quantity=quantity,
                meal_type=meal_type,  # type: ignore
                log_for=log_for,
            ),
            user_id,
        )
    else:
        raise ValueError(f"Invalid unit: {unit}. Must be 'grams' or 'serving'.")
    return {"success": True}


# ── Recipe logging ────────────────────────────────────────────────────────────

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

log_recipe_declaration = models.FunctionDeclaration(
    name="log_recipe",
    description="Logs a recipe. Use unit='recipe' for a proportion (e.g. quantity=0.5 for half), or unit='grams' for absolute weight. The system expands it into per-ingredient logs.",
    parameters_json_schema={
        "anyOf": [_LOG_RECIPE_PROPORTION, _LOG_RECIPE_GRAMS],
    },
)


def log_recipe_tool(
    user_id: str,
    recipe_id: str,
    quantity: float,
    unit: str,
    meal_type: str,
    log_for: str,
) -> dict:
    rid = UUID(recipe_id)
    if unit == "recipe":
        repository.log_recipe_by_proportion(
            rid, quantity, meal_type, log_for, user_id
        )
    elif unit == "grams":
        repository.insert_log_by_grams(
            models.InsertLogByGramsInput(
                food_id=None,
                quantity_g=quantity,
                recipe_id=rid,
                meal_type=meal_type,  # type: ignore
                log_for=log_for,
            ),
            user_id,
        )
    else:
        raise ValueError(f"Invalid unit: {unit}. Must be 'recipe' or 'grams'.")
    return {"success": True}


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

update_log_declaration = models.FunctionDeclaration(
    name="update_log",
    description="Updates an existing log entry. Provide food_id to update an ingredient log, or recipe_id to update a recipe log. Only provided fields are changed.",
    parameters_json_schema={
        "anyOf": [_UPDATE_LOG_INGREDIENT, _UPDATE_LOG_RECIPE],
    },
)


def update_log_tool(
    user_id: str,
    id: UUID,
    food_id: Optional[UUID] = None,
    quantity_g: float | None = None,
    recipe_id: Optional[UUID] = None,
    meal_type: str | None = None,
    log_for: str | None = None,
) -> None:
    repository.update_log(
        models.UpdateLogInput(
            id=id, food_id=food_id, quantity_g=quantity_g, recipe_id=recipe_id, meal_type=meal_type, log_for=log_for,  # type: ignore
        ),
        user_id,
    )


delete_log_declaration = models.FunctionDeclaration(
    name="delete_log",
    description="Deletes a log entry by its ID.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "log_id": {
                "type": "string",
                "format": "uuid",
                "description": "UUID of the log entry to delete.",
            }
        },
        "required": ["log_id"],
    },
)


def delete_log_tool(user_id: str, log_id: UUID) -> None:
    repository.delete_log(log_id, user_id)