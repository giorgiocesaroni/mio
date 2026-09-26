"""Database search over a user's ingredients and recipes."""

import src.agent.models as models
import src.agent.repository as repository

search_declaration = models.FunctionDeclaration(
    name="search",
    description=(
        "Semantically searches for ingredients and recipes by name. Pass every "
        "food you need to check in one call (a `queries` array) instead of one "
        "call per food; results come back grouped by query."
    ),
    parameters_json_schema={
        "type": "object",
        "properties": {
            "queries": {
                "type": "array",
                "items": {"type": "string"},
                "description": "The ingredient names, recipe names, or descriptions to search for.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results per category, per query (default 10).",
            },
        },
        "required": ["queries"],
    },
)


def search_tool(user_id: str, queries: list[str], limit: int = 10) -> dict:
    results = []
    for query in queries:
        try:
            ingredients = repository.search_ingredients(query, limit, user_id)
            recipes = repository.search_recipes(query, limit, user_id)
            results.append(
                {
                    "query": query,
                    "ingredients": [i.model_dump() for i in ingredients],
                    "recipes": [r.model_dump() for r in recipes],
                }
            )
        except Exception as e:
            results.append({"query": query, "error": str(e)})
    return {"results": results}
