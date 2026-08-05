"""Web research tools, backed by TinyFish."""

import src.agent.models as models
from tinyfish import TinyFish

web_search_declaration = models.FunctionDeclaration(
    name="web_search",
    description="Searches the web for information using TinyFish. Use this to research nutrition facts, find sources, or verify data online.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The web search query.",
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
        "required": ["query"],
    },
)


def web_search_tool(
    query: str,
    location: str | None = None,
    language: str | None = None,
) -> dict:
    client = TinyFish()
    response = client.search.query(query=query, location=location, language=language)
    return response.model_dump()


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