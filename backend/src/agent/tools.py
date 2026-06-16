from typing import Optional
from uuid import UUID

import src.agent.models as models
import src.agent.repository as repository
from tinyfish import TinyFish

search_declaration = models.FunctionDeclaration(
    name="search",
    description="Searches the web for a given query and returns relevant results.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query.",
            }
        },
        "required": ["query"],
    },
)


def search_tool(query: str) -> list[dict]:
    client = TinyFish()
    response = client.search.query(query=query, location="IT")
    return [r.model_dump() for r in response.results]


fetch_declaration = models.FunctionDeclaration(
    name="fetch",
    description="Fetches the content of a list of URLs.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "The URLs to fetch.",
            },
        },
        "required": ["urls"],
    },
)


def fetch_tool(urls: list[str]) -> list[dict]:
    client = TinyFish()
    response = client.fetch.get_contents(urls=urls)
    return [r.model_dump() for r in response.results]


search_foods_declaration = models.FunctionDeclaration(
    name="search_foods",
    description="Semantically searches for foods by name. Use this to find foods when the user describes a food, instead of loading the entire list.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The food name or description to search for.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results (default 10).",
            },
        },
        "required": ["query"],
    },
)


def search_foods_tool(user_id: str, query: str, limit: int = 10) -> list[dict]:
    foods = repository.search_foods(query, limit, user_id)
    return [f.model_dump() for f in foods]


# Foods

get_all_foods_declaration = models.FunctionDeclaration(
    name="get_all_foods",
    description="Returns the list of all foods in the database.",
    parameters_json_schema={
        "type": "object",
        "properties": {},
        "required": [],
    },
)


def get_all_foods_tool(user_id: str) -> list[dict]:
    foods = repository.get_all_foods(user_id)
    return [f.model_dump() for f in foods]


get_food_by_id_declaration = models.FunctionDeclaration(
    name="get_food_by_id",
    description="Returns a single food record by its ID.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "food_id": {
                "type": "string",
                "format": "uuid",
                "description": "The UUID of the food.",
            }
        },
        "required": ["food_id"],
    },
)


def get_food_by_id_tool(user_id: str, food_id: UUID) -> dict | None:
    food = repository.get_food_by_id(food_id, user_id)
    return food.model_dump() if food else None


insert_food_declaration = models.FunctionDeclaration(
    name="insert_food",
    description="Inserts a new food into the database.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Name of the food."},
            "protein_g": {
                "type": "integer",
                "description": "Protein content in grams.",
            },
            "carbs_g": {
                "type": "integer",
                "description": "Carbohydrate content in grams.",
            },
            "fat_g": {"type": "integer", "description": "Fat content in grams."},
            "calories_kcal": {
                "type": "integer",
                "description": "Caloric value in kcal.",
            },
            "serving_sizes": {
                "type": "array",
                "description": "Optional list of serving sizes for this food.",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {
                            "type": "string",
                            "description": "Human-readable label (e.g. '1 cup', '1 slice').",
                        },
                        "grams": {
                            "type": "number",
                            "description": "Weight of this serving in grams.",
                        },
                    },
                    "required": ["label", "grams"],
                },
            },
        },
        "required": ["name", "protein_g", "carbs_g", "fat_g", "calories_kcal"],
    },
)


def insert_food_tool(
    user_id: str,
    name: str,
    protein_g: int,
    carbs_g: int,
    fat_g: int,
    calories_kcal: int,
    serving_sizes: list[dict] | None = None,
) -> dict:
    food = repository.insert_food(
        models.InsertFoodInput(
            name=name,
            protein_g=protein_g,
            carbs_g=carbs_g,
            fat_g=fat_g,
            calories_kcal=calories_kcal,
            serving_sizes=[
                models.InsertServingSizeInput(**ss) for ss in (serving_sizes or [])
            ],
        ),
        user_id,
    )
    return food.model_dump()


update_food_declaration = models.FunctionDeclaration(
    name="update_food",
    description="Updates an existing food record. Only provided fields are changed.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "id": {
                "type": "string",
                "format": "uuid",
                "description": "UUID of the food to update.",
            },
            "name": {"type": "string", "description": "New name."},
            "protein_g": {"type": "integer", "description": "New protein in grams."},
            "carbs_g": {"type": "integer", "description": "New carbs in grams."},
            "fat_g": {"type": "integer", "description": "New fat in grams."},
            "calories_kcal": {
                "type": "integer",
                "description": "New calories in kcal.",
            },
        },
        "required": ["id"],
    },
)


def update_food_tool(
    user_id: str,
    id: UUID,
    name: str | None = None,
    protein_g: int | None = None,
    carbs_g: int | None = None,
    fat_g: int | None = None,
    calories_kcal: int | None = None,
) -> None:
    repository.update_food(
        models.UpdateFoodInput(
            id=id,
            name=name,
            protein_g=protein_g,
            carbs_g=carbs_g,
            fat_g=fat_g,
            calories_kcal=calories_kcal,
        ),
        user_id,
    )


delete_food_declaration = models.FunctionDeclaration(
    name="delete_food",
    description="Deletes a food record by its ID.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "food_id": {
                "type": "string",
                "format": "uuid",
                "description": "UUID of the food to delete.",
            }
        },
        "required": ["food_id"],
    },
)


def delete_food_tool(user_id: str, food_id: UUID) -> None:
    repository.delete_food(food_id, user_id)


# Serving Sizes

get_serving_sizes_by_food_id_declaration = models.FunctionDeclaration(
    name="get_serving_sizes_by_food_id",
    description="Returns all serving sizes for a given food.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "food_id": {
                "type": "string",
                "format": "uuid",
                "description": "UUID of the food.",
            }
        },
        "required": ["food_id"],
    },
)


def get_serving_sizes_by_food_id_tool(user_id: str, food_id: UUID) -> list[dict]:
    sizes = repository.get_serving_sizes_by_food_id(food_id, user_id)
    return [s.model_dump() for s in sizes]


insert_serving_size_declaration = models.FunctionDeclaration(
    name="insert_serving_size",
    description="Adds a new serving size to an existing food.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "food_id": {
                "type": "string",
                "format": "uuid",
                "description": "UUID of the food to attach the serving size to.",
            },
            "label": {
                "type": "string",
                "description": "Human-readable label (e.g. '1 cup', '1 slice').",
            },
            "grams": {
                "type": "number",
                "description": "Weight of this serving in grams.",
            },
        },
        "required": ["food_id", "label", "grams"],
    },
)


def insert_serving_size_tool(
    user_id: str, food_id: UUID, label: str, grams: float
) -> dict:
    size = repository.insert_serving_size(
        food_id,
        models.InsertServingSizeInput(label=label, grams=grams),
        user_id,
    )
    return size.model_dump()


update_serving_size_declaration = models.FunctionDeclaration(
    name="update_serving_size",
    description="Updates an existing serving size. Only provided fields are changed.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "id": {
                "type": "string",
                "format": "uuid",
                "description": "UUID of the serving size to update.",
            },
            "label": {"type": "string", "description": "New label."},
            "grams": {"type": "number", "description": "New weight in grams."},
        },
        "required": ["id"],
    },
)


def update_serving_size_tool(
    user_id: str, id: UUID, label: str | None = None, grams: float | None = None
) -> dict:
    size = repository.update_serving_size(
        models.UpdateServingSizeInput(id=id, label=label, grams=grams),
        user_id,
    )
    return size.model_dump()


delete_serving_size_declaration = models.FunctionDeclaration(
    name="delete_serving_size",
    description="Deletes a serving size by its ID.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "serving_size_id": {
                "type": "string",
                "format": "uuid",
                "description": "UUID of the serving size to delete.",
            }
        },
        "required": ["serving_size_id"],
    },
)


def delete_serving_size_tool(user_id: str, serving_size_id: UUID) -> None:
    repository.delete_serving_size(serving_size_id, user_id)


# Food Logs

get_daily_summary_declaration = models.FunctionDeclaration(
    name="get_daily_summary",
    description="Returns food log entries for a given day, the total macros and calories consumed, the latest weight measurement, and the current goal.",
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
    logs = repository.get_food_logs_by_day(day, user_id)
    daily_macros = repository.get_daily_macros(day, user_id)
    latest_measurement = repository.get_latest_measurement(user_id)
    current_goal = repository.get_current_goal(user_id)
    return {
        "logs": [log.model_dump() for log in logs],
        "daily_macros": daily_macros,
        "latest_measurement": (
            latest_measurement.model_dump() if latest_measurement else None
        ),
        "current_goal": current_goal.model_dump() if current_goal else None,
    }


insert_food_log_by_grams_declaration = models.FunctionDeclaration(
    name="insert_food_log_by_grams",
    description="Logs a food entry by specifying the quantity in grams. Defaults to now if no time is provided.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "food_id": {
                "type": "string",
                "format": "uuid",
                "description": "ID of the food being logged.",
            },
            "quantity_g": {
                "type": "number",
                "description": "Quantity consumed in grams.",
            },
            "logged_at": {
                "type": "string",
                "description": "The date and time of the log entry, in YYYY-MM-DD HH:MM format. Defaults to now.",
            },
        },
        "required": ["food_id", "quantity_g"],
    },
)


def insert_food_log_by_grams_tool(
    user_id: str, food_id: UUID, quantity_g: float, logged_at: str | None = None
) -> None:
    repository.insert_food_log_by_grams(
        models.InsertFoodLogByGramsInput(
            food_id=food_id, quantity_g=quantity_g, logged_at=logged_at
        ),
        user_id,
    )


insert_food_log_by_serving_size_declaration = models.FunctionDeclaration(
    name="insert_food_log_by_serving_size",
    description="Logs a food entry by specifying a serving size and the number of servings consumed. Defaults to now if no time is provided.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "food_id": {
                "type": "string",
                "format": "uuid",
                "description": "ID of the food being logged.",
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
            "logged_at": {
                "type": "string",
                "description": "The date and time of the log entry, in YYYY-MM-DD HH:MM format. Defaults to now.",
            },
        },
        "required": ["food_id", "serving_size_id", "quantity"],
    },
)


def insert_food_log_by_serving_size_tool(
    user_id: str,
    food_id: UUID,
    serving_size_id: UUID,
    quantity: float,
    logged_at: str | None = None,
) -> None:
    repository.insert_food_log_by_serving_size(
        models.InsertFoodLogByServingSizeInput(
            food_id=food_id,
            serving_size_id=serving_size_id,
            quantity=quantity,
            logged_at=logged_at,
        ),
        user_id,
    )


update_food_log_declaration = models.FunctionDeclaration(
    name="update_food_log",
    description="Updates an existing food log entry. Only provided fields are changed.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "id": {
                "type": "string",
                "format": "uuid",
                "description": "UUID of the food log entry to update.",
            },
            "food_id": {
                "type": "string",
                "format": "uuid",
                "description": "New food ID.",
            },
            "quantity_g": {"type": "integer", "description": "New quantity in grams."},
            "logged_at": {
                "type": "string",
                "description": "New date and time for the log entry, in YYYY-MM-DD HH:MM format.",
            },
        },
        "required": ["id"],
    },
)


def update_food_log_tool(
    user_id: str,
    id: UUID,
    food_id: Optional[UUID] = None,
    quantity_g: int | None = None,
    logged_at: str | None = None,
) -> None:
    repository.update_food_log(
        models.UpdateFoodLogInput(
            id=id, food_id=food_id, quantity_g=quantity_g, logged_at=logged_at
        ),
        user_id,
    )


delete_food_log_declaration = models.FunctionDeclaration(
    name="delete_food_log",
    description="Deletes a food log entry by its ID.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "food_log_id": {
                "type": "string",
                "format": "uuid",
                "description": "UUID of the food log entry to delete.",
            }
        },
        "required": ["food_log_id"],
    },
)


def delete_food_log_tool(user_id: str, food_log_id: UUID) -> None:
    repository.delete_food_log(food_log_id, user_id)


# Goals

get_current_goal_declaration = models.FunctionDeclaration(
    name="get_current_goal",
    description="Returns the most recently set nutrition and weight goal.",
    parameters_json_schema={
        "type": "object",
        "properties": {},
        "required": [],
    },
)


def get_current_goal_tool(user_id: str) -> dict | None:
    goal = repository.get_current_goal(user_id)
    return goal.model_dump() if goal else None


insert_goal_declaration = models.FunctionDeclaration(
    name="insert_goal",
    description="Creates a new nutrition and weight goal, becoming the current active goal.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "weight_kg": {
                "type": "integer",
                "description": "Target body weight in kg.",
            },
            "calories_kcal": {
                "type": "integer",
                "description": "Daily calorie target in kcal.",
            },
            "protein_g": {
                "type": "integer",
                "description": "Daily protein target in grams.",
            },
            "carbs_g": {
                "type": "integer",
                "description": "Daily carbohydrate target in grams.",
            },
            "fat_g": {"type": "integer", "description": "Daily fat target in grams."},
            "goal": {
                "type": "string",
                "enum": ["lose_weight", "maintain_weight", "gain_weight"],
                "description": "The overall weight goal direction.",
            },
        },
        "required": [
            "weight_kg",
            "calories_kcal",
            "protein_g",
            "carbs_g",
            "fat_g",
            "goal",
        ],
    },
)


def insert_goal_tool(
    user_id: str,
    weight_kg: int,
    calories_kcal: int,
    protein_g: int,
    carbs_g: int,
    fat_g: int,
    goal: str,
) -> None:
    repository.insert_goal(
        models.InsertGoalInput(
            weight_kg=weight_kg,
            calories_kcal=calories_kcal,
            protein_g=protein_g,
            carbs_g=carbs_g,
            fat_g=fat_g,
            goal=goal,  # type: ignore
        ),
        user_id,
    )


# Measurements

get_latest_measurements_declaration = models.FunctionDeclaration(
    name="get_latest_measurements",
    description="Returns the most recent weight measurement.",
    parameters_json_schema={
        "type": "object",
        "properties": {},
        "required": [],
    },
)


def get_latest_measurements_tool(user_id: str) -> dict | None:
    measurement = repository.get_latest_measurement(user_id)
    return measurement.model_dump() if measurement else None


insert_measurement_declaration = models.FunctionDeclaration(
    name="insert_measurement",
    description="Records a weight measurement. Use this when the user reports their weight.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "weight_kg": {
                "type": "number",
                "description": "Body weight in kg.",
            }
        },
        "required": ["weight_kg"],
    },
)


def insert_measurement_tool(user_id: str, weight_kg: float) -> None:
    repository.insert_measurement(
        models.InsertMeasurementInput(weight_kg=weight_kg),
        user_id,
    )
