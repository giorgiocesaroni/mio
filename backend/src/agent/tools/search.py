"""Database search over a user's ingredients and recipes."""

import src.agent.models as models
import src.agent.repository as repository

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