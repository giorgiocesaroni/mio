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


log_ingredient_declaration = models.FunctionDeclaration(
    name="log_ingredient",
    description="Logs an ingredient. Specify quantity and unit: unit='grams' logs a weight in grams, unit='serving' logs a number of servings (requires serving_size_id).",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "food_id": {
                "type": "string",
                "format": "uuid",
                "description": "ID of the ingredient being logged.",
            },
            "quantity": {
                "type": "number",
                "description": "Amount consumed. Interpretation depends on unit.",
            },
            "unit": {
                "type": "string",
                "enum": ["grams", "serving"],
                "description": "'grams' means quantity is the weight in grams. 'serving' means quantity is the number of servings (requires serving_size_id).",
            },
            "serving_size_id": {
                "type": "string",
                "format": "uuid",
                "description": "ID of the serving size. Required when unit='serving'.",
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
    },
)


def log_ingredient_tool(
    user_id: str,
    food_id: str,
    quantity: float,
    unit: str,
    meal_type: str,
    log_for: str,
    serving_size_id: str | None = None,
) -> dict:
    fid = UUID(food_id)
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
        if not serving_size_id:
            raise ValueError("serving_size_id is required when unit='serving'.")
        repository.insert_log_by_serving_size(
            models.InsertLogByServingSizeInput(
                food_id=fid,
                serving_size_id=UUID(serving_size_id),
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

log_recipe_declaration = models.FunctionDeclaration(
    name="log_recipe",
    description="Logs consumption of a recipe. Specify quantity and unit: unit='recipe' logs a proportion of the whole recipe (e.g. quantity=0.5 for half), unit='grams' logs an absolute weight in grams. The system expands the recipe into per-ingredient logs, scaled proportionally.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "recipe_id": {
                "type": "string",
                "format": "uuid",
                "description": "ID of the recipe being logged.",
            },
            "quantity": {
                "type": "number",
                "description": "Amount consumed. Interpretation depends on unit.",
            },
            "unit": {
                "type": "string",
                "enum": ["recipe", "grams"],
                "description": "'recipe' means quantity is a proportion of the whole recipe (1 = entire recipe, 0.5 = half). 'grams' means quantity is the absolute weight in grams of the recipe consumed.",
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


update_log_declaration = models.FunctionDeclaration(
    name="update_log",
    description="Updates an existing log entry. Only provided fields are changed.",
    parameters_json_schema={
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
            "recipe_id": {
                "type": "string",
                "format": "uuid",
                "description": "New recipe ID.",
            },
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