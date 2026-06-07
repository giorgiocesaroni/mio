from google.genai import Client, types

_client = Client()
_EMBEDDING_MODEL = "gemini-embedding-2"


def generate_embedding(text: str) -> list[float]:
    result = _client.models.embed_content(
        model=_EMBEDDING_MODEL,
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=768),
    )
    return result.embeddings[0].values
