"""Ingredient and serving-size tools."""

from uuid import UUID

import src.agent.models as models
import src.agent.repository as repository

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
            "fat_g": {
                "type": "integer",
                "description": "Fat content in grams (per 100 g).",
            },
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


def get_serving_sizes_by_ingredient_id_tool(
    user_id: str, ingredient_id: UUID
) -> list[dict]:
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
                "description": "Human-readable label (e.g. 'cup', 'slice').",
            },
            "label_plural": {
                "type": "string",
                "description": "Plural form of the label (e.g. 'cups', 'slices').",
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
        models.InsertServingSizeInput(
            label=label, label_plural=label_plural, grams=grams
        ),
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
    user_id: str,
    id: UUID,
    label: str | None = None,
    label_plural: str | None = None,
    grams: float | None = None,
) -> dict:
    size = repository.update_serving_size(
        models.UpdateServingSizeInput(
            id=id, label=label, label_plural=label_plural, grams=grams
        ),
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
