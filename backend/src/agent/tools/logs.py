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


_LOG_BY_GRAMS_INGREDIENT = {
    "type": "object",
    "properties": {
        "food_id": {
            "type": "string",
            "format": "uuid",
            "description": "ID of the ingredient being logged.",
        },
        "quantity_g": {
            "type": "number",
            "description": "Quantity consumed in grams.",
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
    "required": ["food_id", "quantity_g", "meal_type", "log_for"],
}

_LOG_BY_GRAMS_RECIPE = {
    "type": "object",
    "properties": {
        "recipe_id": {
            "type": "string",
            "format": "uuid",
            "description": "ID of the recipe being logged.",
        },
        "quantity_g": {
            "type": "number",
            "description": "Amount of the whole recipe consumed, in grams. The system scales the recipe's ingredients proportionally.",
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
    "required": ["recipe_id", "quantity_g", "meal_type", "log_for"],
}

insert_log_by_grams_declaration = models.FunctionDeclaration(
    name="insert_log_by_grams",
    description="Logs food by specifying the quantity in grams. Provide either food_id (a single ingredient) or recipe_id (a recipe). When recipe_id is given, quantity_g is the total weight of the recipe consumed and the system expands it into the recipe's individual ingredients.",
    parameters_json_schema={
        "anyOf": [_LOG_BY_GRAMS_INGREDIENT, _LOG_BY_GRAMS_RECIPE],
    },
)


def insert_log_by_grams_tool(
    user_id: str, quantity_g: float, meal_type: str, log_for: str, food_id: str | None = None, recipe_id: str | None = None,
) -> dict:
    fid = UUID(food_id) if food_id else None
    rid = UUID(recipe_id) if recipe_id else None
    repository.insert_log_by_grams(
        models.InsertLogByGramsInput(
            food_id=fid, quantity_g=quantity_g, recipe_id=rid, meal_type=meal_type, log_for=log_for,  # type: ignore
        ),
        user_id,
    )
    return {"success": True}


_LOG_BY_SERVING_INGREDIENT = {
    "type": "object",
    "properties": {
        "food_id": {
            "type": "string",
            "format": "uuid",
            "description": "ID of the ingredient being logged.",
        },
        "serving_size_id": {
            "type": "string",
            "format": "uuid",
            "description": "ID of the serving size used.",
        },
        "quantity": {
            "type": "number",
            "description": "Number of servings consumed.",
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
    "required": ["food_id", "serving_size_id", "quantity", "meal_type", "log_for"],
}

insert_log_by_serving_size_declaration = models.FunctionDeclaration(
    name="insert_log_by_serving_size",
    description="Logs an ingredient by specifying a serving size and the number of servings consumed.",
    parameters_json_schema={
        "anyOf": [_LOG_BY_SERVING_INGREDIENT],
    },
)


def insert_log_by_serving_size_tool(
    user_id: str,
    quantity: float,
    meal_type: str,
    log_for: str,
    food_id: str | None = None,
    serving_size_id: str | None = None,
) -> dict:
    fid = UUID(food_id) if food_id else None
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