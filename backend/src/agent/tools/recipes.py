"""Recipe template tools."""

from uuid import UUID

import src.agent.models as models
import src.agent.repository as repository

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
    image_url: str | None = None,
) -> dict:
    recipe = repository.insert_recipe(
        models.InsertRecipeInput(
            name=name,
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
            "image_url": {"type": "string", "description": "New image URL."},
        },
        "required": ["id"],
    },
)


def update_recipe_tool(
    user_id: str,
    id: UUID,
    name: str | None = None,
    image_url: str | None = None,
) -> None:
    repository.update_recipe(
        models.UpdateRecipeInput(
            id=id,
            name=name,
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