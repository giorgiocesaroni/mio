from google.genai import Client, types


def generate_embedding(text: str) -> list[float]:
    client = Client()
    result = client.models.embed_content(
        model="gemini-embedding-2",
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=768),
    )
    if not result.embeddings or not result.embeddings[0].values:
        raise ValueError("No embeddings returned from the API.")
    return result.embeddings[0].values
