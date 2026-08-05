"""Goal and measurement tools."""

import src.agent.models as models
import src.agent.repository as repository

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
    return goal.model_dump(mode="json") if goal else None


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
    return measurement.model_dump(mode="json") if measurement else None


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