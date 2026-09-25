from google import genai
from google.genai import types

from llm.client import SchemaT
from llm.exceptions import LLMResponseError


def _diagnose(response: types.GenerateContentResponse) -> str:
    feedback = response.prompt_feedback
    if feedback is not None and feedback.block_reason:
        return f"prompt blocked: {feedback.block_reason}"
    if response.candidates:
        return f"finish_reason={response.candidates[0].finish_reason}"
    return "no candidates returned"


class GeminiClient:
    def __init__(self, client: genai.Client, model: str) -> None:
        self._client = client
        self._model = model

    async def generate(self, prompt: str) -> str:
        response = await self._client.aio.models.generate_content(
            model=self._model, contents=prompt
        )
        if response.text is None:
            raise LLMResponseError(f"no text ({_diagnose(response)})")
        return response.text

    async def generate_structured(self, prompt: str, schema: type[SchemaT]) -> SchemaT:
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json", response_schema=schema
            ),
        )
        if response.parsed is None:
            raise LLMResponseError(
                f"no parseable {schema.__name__} ({_diagnose(response)})"
            )
        return response.parsed
