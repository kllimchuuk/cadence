from google import genai
from google.genai import types

from llm.client import SchemaT


class GeminiClient:
    def __init__(self, client: genai.Client, model: str) -> None:
        self._client = client
        self._model = model

    async def generate(self, prompt: str) -> str:
        response = await self._client.aio.models.generate_content(
            model=self._model, contents=prompt
        )
        return response.text

    async def generate_structured(self, prompt: str, schema: type[SchemaT]) -> SchemaT:
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json", response_schema=schema
            ),
        )
        return response.parsed
