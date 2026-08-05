from typing import Optional
from uuid import UUID

import src.agent.models as models
import src.agent.repository as repository
from tinyfish import TinyFish

# ── Web Search / Fetch ────────────────────────────────────────────────────────

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


# ── Unified Search (ingredients + recipes) ────────────────────────────────────

search_declaration = models.FunctionDeclaration(
    name="search",
    description="Semantically searches for ingredients and recipes by name. Use this to find entries when the user describes a food or a recipe, instead of loading the entire list.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The ingredient name, recipe name, or description to search for.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results per category (default 10).",
            },
        },
        "required": ["query"],
    },
)


def search_tool(user_id: str, query: str, limit: int = 10) -> dict:
    ingredients = repository.search_ingredients(query, limit, user_id)
    recipes = repository.search_recipes(query, limit, user_id)
    return {
        "ingredients": [i.model_dump() for i in ingredients],
        "recipes": [r.model_dump() for r in recipes],
    }


# ── Ingredients ───────────────────────────────────────────────────────────────

get_ingredient_by_id_declaration = models.FunctionDeclaration(
    name="get_ingredient_by_id",
    description="Returns a single ingredient record by its ID.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "ingredient_id": {
                "type": "string",
                "format": "uuid",
                "description": "The UUID of the ingredient.",
            }
        },
        "required": ["ingredient_id"],
    },
)


def get_ingredient_by_id_tool(user_id: str, ingredient_id: UUID) -> dict | None:
    ingredient = repository.get_ingredient_by_id(ingredient_id, user_id)
    return ingredient.model_dump() if ingredient else None


insert_ingredient_declaration = models.FunctionDeclaration(
    name="insert_ingredient",
    description="Inserts a new ingredient into the database.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Name of the ingredient."},
            "protein_g": {
                "type": "integer",
                "description": "Protein content in grams (per 100 g).",
            },
            "carbs_g": {
                "type": "integer",
                "description": "Carbohydrate content in grams (per 100 g).",
            },
            "fat_g": {"type": "integer", "description": "Fat content in grams (per 100 g)."},
            "calories_kcal": {
                "type": "integer",
                "description": "Caloric value in kcal (per 100 g).",
            },
            "brand": {
                "type": "string",
                "description": "Brand or manufacturer (e.g. 'Barilla', 'Galbani').",
            },
            "source_url": {
                "type": "string",
                "description": "URL of the nutritional source used to obtain the data.",
            },
            "state": {
                "type": "string",
                "enum": ["raw", "cooked"],
                "description": "Whether the nutrition data refers to the raw or cooked state.",
            },
            "serving_sizes": {
                "type": "array",
                "description": "Optional list of serving sizes for this ingredient.",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {
                            "type": "string",
                            "description": "Human-readable label (e.g. '1 cup', '1 slice').",
                        },
                        "label_plural": {
                            "type": "string",
                            "description": "Plural form of the label (e.g. '2 cups', '3 slices').",
                        },
                        "grams": {
                            "type": "number",
                            "description": "Weight of this serving in grams.",
                        },
                    },
                    "required": ["label", "label_plural", "grams"],
                },
            },
        },
        "required": ["name", "protein_g", "carbs_g", "fat_g", "calories_kcal"],
    },
)


def insert_ingredient_tool(
    user_id: str,
    name: str,
    protein_g: int,
    carbs_g: int,
    fat_g: int,
    calories_kcal: int,
    state: str,
    brand: str | None = None,
    source_url: str | None = None,
    serving_sizes: list[dict] | None = None,
) -> dict:
    ingredient = repository.insert_ingredient(
        models.InsertIngredientInput(
            name=name,
            protein_g=protein_g,
            carbs_g=carbs_g,
            fat_g=fat_g,
            calories_kcal=calories_kcal,
            brand=brand,
            source_url=source_url,
            state=state,  # type: ignore
            serving_sizes=[
                models.InsertServingSizeInput(**ss) for ss in (serving_sizes or [])
            ],
        ),
        user_id,
    )
    return ingredient.model_dump()


update_ingredient_declaration = models.FunctionDeclaration(
    name="update_ingredient",
    description="Updates an existing ingredient record. Only provided fields are changed.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "id": {
                "type": "string",
                "format": "uuid",
                "description": "UUID of the ingredient to update.",
            },
            "name": {"type": "string", "description": "New name."},
            "protein_g": {"type": "integer", "description": "New protein in grams."},
            "carbs_g": {"type": "integer", "description": "New carbs in grams."},
            "fat_g": {"type": "integer", "description": "New fat in grams."},
            "calories_kcal": {
                "type": "integer",
                "description": "New calories in kcal.",
            },
            "source_url": {
                "type": "string",
                "description": "New URL of the nutritional source.",
            },
            "brand": {
                "type": "string",
                "description": "New brand or manufacturer.",
            },
            "state": {
                "type": "string",
                "enum": ["raw", "cooked"],
                "description": "New state.",
            },
        },
        "required": ["id"],
    },
)


def update_ingredient_tool(
    user_id: str,
    id: UUID,
    name: str | None = None,
    protein_g: int | None = None,
    carbs_g: int | None = None,
    fat_g: int | None = None,
    calories_kcal: int | None = None,
    source_url: str | None = None,
    brand: str | None = None,
    state: str | None = None,
) -> None:
    repository.update_ingredient(
        models.UpdateIngredientInput(
            id=id,
            name=name,
            protein_g=protein_g,
            carbs_g=carbs_g,
            fat_g=fat_g,
            calories_kcal=calories_kcal,
            source_url=source_url,
            brand=brand,
            state=state,  # type: ignore
        ),
        user_id,
    )


delete_ingredient_declaration = models.FunctionDeclaration(
    name="delete_ingredient",
    description="Deletes an ingredient record by its ID.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "ingredient_id": {
                "type": "string",
                "format": "uuid",
                "description": "UUID of the ingredient to delete.",
            }
        },
        "required": ["ingredient_id"],
    },
)


def delete_ingredient_tool(user_id: str, ingredient_id: UUID) -> None:
    repository.delete_ingredient(ingredient_id, user_id)


# ── Serving Sizes ─────────────────────────────────────────────────────────────

get_serving_sizes_by_ingredient_id_declaration = models.FunctionDeclaration(
    name="get_serving_sizes_by_ingredient_id",
    description="Returns all serving sizes for a given ingredient.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "ingredient_id": {
                "type": "string",
                "format": "uuid",
                "description": "UUID of the ingredient.",
            }
        },
        "required": ["ingredient_id"],
    },
)


def get_serving_sizes_by_ingredient_id_tool(user_id: str, ingredient_id: UUID) -> list[dict]:
    sizes = repository.get_serving_sizes_by_ingredient_id(ingredient_id, user_id)
    return [s.model_dump() for s in sizes]


insert_serving_size_declaration = models.FunctionDeclaration(
    name="insert_serving_size",
    description="Adds a new serving size to an existing ingredient.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "ingredient_id": {
                "type": "string",
                "format": "uuid",
                "description": "UUID of the ingredient to attach the serving size to.",
            },
            "label": {
                "type": "string",
                "description": "Human-readable label (e.g. '1 cup', '1 slice').",
            },
            "label_plural": {
                "type": "string",
                "description": "Plural form of the label (e.g. '2 cups', '3 slices').",
            },
            "grams": {
                "type": "number",
                "description": "Weight of this serving in grams.",
            },
        },
        "required": ["ingredient_id", "label", "label_plural", "grams"],
    },
)


def insert_serving_size_tool(
    user_id: str, ingredient_id: UUID, label: str, label_plural: str, grams: float
) -> dict:
    size = repository.insert_serving_size(
        ingredient_id,
        models.InsertServingSizeInput(label=label, label_plural=label_plural, grams=grams),
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
            "label_plural": {"type": "string", "description": "New plural label."},
            "grams": {"type": "number", "description": "New weight in grams."},
        },
        "required": ["id"],
    },
)


def update_serving_size_tool(
    user_id: str, id: UUID, label: str | None = None, label_plural: str | None = None, grams: float | None = None
) -> dict:
    size = repository.update_serving_size(
        models.UpdateServingSizeInput(id=id, label=label, label_plural=label_plural, grams=grams),
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


# ── Recipes ───────────────────────────────────────────────────────────────────

get_recipe_by_id_declaration = models.FunctionDeclaration(
    name="get_recipe_by_id",
    description="Returns a single recipe record by its ID, including its items.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "recipe_id": {
                "type": "string",
                "format": "uuid",
                "description": "The UUID of the recipe.",
            }
        },
        "required": ["recipe_id"],
    },
)


def get_recipe_by_id_tool(user_id: str, recipe_id: UUID) -> dict | None:
    recipe = repository.get_recipe_by_id(recipe_id, user_id)
    return recipe.model_dump() if recipe else None


_RECIPE_ITEM_BY_GRAMS = {
    "type": "object",
    "properties": {
        "ingredient_id": {
            "type": "string",
            "format": "uuid",
            "description": "UUID of the ingredient.",
        },
        "quantity_g": {
            "type": "number",
            "description": "Quantity in grams.",
        },
    },
    "required": ["ingredient_id", "quantity_g"],
}

_RECIPE_ITEM_BY_SERVING = {
    "type": "object",
    "properties": {
        "ingredient_id": {
            "type": "string",
            "format": "uuid",
            "description": "UUID of the ingredient.",
        },
        "quantity": {
            "type": "number",
            "description": "Number of servings.",
        },
        "serving_size_id": {
            "type": "string",
            "format": "uuid",
            "description": "UUID of the serving size.",
        },
    },
    "required": ["ingredient_id", "quantity", "serving_size_id"],
}

insert_recipe_declaration = models.FunctionDeclaration(
    name="insert_recipe",
    description="Inserts a new recipe into the database, with its ingredient items.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Name of the recipe."},
            "is_template": {
                "type": "boolean",
                "description": "Whether this recipe is a template (reusable).",
            },
            "image_url": {
                "type": "string",
                "description": "Optional image URL for the recipe.",
            },
            "items": {
                "type": "array",
                "description": "The ingredient items composing this recipe.",
                "items": {
                    "anyOf": [_RECIPE_ITEM_BY_GRAMS, _RECIPE_ITEM_BY_SERVING],
                },
            },
        },
        "required": ["name", "items"],
    },
)


def _clean_uuid(v) -> UUID | None:
    """Convert empty strings / falsy values to None for UUID fields."""
    if not v:
        return None
    return UUID(v) if isinstance(v, str) else v


def _clean_recipe_item(item: dict) -> models.InsertRecipeItemInput:
    """Sanitize a recipe item dict: convert empty strings to None."""
    qg = item.get("quantity_g") or None
    qty = item.get("quantity") or None
    ssid = _clean_uuid(item.get("serving_size_id"))
    if qg is not None and (qty is not None or ssid is not None):
        raise ValueError(f"Ingredient {item.get('ingredient_id')}: use quantity_g OR quantity+serving_size_id, not both.")
    if qg is None and qty is None and ssid is None:
        raise ValueError(f"Ingredient {item.get('ingredient_id')}: provide quantity_g or quantity+serving_size_id.")
    return models.InsertRecipeItemInput(
        ingredient_id=UUID(item["ingredient_id"]),
        quantity_g=qg,
        quantity=qty,
        serving_size_id=ssid,
    )


def insert_recipe_tool(
    user_id: str,
    name: str,
    items: list[dict],
    is_template: bool = False,
    image_url: str | None = None,
) -> dict:
    recipe = repository.insert_recipe(
        models.InsertRecipeInput(
            name=name,
            is_template=is_template,
            image_url=image_url,
            items=[_clean_recipe_item(item) for item in items],
        ),
        user_id,
    )
    return recipe.model_dump()


update_recipe_declaration = models.FunctionDeclaration(
    name="update_recipe",
    description="Updates an existing recipe record. Only provided fields are changed.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "id": {
                "type": "string",
                "format": "uuid",
                "description": "UUID of the recipe to update.",
            },
            "name": {"type": "string", "description": "New name."},
            "is_template": {"type": "boolean", "description": "New template flag."},
            "image_url": {"type": "string", "description": "New image URL."},
        },
        "required": ["id"],
    },
)


def update_recipe_tool(
    user_id: str,
    id: UUID,
    name: str | None = None,
    is_template: bool | None = None,
    image_url: str | None = None,
) -> None:
    repository.update_recipe(
        models.UpdateRecipeInput(
            id=id,
            name=name,
            is_template=is_template,
            image_url=image_url,
        ),
        user_id,
    )


delete_recipe_declaration = models.FunctionDeclaration(
    name="delete_recipe",
    description="Deletes a recipe record by its ID.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "recipe_id": {
                "type": "string",
                "format": "uuid",
                "description": "UUID of the recipe to delete.",
            }
        },
        "required": ["recipe_id"],
    },
)


def delete_recipe_tool(user_id: str, recipe_id: UUID) -> None:
    repository.delete_recipe(recipe_id, user_id)


# ── Logs ──────────────────────────────────────────────────────────────────────

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
    "required": ["recipe_id", "quantity_g", "meal_type", "log_for"],
}

insert_log_by_grams_declaration = models.FunctionDeclaration(
    name="insert_log_by_grams",
    description="Logs an entry by specifying the quantity in grams. Provide either food_id (ingredient) or recipe_id (recipe).",
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

_LOG_BY_SERVING_RECIPE = {
    "type": "object",
    "properties": {
        "recipe_id": {
            "type": "string",
            "format": "uuid",
            "description": "ID of the recipe being logged.",
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
    "required": ["recipe_id", "quantity", "meal_type", "log_for"],
}

insert_log_by_serving_size_declaration = models.FunctionDeclaration(
    name="insert_log_by_serving_size",
    description="Logs an entry by specifying a serving size and the number of servings consumed. Provide either food_id (ingredient) or recipe_id (recipe).",
    parameters_json_schema={
        "anyOf": [_LOG_BY_SERVING_INGREDIENT, _LOG_BY_SERVING_RECIPE],
    },
)


def insert_log_by_serving_size_tool(
    user_id: str,
    quantity: float,
    meal_type: str,
    log_for: str,
    food_id: str | None = None,
    serving_size_id: str | None = None,
    recipe_id: str | None = None,
) -> dict:
    fid = UUID(food_id) if food_id else None
    rid = UUID(recipe_id) if recipe_id else None
    repository.insert_log_by_serving_size(
        models.InsertLogByServingSizeInput(
            food_id=fid,
            serving_size_id=UUID(serving_size_id) if serving_size_id else None,
            quantity=quantity,
            recipe_id=rid,
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
            "quantity_g": {"type": "integer", "description": "New quantity in grams."},
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
    quantity_g: int | None = None,
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


# ── Goals ─────────────────────────────────────────────────────────────────────

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


# ── Measurements ──────────────────────────────────────────────────────────────

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
