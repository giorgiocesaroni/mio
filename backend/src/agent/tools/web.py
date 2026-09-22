"""Web research tools, backed by TinyFish."""

import src.agent.models as models
from tinyfish import TinyFish

web_search_declaration = models.FunctionDeclaration(
    name="web_search",
    description=(
        "Searches the web for information using TinyFish. Use this to research "
        "nutrition facts, find sources, or verify data online. Pass every query "
        "you need in one call (a `queries` array) instead of one call per query; "
        "results come back grouped by query."
    ),
    parameters_json_schema={
        "type": "object",
        "properties": {
            "queries": {
                "type": "array",
                "items": {"type": "string"},
                "description": "The web search queries to run.",
            },
            "location": {
                "type": "string",
                "description": "Optional location to scope results (e.g. \"United States\").",
            },
            "language": {
                "type": "string",
                "description": "Optional language code (e.g. \"en\").",
            },
        },
        "required": ["queries"],
    },
)


def web_search_tool(
    queries: list[str],
    location: str | None = None,
    language: str | None = None,
) -> dict:
    client = TinyFish()
    results = []
    for query in queries:
        try:
            response = client.search.query(
                query=query, location=location, language=language
            )
            results.append(response.model_dump())
        except Exception as e:
            results.append({"query": query, "error": str(e)})
    return {"results": results}


web_fetch_declaration = models.FunctionDeclaration(
    name="web_fetch",
    description="Fetches the content of a list of URLs using TinyFish.",
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


def web_fetch_tool(urls: list[str]) -> list[dict]:
    client = TinyFish()
    response = client.fetch.get_contents(urls=urls)
    return [r.model_dump() for r in response.results]
